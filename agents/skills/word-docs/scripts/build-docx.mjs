#!/usr/bin/env node
// Build a .docx from Markdown with YAML front matter, using Word's current default styles.
// Usage: node build-docx.mjs input.md [-o output.docx] [--image-scale 3]
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { marked } from "marked";
import {
  AlignmentType,
  Document,
  HeadingLevel,
  LevelFormat,
  Packer,
  Paragraph,
  TableOfContents,
  TextRun,
} from "docx";
import { splitFrontMatter, resolveMeta } from "./lib/front-matter.mjs";
import { blockElements, baseDirOf } from "./lib/blocks.mjs";
import { characterStyles, defaultStyles, paragraphStyles, COLOR } from "./lib/word-styles.mjs";
import { footers, headers, sectionProperties, textHeightDxa, textWidthDxa } from "./lib/page.mjs";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_IMAGE_SCALE = 3; // diagrams are rendered at 3x for print

function parseArgs(argv) {
  const args = { imageScale: DEFAULT_IMAGE_SCALE };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-o" || arg === "--output") args.output = argv[++i];
    else if (arg === "--image-scale") args.imageScale = Number(argv[++i]);
    else if (arg.startsWith("-")) throw new Error(`Unknown option: ${arg}`);
    else if (!args.input) args.input = arg;
    else throw new Error(`Unexpected argument: ${arg}`);
  }
  if (!args.input) throw new Error("Usage: build-docx.mjs input.md [-o output.docx] [--image-scale N]");
  if (!Number.isFinite(args.imageScale) || args.imageScale <= 0) throw new Error("--image-scale must be a positive number");
  args.output ??= args.input.replace(/\.md$/i, "") + ".docx";
  return args;
}

function numberingConfig() {
  const indent = (level) => ({ left: 720 * (level + 1), hanging: 360 });
  const bullets = ["•", "◦", "▪"];
  const numbers = [LevelFormat.DECIMAL, LevelFormat.LOWER_LETTER, LevelFormat.LOWER_ROMAN];
  return {
    config: [
      {
        reference: "bullets",
        levels: bullets.map((text, level) => ({
          level,
          format: LevelFormat.BULLET,
          text,
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: indent(level) } },
        })),
      },
      {
        reference: "numbered",
        levels: numbers.map((format, level) => ({
          level,
          format,
          text: `%${level + 1}.`,
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: indent(level) } },
        })),
      },
    ],
  };
}

function titleBlock(meta) {
  const byline = [meta.author, meta.dateText, meta.status].filter(Boolean).join("  |  ");
  const elements = [new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: meta.title })] })];
  if (meta.subtitle) elements.push(new Paragraph({ style: "Subtitle", children: [new TextRun({ text: meta.subtitle })] }));
  elements.push(
    new Paragraph({
      spacing: { before: 0, after: 240 },
      children: [new TextRun({ text: byline, color: COLOR.muted, size: 20 })],
    }),
  );
  return elements;
}

function tableOfContents() {
  return [
    new Paragraph({ style: "TOCHeading", children: [new TextRun({ text: "Contents" })] }),
    new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-3" }),
  ];
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const defaults = JSON.parse(readFileSync(join(SCRIPT_DIR, "defaults.json"), "utf8"));
  const source = readFileSync(args.input, "utf8");
  const { meta: rawMeta, body } = splitFrontMatter(source);
  const meta = resolveMeta(rawMeta, defaults);

  const ctx = {
    baseDir: baseDirOf(args.input),
    textWidthDxa: textWidthDxa(meta.page),
    textHeightDxa: textHeightDxa(meta.page),
    imageScale: args.imageScale,
    counters: { figure: 0, list: 0 },
  };
  const tokens = marked.lexer(body, { gfm: true });
  const bodyElements = blockElements(tokens, ctx);

  const doc = new Document({
    creator: meta.author,
    lastModifiedBy: meta.author,
    title: meta.title,
    subject: meta.subtitle,
    description: meta.description,
    keywords: meta.keywords,
    features: { updateFields: meta.toc },
    styles: { default: defaultStyles, paragraphStyles, characterStyles },
    numbering: numberingConfig(),
    sections: [
      {
        properties: sectionProperties(meta),
        headers: headers(meta),
        footers: footers(meta),
        children: [...titleBlock(meta), ...(meta.toc ? tableOfContents() : []), ...bodyElements],
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  const output = resolve(args.output);
  writeFileSync(output, buffer);
  process.stdout.write(`wrote ${output} (${ctx.counters.figure} figures)\n`);
}

main().catch((error) => {
  process.stderr.write(`build-docx: ${error.message}\n`);
  process.exit(1);
});
