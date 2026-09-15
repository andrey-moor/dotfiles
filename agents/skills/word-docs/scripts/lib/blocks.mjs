import { dirname, relative, resolve, isAbsolute } from "node:path";
import { existsSync } from "node:fs";
import {
  AlignmentType,
  BorderStyle,
  HeadingLevel,
  ImageRun,
  PageBreak,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} from "docx";
import { inlineRuns, decodeEntities } from "./inline.mjs";
import { readImage } from "./images.mjs";
import { COLOR } from "./word-styles.mjs";

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
const MAX_IMAGE_WIDTH_PX = 624; // 6.5in text width at 96 dpi
const THIN_BORDER = { style: BorderStyle.SINGLE, size: 4, color: COLOR.text1 };
const CELL_BORDERS = { top: THIN_BORDER, bottom: THIN_BORDER, left: THIN_BORDER, right: THIN_BORDER };

// Converts marked block tokens into docx elements.
// ctx: { baseDir, textWidthDxa, imageScale, paragraphStyle?, counters: { figure, list } }
// `counters` is shared by reference so nested contexts keep numbering continuous.
export function blockElements(tokens, ctx, listDepth = 0) {
  return tokens.flatMap((token) => blockElement(token, ctx, listDepth));
}

function blockElement(token, ctx, listDepth) {
  switch (token.type) {
    case "space":
      return [];
    case "heading":
      return [new Paragraph({ heading: HEADING_LEVELS[token.depth - 1], children: inlineRuns(token.tokens) })];
    case "paragraph":
      return paragraphOrFigure(token, ctx);
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

// A paragraph that is exactly one image, or one link wrapping one image, is a figure.
function soleImage(inline) {
  if (inline.length !== 1) return null;
  const [only] = inline;
  if (only.type === "image") return only;
  if (only.type === "link" && only.tokens?.length === 1 && only.tokens[0].type === "image") return only.tokens[0];
  return null;
}

function paragraphOrFigure(token, ctx) {
  const inline = token.tokens ?? [];
  const image = soleImage(inline);
  if (!image) return [new Paragraph({ style: ctx.paragraphStyle, children: inlineRuns(inline) })];
  return figure(image, ctx);
}

// Images must live in the document's folder (or below it); nothing else on disk is embeddable.
function imagePath(href, ctx) {
  if (!href || !href.trim()) throw new Error("Image reference is empty. Give the figure a file name.");
  const path = resolve(ctx.baseDir, href);
  const rel = relative(ctx.baseDir, path);
  if (rel.startsWith("..") || isAbsolute(rel)) {
    throw new Error(`Image must be inside the document folder ${ctx.baseDir}: ${href}`);
  }
  if (!existsSync(path)) throw new Error(`Image not found: ${path}`);
  return path;
}

function figure(imageToken, ctx) {
  const path = imagePath(imageToken.href, ctx);
  const image = readImage(path);
  const scale = Math.min(1, MAX_IMAGE_WIDTH_PX / (image.width / ctx.imageScale));
  const width = Math.round((image.width / ctx.imageScale) * scale);
  const height = Math.round((image.height / ctx.imageScale) * scale);
  ctx.counters.figure += 1;
  const caption = decodeEntities(imageToken.text || imageToken.title || "");
  const label = `Figure ${ctx.counters.figure}`;
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      keepNext: true,
      spacing: { before: 120, after: 60 },
      children: [
        new ImageRun({
          type: image.type,
          data: image.data,
          transformation: { width, height },
          altText: { name: label, title: label, description: caption || label },
        }),
      ],
    }),
    new Paragraph({
      style: "Caption",
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: caption ? `${label}. ${caption}` : label })],
    }),
  ];
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

function codeParagraphs(token) {
  const lines = token.text.split("\n");
  return lines.map(
    (line, index) =>
      new Paragraph({
        style: "CodeBlock",
        keepNext: index < lines.length - 1,
        spacing: { before: index === 0 ? 120 : 0, after: index === lines.length - 1 ? 160 : 0 },
        children: [new TextRun({ text: line })],
      }),
  );
}

function tableElement(token, ctx) {
  const widths = columnWidths(token, ctx.textWidthDxa);
  const alignments = token.align.map(toAlignment);
  const row = (cells, isHeader) =>
    new TableRow({
      tableHeader: isHeader,
      cantSplit: true,
      children: cells.map(
        (cell, i) =>
          new TableCell({
            width: { size: widths[i], type: WidthType.DXA },
            borders: CELL_BORDERS,
            shading: isHeader ? { type: "clear", fill: COLOR.codeBackground } : undefined,
            margins: { top: 60, bottom: 60, left: 100, right: 100 },
            children: [
              new Paragraph({
                alignment: alignments[i],
                spacing: { before: 0, after: 0, line: 240 },
                children: inlineRuns(cell.tokens, isHeader ? { bold: true } : {}),
              }),
            ],
          }),
      ),
    });
  return new Table({
    width: { size: ctx.textWidthDxa, type: WidthType.DXA },
    columnWidths: widths,
    rows: [row(token.header, true), ...token.rows.map((cells) => row(cells, false))],
  });
}

// Each column gets at least enough width for its longest word, then the rest is
// shared in proportion to the text each column carries.
const CHAR_DXA = 125; // about one 12pt Aptos character
const CELL_PADDING_DXA = 260;

function columnWidths(token, totalDxa) {
  const columnCells = token.header.map((cell, i) => [cell, ...token.rows.map((cells) => cells[i])].filter(Boolean));
  const longestWord = columnCells.map((cells) =>
    Math.max(...cells.flatMap((cell) => cell.text.split(/\s+/).map((word) => word.length)), 1),
  );
  const minimums = longestWord.map((n) => n * CHAR_DXA + CELL_PADDING_DXA);
  const textLength = columnCells.map((cells) => Math.max(...cells.map((cell) => cell.text.length), 4));
  const minimumTotal = minimums.reduce((a, b) => a + b, 0);
  if (minimumTotal >= totalDxa) {
    process.stderr.write("warning: table is too wide for the page; long words will break\n");
    return distribute(minimums, totalDxa);
  }
  const spare = totalDxa - minimumTotal;
  const weightTotal = textLength.reduce((a, b) => a + b, 0);
  const widths = minimums.map((min, i) => min + (textLength[i] / weightTotal) * spare);
  return distribute(widths, totalDxa);
}

function distribute(weights, totalDxa) {
  const sum = weights.reduce((a, b) => a + b, 0);
  const widths = weights.map((w) => Math.floor((w / sum) * totalDxa));
  widths[widths.length - 1] += totalDxa - widths.reduce((a, b) => a + b, 0);
  return widths;
}

function toAlignment(align) {
  if (align === "center") return AlignmentType.CENTER;
  if (align === "right") return AlignmentType.RIGHT;
  return AlignmentType.LEFT;
}

export function baseDirOf(inputPath) {
  return dirname(resolve(inputPath));
}
