// Word 2023+ default styles (Office theme: Aptos / Aptos Display).
// Values verified against a styles.xml produced by current Microsoft 365 Word.
// Sizes are half-points, spacing is twentieths of a point (DXA), line 278 = 1.15.
import { LineRuleType, UnderlineType } from "docx";

export const FONT_BODY = "Aptos";
export const FONT_HEADING = "Aptos Display";
export const FONT_MONO = "Consolas";

// Office 2023 theme colors
export const COLOR = {
  text1: "000000",
  text2: "0E2841",
  heading: "0F4761", // accent1 darker 25%
  accent1: "156082",
  accent2: "E97132",
  muted: "595959", // text1 lighter 35%
  quote: "404040",
  hyperlink: "467886",
  light2: "E8E8E8",
  codeBackground: "F2F2F2",
  border: "BFBFBF",
};

const heading = (font, size, spacing, level, extraRun = {}) => ({
  run: { font, size, color: COLOR.heading, ...extraRun },
  paragraph: {
    spacing,
    keepNext: true,
    keepLines: true,
    outlineLevel: level,
  },
});

export const defaultStyles = {
  document: {
    run: { font: FONT_BODY, size: 24 },
    paragraph: {
      spacing: { after: 160, line: 278, lineRule: LineRuleType.AUTO },
    },
  },
  title: {
    run: { font: FONT_HEADING, size: 56, characterSpacing: -10, kern: 28 },
    paragraph: {
      spacing: { after: 80, line: 240, lineRule: LineRuleType.AUTO },
      contextualSpacing: true,
    },
  },
  heading1: heading(FONT_HEADING, 40, { before: 360, after: 80 }, 0),
  heading2: heading(FONT_HEADING, 32, { before: 160, after: 80 }, 1),
  heading3: heading(FONT_BODY, 28, { before: 160, after: 80 }, 2),
  heading4: heading(FONT_BODY, 24, { before: 80, after: 40 }, 3, { italics: true }),
  heading5: heading(FONT_BODY, 24, { before: 80, after: 40 }, 4),
  heading6: {
    run: { font: FONT_BODY, size: 24, italics: true, color: COLOR.muted },
    paragraph: { spacing: { before: 40, after: 0 }, keepNext: true, keepLines: true, outlineLevel: 5 },
  },
  listParagraph: {
    paragraph: { indent: { left: 720 }, contextualSpacing: true },
  },
  hyperlink: {
    run: { color: COLOR.hyperlink, underline: { type: UnderlineType.SINGLE } },
  },
};

export const paragraphStyles = [
  {
    id: "Subtitle",
    name: "Subtitle",
    basedOn: "Normal",
    next: "Normal",
    quickFormat: true,
    run: { size: 28, color: COLOR.muted, characterSpacing: 15 },
    paragraph: { spacing: { after: 160 } },
  },
  {
    id: "Quote",
    name: "Quote",
    basedOn: "Normal",
    next: "Normal",
    quickFormat: true,
    run: { italics: true, color: COLOR.quote },
    paragraph: { spacing: { before: 160 }, indent: { left: 720, right: 720 } },
  },
  {
    id: "Caption",
    name: "Caption",
    basedOn: "Normal",
    next: "Normal",
    run: { size: 18, italics: true, color: COLOR.text2 },
    paragraph: { spacing: { after: 200 } },
  },
  {
    id: "TOCHeading",
    name: "TOC Heading",
    basedOn: "Heading1",
    next: "Normal",
    paragraph: { outlineLevel: 9 },
  },
  {
    id: "CodeBlock",
    name: "Code Block",
    basedOn: "Normal",
    next: "Normal",
    run: { font: FONT_MONO, size: 19 },
    paragraph: {
      spacing: { before: 0, after: 0, line: 240, lineRule: LineRuleType.AUTO },
      shading: { type: "clear", fill: COLOR.codeBackground },
      indent: { left: 240, right: 240 },
    },
  },
  {
    id: "TableSpacer",
    name: "Table Spacer",
    basedOn: "Normal",
    run: { size: 8 },
    paragraph: { spacing: { before: 0, after: 80, line: 240, lineRule: LineRuleType.AUTO } },
  },
  {
    id: "HeaderText",
    name: "Header Text",
    basedOn: "Normal",
    run: { size: 18, color: COLOR.muted },
    paragraph: { spacing: { after: 0, line: 240, lineRule: LineRuleType.AUTO } },
  },
];

export const characterStyles = [
  {
    id: "CodeChar",
    name: "Code Char",
    basedOn: "DefaultParagraphFont",
    run: { font: FONT_MONO, size: 20, shading: { type: "clear", fill: COLOR.codeBackground } },
  },
];
