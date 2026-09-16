import { relative, resolve, isAbsolute } from "node:path";
import { existsSync } from "node:fs";
import { AlignmentType, ImageRun, Paragraph, TextRun } from "docx";
import { decodeEntities } from "./inline.mjs";
import { readImage } from "./images.mjs";

const PX_PER_INCH = 96;
const DXA_PER_INCH = 1440;
const CAPTION_ALLOWANCE_PX = PX_PER_INCH; // room under a full-height figure for its caption
const ATTRIBUTE = /^([a-z]+)=(.*)$/;

// A paragraph that is exactly one image, or one link wrapping one image, is a figure.
export function soleImage(inline) {
  if (inline.length !== 1) return null;
  const [only] = inline;
  if (only.type === "image") return only;
  if (only.type === "link" && only.tokens?.length === 1 && only.tokens[0].type === "image") return only.tokens[0];
  return null;
}

// The image title holds optional attributes, scale=N and width=Nin, plus any other words as a caption fallback.
// A title made only of key=value words is an attribute list, so an unknown key there is an error.
// In a title with other words, key=value text such as y=mx+b is caption text.
export function imageOptions(title, href) {
  const options = { scale: undefined, widthPx: undefined, caption: [] };
  const words = (title ?? "").split(/\s+/).filter(Boolean);
  const attributeList = words.length > 0 && words.every((word) => ATTRIBUTE.test(word));
  for (const word of words) {
    const attribute = word.match(ATTRIBUTE);
    const known = attribute && ["scale", "width"].includes(attribute[1]);
    if (!known && !(attribute && attributeList)) {
      options.caption.push(word);
      continue;
    }
    const [, key, value] = attribute;
    if (key === "scale") {
      const scale = Number(value);
      if (!Number.isFinite(scale) || scale <= 0) throw new Error(`Image ${href}: scale must be a positive number, got "${value}"`);
      options.scale = scale;
    } else if (key === "width") {
      const inches = value.match(/^(\d+(?:\.\d+)?)in$/);
      if (!inches || Number(inches[1]) <= 0) throw new Error(`Image ${href}: width must be inches such as width=4in, got "${value}"`);
      options.widthPx = Number(inches[1]) * PX_PER_INCH;
    } else {
      throw new Error(`Image ${href}: unknown attribute "${key}" in the title. Use scale=N or width=Nin`);
    }
  }
  return { ...options, caption: options.caption.join(" ") };
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

// Display size in pixels: the file's pixels divided by its scale, or the width it asks for,
// shrunk to fit the text width and a page's text height.
export function displaySize(image, options, ctx) {
  const wanted = options.widthPx ?? image.width / (options.scale ?? ctx.imageScale);
  const maxWidth = (ctx.textWidthDxa / DXA_PER_INCH) * PX_PER_INCH;
  const maxHeight = (ctx.textHeightDxa / DXA_PER_INCH) * PX_PER_INCH - CAPTION_ALLOWANCE_PX;
  const height = (wanted * image.height) / image.width;
  const fit = Math.min(1, maxWidth / wanted, maxHeight / height);
  return { width: Math.round(wanted * fit), height: Math.round(height * fit) };
}

export function figure(imageToken, ctx) {
  const path = imagePath(imageToken.href, ctx);
  const image = readImage(path);
  const options = imageOptions(imageToken.title, imageToken.href);
  const size = displaySize(image, options, ctx);
  ctx.counters.figure += 1;
  const caption = decodeEntities(imageToken.text || options.caption || "");
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
          transformation: size,
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

