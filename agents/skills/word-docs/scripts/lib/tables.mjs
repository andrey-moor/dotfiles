import { AlignmentType, BorderStyle, Paragraph, Table, TableCell, TableRow, WidthType } from "docx";
import { inlineRuns, decodeEntities } from "./inline.mjs";
import { COLOR } from "./word-styles.mjs";

const THIN_BORDER = { style: BorderStyle.SINGLE, size: 4, color: COLOR.text1 };
const CELL_BORDERS = { top: THIN_BORDER, bottom: THIN_BORDER, left: THIN_BORDER, right: THIN_BORDER };
const CHAR_DXA = 125; // about one 12pt Aptos character
const CELL_PADDING_DXA = 260;
const MAX_COLUMN_SHARE = 0.45; // in tables of three or more columns, so no column starves the others
const MIN_COLUMN_SHARE = 0.15; // so a prose column never wraps a word or two per line

export function tableElement(token, ctx) {
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

// The text a reader sees in a cell: link text without its URL, code without backticks.
function cellText(cell) {
  const walk = (tokens) =>
    (tokens ?? [])
      .map((t) => (t.tokens ? walk(t.tokens) : t.type === "br" ? " " : decodeEntities(t.text ?? "")))
      .join("");
  return cell.tokens ? walk(cell.tokens) : cell.text;
}

const sum = (values) => values.reduce((a, b) => a + b, 0);

// Each column gets room for its longest word and a minimum share, then the rest is shared in
// proportion to the text each column carries. In tables of three or more columns, width above the
// cap moves to the other columns.
export function columnWidths(token, totalDxa) {
  const count = token.header.length;
  const texts = token.header.map((cell, i) => [cell, ...token.rows.map((cells) => cells[i])].filter(Boolean).map(cellText));
  const longestWord = texts.map((cells) => Math.max(1, ...cells.flatMap((text) => text.split(/\s+/).map((word) => word.length))));
  const textLength = texts.map((cells) => Math.max(4, ...cells.map((text) => text.length)));
  const cap = count >= 3 ? MAX_COLUMN_SHARE * totalDxa : totalDxa;
  const minimum = Math.min(MIN_COLUMN_SHARE, 0.9 / count) * totalDxa;
  const floors = longestWord.map((letters) => Math.min(cap, Math.max(minimum, letters * CHAR_DXA + CELL_PADDING_DXA)));
  const tooLong = longestWord.flatMap((letters, i) => (letters * CHAR_DXA + CELL_PADDING_DXA > cap ? [i] : []));
  if (tooLong.length) {
    process.stderr.write(`warning: the longest word in column ${tooLong.map((i) => `"${texts[i][0]}"`).join(", ")} is wider than the column can be; it will wrap inside the word\n`);
  }
  if (sum(floors) >= totalDxa) {
    process.stderr.write(`warning: table with columns ${texts.map((cells) => `"${cells[0]}"`).join(", ")} is too wide for the page; shorten the cells or drop a column\n`);
    return distribute(floors, totalDxa);
  }
  const spare = totalDxa - sum(floors);
  const shared = floors.map((floor, i) => floor + (textLength[i] / sum(textLength)) * spare);
  return distribute(withinCap(shared, cap, textLength), totalDxa);
}

// Moves width above the cap to the columns below it, by weight, until none is above.
function withinCap(widths, cap, weights) {
  let result = widths;
  for (let round = 0; round < widths.length; round += 1) {
    const excess = sum(result.map((width) => Math.max(0, width - cap)));
    const open = result.map((width, i) => (width < cap ? i : -1)).filter((i) => i >= 0);
    if (excess < 1 || open.length === 0) break;
    const openWeight = sum(open.map((i) => weights[i]));
    result = result.map((width, i) => (width >= cap ? cap : width + (excess * weights[i]) / openWeight));
  }
  return result;
}

function distribute(weights, totalDxa) {
  const total = sum(weights);
  const widths = weights.map((w) => Math.floor((w / total) * totalDxa));
  const last = widths.length - 1;
  return widths.map((width, i) => (i === last ? width + totalDxa - sum(widths) : width));
}

function toAlignment(align) {
  if (align === "center") return AlignmentType.CENTER;
  if (align === "right") return AlignmentType.RIGHT;
  return AlignmentType.LEFT;
}
