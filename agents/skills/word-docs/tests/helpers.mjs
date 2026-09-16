// Shared helpers for the word-docs tests: build a Markdown fixture, read the .docx parts, make PNGs.
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { createRequire } from "node:module";

export const SKILL_DIR = join(dirname(fileURLToPath(import.meta.url)), "..");
export const BUILD = join(SKILL_DIR, "scripts", "build-docx.mjs");
// Dependencies live in scripts/node_modules, installed by scripts/setup.sh.
const JSZip = createRequire(join(SKILL_DIR, "scripts", "package.json"))("jszip");

// Temp folders are removed when the test process exits, so a run leaves nothing behind.
const created = [];
process.on("exit", () => created.forEach((dir) => rmSync(dir, { recursive: true, force: true })));

export function tempDir(prefix = "word-docs-test-") {
  const dir = mkdtempSync(join(tmpdir(), prefix));
  created.push(dir);
  return dir;
}

// Writes doc.md plus extra files into a temp folder and runs the builder. Returns stdout/stderr and status.
export function build(markdown, { files = {}, args = [], dir = tempDir() } = {}) {
  writeFileSync(join(dir, "doc.md"), markdown);
  for (const [name, data] of Object.entries(files)) writeFileSync(join(dir, name), data);
  const result = spawnSync(process.execPath, [BUILD, join(dir, "doc.md"), ...args], { encoding: "utf8" });
  return { dir, docx: join(dir, "doc.docx"), status: result.status, stdout: result.stdout, stderr: result.stderr };
}

export async function parts(docxPath) {
  const zip = await JSZip.loadAsync(readFileSync(docxPath));
  const read = async (name) => (zip.file(name) ? zip.file(name).async("string") : "");
  return { document: await read("word/document.xml"), styles: await read("word/styles.xml") };
}

// Each <w:p> with its plain text and the properties the tests look at.
export function paragraphs(documentXml) {
  const found = documentXml.match(/<w:p[ >][\s\S]*?<\/w:p>/g) ?? [];
  return found.map((xml) => ({
    xml,
    text: [...xml.matchAll(/<w:t(?: [^>]*)?>([^<]*)<\/w:t>/g)].map((m) => m[1]).join(""),
    keepNext: /<w:keepNext\/>|<w:keepNext w:val="(?:true|1|on)"\/>/.test(xml),
    style: xml.match(/<w:pStyle w:val="([^"]+)"/)?.[1] ?? "",
  }));
}

export function gridColumns(documentXml) {
  const tables = documentXml.match(/<w:tblGrid>[\s\S]*?<\/w:tblGrid>/g) ?? [];
  return tables.map((grid) => [...grid.matchAll(/<w:gridCol w:w="(\d+)"/g)].map((m) => Number(m[1])));
}

// Image extents in pixels at 96 dpi (EMU / 9525), in document order.
export function imageSizes(documentXml) {
  return [...documentXml.matchAll(/<wp:extent cx="(\d+)" cy="(\d+)"\/>/g)].map((m) => ({
    width: Math.round(Number(m[1]) / 9525),
    height: Math.round(Number(m[2]) / 9525),
  }));
}

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buffer) {
  let c = 0xffffffff;
  for (const byte of buffer) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

// A valid grey PNG of the given pixel size.
export function png(width, height) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.writeUInt8(8, 8); // bit depth
  header.writeUInt8(0, 9); // greyscale
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(width, 200)]);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

export function has(command) {
  return spawnSync("sh", ["-c", `command -v ${command}`], { encoding: "utf8" }).status === 0;
}

export { execFileSync };
