import { readFileSync } from "node:fs";
import { extname } from "node:path";

// Pixel dimensions from PNG/JPEG headers. Enough for sizing; no decoder needed.
export function readImage(path) {
  const data = readFileSync(path);
  const type = imageType(path, data);
  const size = type === "png" ? pngSize(data) : jpegSize(data);
  return { data, type, ...size };
}

function imageType(path, data) {
  if (data.length > 8 && data.readUInt32BE(0) === 0x89504e47) return "png";
  if (data.length > 3 && data[0] === 0xff && data[1] === 0xd8) return "jpg";
  throw new Error(`Unsupported image (need PNG or JPEG): ${path} (${extname(path)})`);
}

const PNG_HEADER_LENGTH = 24;

function pngSize(data) {
  if (data.length < PNG_HEADER_LENGTH) throw new Error("Malformed PNG: file is truncated");
  return { width: data.readUInt32BE(16), height: data.readUInt32BE(20) };
}

// Markers with no length field: TEM (01), RSTn (D0-D7), SOI (D8), EOI (D9).
const isStandaloneMarker = (m) => m === 0x01 || (m >= 0xd0 && m <= 0xd9);
const isStartOfFrame = (m) => m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc;

function jpegSize(data) {
  let offset = 2;
  while (offset + 1 < data.length) {
    if (data[offset] !== 0xff) throw new Error("Malformed JPEG: marker expected");
    const marker = data[offset + 1];
    if (marker === 0xff) { offset += 1; continue; } // fill byte
    if (isStandaloneMarker(marker)) { offset += 2; continue; }
    if (offset + 4 > data.length) throw new Error("Malformed JPEG: file is truncated");
    const length = data.readUInt16BE(offset + 2);
    if (isStartOfFrame(marker)) {
      if (offset + 9 > data.length) throw new Error("Malformed JPEG: frame header is truncated");
      return { height: data.readUInt16BE(offset + 5), width: data.readUInt16BE(offset + 7) };
    }
    if (length < 2) throw new Error("Malformed JPEG: bad segment length");
    offset += 2 + length;
  }
  throw new Error("Malformed JPEG: no frame header found");
}
