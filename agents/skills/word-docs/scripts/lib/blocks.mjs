import { dirname, resolve } from "node:path";
import { BorderStyle, HeadingLevel, PageBreak, Paragraph, TextRun } from "docx";
import { inlineRuns } from "./inline.mjs";
import { COLOR } from "./word-styles.mjs";
import { figure, soleImage } from "./figures.mjs";
import { tableElement } from "./tables.mjs";

const HEADING_LEVELS = [
  HeadingLevel.HEADING_1,
  HeadingLevel.HEADING_2,
  HeadingLevel.HEADING_3,
  HeadingLevel.HEADING_4,
  HeadingLevel.HEADING_5,
  HeadingLevel.HEADING_6,
];
const PAGE_BREAK_MARKER = /^<!--\s*pagebreak\s*-->\s*$/i;
const HTML_COMMENT = /^<!--[\s\S]*-->\s*$/;
// A block longer than this cannot move to the next page as a whole without leaving a gap, so it may break.
const MAX_KEPT_CODE_LINES = 40;

// Converts marked block tokens into docx elements.
// ctx: { baseDir, textWidthDxa, textHeightDxa, imageScale, paragraphStyle?, counters: { figure, list } }
// `counters` is shared by reference so nested contexts keep numbering continuous.
export function blockElements(tokens, ctx, listDepth = 0) {
  return tokens.flatMap((token, index) => blockElement(token, ctx, listDepth, nextContent(tokens, index)));
}

function nextContent(tokens, index) {
  return tokens.slice(index + 1).find((token) => token.type !== "space") ?? null;
}

function blockElement(token, ctx, listDepth, next) {
  switch (token.type) {
    case "space":
      return [];
    case "heading":
      return [new Paragraph({ heading: HEADING_LEVELS[token.depth - 1], children: inlineRuns(token.tokens) })];
    case "paragraph":
      return paragraphOrFigure(token, ctx, next);
    case "list":
      return listParagraphs(token, ctx, listDepth);
    case "table":
      // Word puts no space after a table; a tiny spacer paragraph keeps the next line off the border.
      return [tableElement(token, ctx), new Paragraph({ style: "TableSpacer", children: [] })];
    case "code":
      return codeParagraphs(token);
    case "blockquote":
      return blockElements(token.tokens, { ...ctx, paragraphStyle: "Quote" }, listDepth);
    case "hr":
      return [new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLOR.border, space: 1 } } })];
    case "html":
      if (PAGE_BREAK_MARKER.test(token.text)) return [new Paragraph({ children: [new PageBreak()] })];
      if (HTML_COMMENT.test(token.text)) return [];
      process.stderr.write(`warning: raw HTML block skipped: ${token.text.trim().slice(0, 60)}\n`);
      return [];
    case "text":
      return [new Paragraph({ children: inlineRuns(token.tokens ?? [{ type: "text", text: token.text }]) })];
    default:
      throw new Error(`Unsupported Markdown block: ${token.type}`);
  }
}

// A sentence that ends with a colon introduces the block after it, so the two stay on one page.
function introducesBlock(token, next) {
  if (!next || !token.text.trimEnd().endsWith(":")) return false;
  if (["table", "code", "list"].includes(next.type)) return true;
  return next.type === "paragraph" && soleImage(next.tokens ?? []) !== null;
}

function paragraphOrFigure(token, ctx, next) {
  const inline = token.tokens ?? [];
  const image = soleImage(inline);
  if (image) return figure(image, ctx);
  return [new Paragraph({ style: ctx.paragraphStyle, keepNext: introducesBlock(token, next), children: inlineRuns(inline) })];
}

function listParagraphs(token, ctx, listDepth) {
  if (listDepth > 2) throw new Error("Lists nest at most three levels deep.");
  const reference = token.ordered ? "numbered" : "bullets";
  // Every ordered list, at any depth, gets its own numbering instance so it restarts at 1.
  if (token.ordered) ctx.counters.list += 1;
  const instance = ctx.counters.list;
  return token.items.flatMap((item) => {
    const [first, ...rest] = item.tokens;
    const firstInline = first?.tokens ?? [];
    const lead = new Paragraph({
      numbering: { reference, level: listDepth, instance },
      children: inlineRuns(firstInline),
    });
    const nested = blockElements(rest, ctx, listDepth + 1);
    return [lead, ...nested];
  });
}

// Short blocks stay on one page. A long block keeps its first two and last two lines together,
// so it never leaves a single line at the bottom or top of a page.
function codeParagraphs(token) {
  const lines = token.text.split("\n");
  const last = lines.length - 1;
  const keepsWhole = lines.length <= MAX_KEPT_CODE_LINES;
  const keepsNext = (index) => index < last && (keepsWhole || index === 0 || index === last - 1);
  return lines.map(
    (line, index) =>
      new Paragraph({
        style: "CodeBlock",
        keepNext: keepsNext(index),
        spacing: { before: index === 0 ? 120 : 0, after: index === last ? 160 : 0 },
        children: [new TextRun({ text: line })],
      }),
  );
}

export function baseDirOf(inputPath) {
  return dirname(resolve(inputPath));
}
