import { ExternalHyperlink, TextRun } from "docx";

// marked inline tokens -> docx runs. Formatting flags accumulate down the tree.
export function inlineRuns(tokens, format = {}) {
  return (tokens ?? []).flatMap((token) => inlineRun(token, format));
}

function inlineRun(token, format) {
  switch (token.type) {
    case "text":
    case "escape":
      return token.tokens ? inlineRuns(token.tokens, format) : [textRun(token.text, format)];
    case "strong":
      return inlineRuns(token.tokens, { ...format, bold: true });
    case "em":
      return inlineRuns(token.tokens, { ...format, italics: true });
    case "del":
      return inlineRuns(token.tokens, { ...format, strike: true });
    case "codespan":
      return [new TextRun({ text: decodeEntities(token.text), style: "CodeChar", ...format })];
    case "br":
      return [new TextRun({ break: 1 })];
    case "link":
      return [
        new ExternalHyperlink({
          link: token.href,
          children: inlineRuns(token.tokens, { ...format, style: "Hyperlink" }),
        }),
      ];
    case "image":
      throw new Error(`Inline image "${token.href}" is not supported. Put images on their own line.`);
    case "html":
      return [textRun(token.text, format)];
    default:
      process.stderr.write(`warning: unsupported inline token "${token.type}" rendered as text\n`);
      return [textRun(token.raw ?? "", format)];
  }
}

const STRAY_IMAGE = /!\[[^\]]*\]\(/;

function textRun(text, format) {
  if (STRAY_IMAGE.test(text)) {
    throw new Error(
      `Image syntax was not parsed: ${text.trim().slice(0, 60)}. Wrap a path with spaces in angle brackets: ![caption](<my file.png>)`,
    );
  }
  return new TextRun({ text: decodeEntities(text), ...format });
}

const ENTITIES = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'" };

export function decodeEntities(text) {
  return text.replace(/&(amp|lt|gt|quot|#39);/g, (match) => ENTITIES[match]);
}
