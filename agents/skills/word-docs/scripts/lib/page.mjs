import {
  AlignmentType,
  Footer,
  Header,
  PageNumber,
  Paragraph,
  TabStopType,
  TextRun,
} from "docx";

const INCH = 1440;
export const PAGE_SIZES = {
  letter: { width: 12240, height: 15840 },
  a4: { width: 11906, height: 16838 },
};
const MARGIN = INCH;
const HEADER_MARGIN = INCH / 2;

export function textWidthDxa(page) {
  return PAGE_SIZES[page].width - 2 * MARGIN;
}

export function textHeightDxa(page) {
  return PAGE_SIZES[page].height - 2 * MARGIN;
}

export function sectionProperties(meta) {
  return {
    titlePage: true,
    page: {
      size: PAGE_SIZES[meta.page],
      margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN, header: HEADER_MARGIN, footer: HEADER_MARGIN },
    },
  };
}

// Word convention: the running header carries the document title on the left and
// author + date on the right. Page 1 already shows both in the title block, so its
// header is blank unless front matter sets `header: all`.
export function headers(meta) {
  const rightText = `${meta.author}  |  ${meta.dateText}`;
  const running = new Header({ children: [tabbedLine(meta.title, rightText, meta)] });
  const firstPage = meta.header === "all" ? new Header({ children: [tabbedLine("", rightText, meta)] }) : new Header({ children: [] });
  return { first: firstPage, default: running };
}

export function footers(meta) {
  const footer = new Footer({ children: [pageNumberLine(meta)] });
  return { first: footer, default: footer };
}

function tabbedLine(left, right, meta) {
  return new Paragraph({
    style: "HeaderText",
    tabStops: [{ type: TabStopType.RIGHT, position: textWidthDxa(meta.page) }],
    children: [new TextRun({ text: left }), new TextRun({ text: `\t${right}` })],
  });
}

function pageNumberLine(meta) {
  return new Paragraph({
    style: "HeaderText",
    alignment: meta.footer ? AlignmentType.LEFT : AlignmentType.CENTER,
    tabStops: [{ type: TabStopType.RIGHT, position: textWidthDxa(meta.page) }],
    children: [
      new TextRun({ text: meta.footer ? `${meta.footer}\t` : "" }),
      new TextRun({ text: "Page " }),
      new TextRun({ children: [PageNumber.CURRENT] }),
      new TextRun({ text: " of " }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES] }),
    ],
  });
}
