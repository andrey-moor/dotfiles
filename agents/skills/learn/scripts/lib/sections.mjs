import { marked } from "marked";
import { resolve, dirname } from "node:path";
import { existsSync } from "node:fs";
import { embedDiagram } from "./figures.mjs";

// Canonical H1 sections of a study file, in reading order, and their depth.
export const SECTIONS = [
  { key: "gist", name: "Gist", match: /^gist/i, depth: "gist" },
  { key: "mechanism", name: "Mechanism", match: /^mechanism/i, depth: "mechanism" },
  { key: "example", name: "Worked example", match: /^worked example/i, depth: "mechanism" },
  { key: "parts", name: "Parts", match: /^parts/i, depth: "mechanism" },
  { key: "misconceptions", name: "Misconceptions", match: /^(misconceptions|where people get it wrong)/i, depth: "mechanism" },
  { key: "check", name: "Check yourself", match: /^check yourself/i, depth: "mechanism" },
  { key: "glossary", name: "Glossary", match: /^glossary/i, depth: "mechanism" },
  { key: "deeper", name: "Go deeper", match: /^go deeper/i, depth: "details" },
];

const stripComments = (text) => text.replace(/<!--[\s\S]*?-->/g, "");
const SAFE_HREF = /^(https?:|mailto:|#|[^:]*$)/i;
const INLINE_TAGS = ["em", "strong", "a", "code", "del", "span"];
const isBalanced = (html) => INLINE_TAGS.every((tag) => (html.match(new RegExp(`<${tag}\\b`, "g")) ?? []).length === (html.match(new RegExp(`</${tag}>`, "g")) ?? []).length);

export const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const slug = (text) => text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
export const plain = (tokens) => (tokens ?? []).map((t) => (t.tokens ? plain(t.tokens) : t.text ?? "")).join("");

// Split top-level tokens into H1 sections. Returns [{ key, depth, title, tokens }].
export function splitSections(tokens) {
  const sections = [];
  let current = null;
  for (const token of tokens) {
    if (token.type === "heading" && token.depth === 1) {
      const title = plain(token.tokens);
      const def = SECTIONS.find((s) => s.match.test(title)) ?? { key: slug(title), depth: "mechanism" };
      current = { key: def.key, depth: def.depth, title, tokens: [] };
      sections.push(current);
    } else if (current) {
      current.tokens.push(token);
    } else if (token.type !== "space" && !(token.type === "html" && !stripComments(token.text).trim())) {
      throw new Error("Study file must start with a level-1 heading (for example: # Gist)");
    }
  }
  return sections;
}

// Group tokens under headings of one depth: { lead, groups: [{ title, tokens }] }.
export function splitByHeading(tokens, depth) {
  const groups = [];
  const lead = [];
  let current = null;
  for (const token of tokens) {
    if (token.type === "heading" && token.depth === depth) {
      current = { title: plain(token.tokens), tokens: [] };
      groups.push(current);
    } else if (current) current.tokens.push(token);
    else lead.push(token);
  }
  return { lead, groups };
}

export const FACT_LABELS = ["What", "Why", "Without it", "Remember"];
const FACT_SPLIT = /<strong>(What|Why|Without it|Remember):<\/strong>/;

// Paragraphs carrying the four part labels become one labeled list, so each fact reads on its own line.
function factsToList(html) {
  const converted = html.replace(/<p>([\s\S]*?)<\/p>/g, (whole, inner) => {
    if (!FACT_SPLIT.test(inner)) return whole;
    const pieces = inner.split(FACT_SPLIT);
    if (!pieces.filter((_, i) => i % 2 === 0).every(isBalanced)) return whole;
    const before = pieces[0].trim();
    let items = "";
    for (let i = 1; i < pieces.length; i += 2) {
      const label = pieces[i];
      items += `<dt${label === "Remember" ? ' class="fact-remember"' : ""}>${label}</dt><dd>${(pieces[i + 1] ?? "").trim()}</dd>`;
    }
    return `${before ? `<p>${before}</p>` : ""}<dl class="part-facts">${items}</dl>`;
  });
  return converted.replace(/<\/dl>\s*<dl class="part-facts">/g, "");
}

// The walkthrough word is "Step" unless front matter sets another, for systems that have steps of their own.
export function headingNumber(title, label) {
  const match = title.match(new RegExp(`^(?:${label}|step)\\s*(\\d+)\\s*[:.]\\s*`, "i"));
  return match ? { number: Number(match[1]), rest: title.slice(match[0].length) } : { number: NaN, rest: title };
}

export function createRenderer(inputPath, { walkthroughLabel = "Step" } = {}) {
  const baseDir = dirname(resolve(inputPath));
  const figures = { css: [], controllers: new Set(), fontLinks: new Set(), stepped: 0, count: 0, stepCounts: [], partsWithoutList: [] };
  const renderer = new marked.Renderer();
  // HTML comments are author notes and are dropped. Other raw HTML is shown as text, never executed.
  renderer.html = ({ text }) => {
    const rest = stripComments(text);
    return rest.trim() ? escapeHtml(rest) : "";
  };
  // Only http, https, mailto, anchors, and relative paths become links; anything else stays text.
  renderer.link = function ({ href, title, tokens }) {
    const text = this.parser.parseInline(tokens);
    if (!SAFE_HREF.test(href)) return text;
    return `<a href="${escapeHtml(href)}"${title ? ` title="${escapeHtml(title)}"` : ""}>${text}</a>`;
  };

  renderer.image = ({ href, text }) => {
    const path = resolve(baseDir, href);
    if (!existsSync(path)) throw new Error(`Figure not found: ${path}`);
    figures.count += 1;
    const caption = escapeHtml(`Figure ${figures.count}. ${text}`);
    if (/\.html?$/i.test(href)) {
      const embed = embedDiagram(path);
      figures.css.push(embed.css);
      if (embed.controller) figures.controllers.add(embed.controller);
      if (embed.fontLink) figures.fontLinks.add(embed.fontLink);
      if (embed.isStepped) { figures.stepped += 1; figures.stepCounts.push(embed.stepCount); }
      return `<figure class="figure${embed.isStepped ? " figure-stepped" : ""}">${embed.markup}<figcaption>${caption}</figcaption></figure>`;
    }
    return `<figure class="figure"><img src="${escapeHtml(href)}" alt="${escapeHtml(text)}"><figcaption>${caption}</figcaption></figure>`;
  };

  const toHtml = (tokens) => marked.parser(tokens, { renderer });

  function renderExample(section) {
    const { lead, groups } = splitByHeading(section.tokens, 2);
    if (groups.length === 0) throw new Error(`Worked example needs "## ${walkthroughLabel} N: title" subsections`);
    const steps = groups
      .map((g, i) => {
        const title = headingNumber(g.title, walkthroughLabel).rest;
        return `<li class="step" data-step="${i + 1}"><h3><span class="step-number">${i + 1}</span>${escapeHtml(title)}</h3>${toHtml(g.tokens)}</li>`;
      })
      .join("");
    return `${toHtml(lead)}
<div class="stepper" data-stepper data-step-count="${groups.length}" data-label="${escapeHtml(walkthroughLabel)}">
  <div class="stepper-controls" data-stepper-controls hidden>
    <button type="button" data-stepper-action="prev">Previous</button>
    <span class="stepper-status" data-stepper-status>${escapeHtml(walkthroughLabel)} 1 of ${groups.length}</span>
    <button type="button" data-stepper-action="next">Next</button>
    <button type="button" data-stepper-action="all">Show all</button>
  </div>
  <ol class="steps">${steps}</ol>
</div>`;
  }

  function renderParts(section) {
    const { lead, groups } = splitByHeading(section.tokens, 2);
    const parts = groups
      .map((g) => {
        const inner = splitByHeading(g.tokens, 3);
        const details = inner.groups
          .map((d) => `<details class="depth-details part-details"><summary>${escapeHtml(d.title)}</summary>${toHtml(d.tokens)}</details>`)
          .join("");
        const facts = factsToList(toHtml(inner.lead));
        if (!facts.includes('class="part-facts"')) figures.partsWithoutList.push(g.title);
        return `<section class="part" id="part-${slug(g.title)}"><h3>${escapeHtml(g.title)}</h3>${facts}${details}</section>`;
      })
      .join("");
    return toHtml(lead) + parts;
  }

  function renderCheck(section) {
    const { lead, groups } = splitByHeading(section.tokens, 2);
    if (groups.length === 0) throw new Error('Check yourself needs "## Q: question" subsections with the answer below each');
    const cards = groups
      .map((g, i) => {
        const question = g.title.replace(/^q\s*\d*\s*[:.]\s*/i, "");
        return `<details class="card" data-card="${i + 1}"><summary>${escapeHtml(question)}</summary><div class="answer">${toHtml(g.tokens)}</div><div class="grade" data-grade-controls hidden><button type="button" data-grade="got">Got it</button><button type="button" data-grade="missed">Missed</button></div></details>`;
      })
      .join("");
    return `${toHtml(lead)}<p class="progress" data-progress hidden></p><label class="review-toggle" data-review-toggle hidden><input type="checkbox" data-review-missed> Review missed only</label><div class="cards">${cards}</div>`;
  }

  function renderGlossary(section) {
    const terms = [];
    for (const token of section.tokens) {
      if (token.type !== "list") continue;
      for (const item of token.items) {
        const text = plain(item.tokens);
        const m = text.match(/^([^:]+?)\s*:\s*(.+)$/s);
        if (m) terms.push({ term: m[1].trim(), definition: m[2].trim() });
      }
    }
    if (terms.length === 0) throw new Error('Glossary needs list items of the form "- **Term**: definition"');
    const dl = terms.map((t) => `<dt id="term-${slug(t.term)}">${escapeHtml(t.term)}</dt><dd>${escapeHtml(t.definition)}</dd>`).join("");
    return { html: `<dl class="glossary">${dl}</dl>`, terms };
  }

  return { toHtml, renderExample, renderParts, renderCheck, renderGlossary, figures };
}
