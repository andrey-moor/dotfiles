#!/usr/bin/env node
// Render a study Markdown file into a single-file interactive study page.
// Usage: node build-study.mjs study.md [-o study.html]
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { marked } from "marked";
import { parse as parseYaml } from "yaml";
import { splitSections, createRenderer, SECTIONS, escapeHtml as escape } from "./lib/sections.mjs";
import { CSS, JS } from "./lib/assets.mjs";
import { lintStudy } from "./lib/lint.mjs";

const REQUIRED = ["gist", "example", "parts", "check", "glossary"];
const FRONT_MATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-o" || arg === "--output") args.output = argv[++i];
    else if (arg.startsWith("-")) throw new Error(`Unknown option: ${arg}`);
    else if (!args.input) args.input = arg;
    else throw new Error(`Unexpected argument: ${arg}`);
  }
  if (!args.input) throw new Error("Usage: build-study.mjs study.md [-o study.html]");
  args.output ??= args.input.replace(/\.md$/i, "") + ".html";
  return args;
}

function readStudy(path) {
  const source = readFileSync(path, "utf8");
  const match = source.match(FRONT_MATTER);
  if (!match) throw new Error("Study file needs YAML front matter with at least a title.");
  const meta = parseYaml(match[1]) ?? {};
  if (!meta.title) throw new Error('Front matter needs a "title:" line.');
  if (meta.walkthrough !== undefined && !/^[A-Za-z]{2,20}$/.test(String(meta.walkthrough))) {
    throw new Error('Front matter "walkthrough" must be one word of letters, for example: walkthrough: Stage');
  }
  return { meta, body: source.slice(match[0].length) };
}


function renderSection(section, r) {
  switch (section.key) {
    case "example": return r.renderExample(section);
    case "parts": return r.renderParts(section);
    case "check": return r.renderCheck(section);
    case "glossary": return r.renderGlossary(section).html;
    default: return r.toHtml(section.tokens).replace(/<p><strong>Remember:<\/strong>/g, '<p class="remember"><strong>Remember:</strong>');
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const { meta, body } = readStudy(args.input);
  const sections = splitSections(marked.lexer(body, { gfm: true }));
  const present = new Set(sections.map((s) => s.key));
  const missing = REQUIRED.filter((k) => !present.has(k));
  if (missing.length) {
    const names = missing.map((k) => SECTIONS.find((s) => s.key === k).name);
    throw new Error(`Study file is missing required sections: ${names.join(", ")}`);
  }
  const walkthroughLabel = meta.walkthrough ? String(meta.walkthrough) : "Step";
  const r = createRenderer(args.input, { walkthroughLabel });
  const glossary = r.renderGlossary(sections.find((s) => s.key === "glossary"));
  const rendered = sections
    .map((s) => `<section class="depth-${s.depth}" data-section="${s.key}" id="${s.key}"><h2>${escape(s.title)}</h2>${renderSection(s, r)}</section>`)
    .join("\n");
  const { errors, warnings } = lintStudy(sections, r.figures, args.input, walkthroughLabel);
  warnings.forEach((warning) => process.stderr.write(`warning: ${warning}\n`));
  if (errors.length) throw new Error(`the study file breaks ${errors.length} rule(s):\n  ${errors.join("\n  ")}`);
  const sources = Array.isArray(meta.sources) ? meta.sources.join(", ") : meta.sources ?? "";
  const metaLine = [meta.goal && `Goal: ${meta.goal}`, sources && `Sources: ${sources}`, meta.date && String(meta.date)].filter(Boolean).join("  |  ");

  const html = `<!DOCTYPE html>
<html lang="en" data-study="${escape(meta.title)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escape(meta.title)}</title>
${[...r.figures.fontLinks].join("\n")}
<style>${CSS}</style>
<style>${r.figures.css.join("\n")}</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <p class="eyebrow">Study page</p>
  <h1>${escape(meta.title)}</h1>
  ${metaLine ? `<p class="meta">${escape(metaLine)}</p>` : ""}
</header>
<nav class="depth-switch" data-depth-switch hidden aria-label="Depth">
  <span>Depth</span>
  <button type="button" data-depth="gist">Gist</button>
  <button type="button" data-depth="mechanism">Mechanism</button>
  <button type="button" data-depth="details">Details</button>
</nav>
${rendered}
</div>
<script id="glossary-data" type="application/json">${JSON.stringify(glossary.terms).replace(/</g, "\\u003c")}</script>
${[...r.figures.controllers].join("\n")}
<script>${JS}</script>
</body>
</html>`;
  const output = resolve(args.output);
  writeFileSync(output, html);
  process.stdout.write(`wrote ${output} (${sections.length} sections, ${r.figures.count} figures, ${r.figures.stepped} stepped, ${glossary.terms.length} terms, ${warnings.length} warnings)\n`);
}

try {
  main();
} catch (error) {
  process.stderr.write(`build-study: ${error.message}\n`);
  process.exit(1);
}
