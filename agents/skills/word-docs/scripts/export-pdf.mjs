#!/usr/bin/env node
// Export a .docx to PDF with LibreOffice, with installed fonts standing in for Word's when Word's are missing.
// Usage: node export-pdf.mjs doc.docx [-o doc.pdf] [--allow-font NAME]...
//
// Aptos, Aptos Display and Consolas are swapped for similar installed fonts in a temporary copy, so the
// PDF is sans serif with a monospace code font instead of LibreOffice's fallback serif. On macOS,
// headless LibreOffice sees only its own fonts, so it also gets a fontconfig file that lists the system
// font folders. The result is checked with pdffonts: any embedded font other than the chosen ones fails
// the export (exit 1, PDF kept) unless allowed with --allow-font.
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, readFileSync, renameSync, copyFileSync, rmSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const JSZip = createRequire(fileURLToPath(import.meta.url))("jszip");
const WORD_FONTS = { body: "Aptos", heading: "Aptos Display", mono: "Consolas" };
const LINUX_SANS = ["Liberation Sans", "Arimo", "DejaVu Sans", "Noto Sans"];
const LINUX_MONO = ["Liberation Mono", "Cousine", "DejaVu Sans Mono", "Noto Sans Mono"];
const MAC_FONT_DIRS = ["/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts", join(homedir(), "Library/Fonts")];
const CONVERT_TIMEOUT_MS = 180_000;

function parseArgs(argv) {
  const args = { allowFonts: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-o" || arg === "--output") args.output = argv[++i];
    else if (arg === "--allow-font") args.allowFonts.push(argv[++i]);
    else if (arg.startsWith("-")) throw new Error(`Unknown option: ${arg}`);
    else if (!args.input) args.input = arg;
    else throw new Error(`Unexpected argument: ${arg}`);
  }
  if (!args.input) throw new Error("Usage: export-pdf.mjs doc.docx [-o doc.pdf] [--allow-font NAME]");
  if (!existsSync(args.input)) throw new Error(`Input not found: ${args.input}`);
  args.output = resolve(args.output ?? args.input.replace(/\.docx$/i, "") + ".pdf");
  return args;
}

function findSoffice() {
  const candidates = ["/Applications/LibreOffice.app/Contents/MacOS/soffice", join(homedir(), "Applications/LibreOffice.app/Contents/MacOS/soffice")];
  const onPath = commandPath("soffice");
  const found = onPath ?? candidates.find((path) => existsSync(path));
  if (!found) throw new Error("LibreOffice (soffice) not found. Install it to export PDFs");
  return found;
}

function commandPath(name) {
  try {
    return execFileSync("sh", ["-c", `command -v ${name}`], { encoding: "utf8" }).trim() || null;
  } catch {
    return null;
  }
}

const normalize = (name) => name.toLowerCase().replace(/[\s_-]/g, "");

// Font families this machine offers: fontconfig on Linux, font file names on macOS.
function installedFamilies() {
  if (process.platform === "darwin") {
    return MAC_FONT_DIRS.filter(existsSync).flatMap((dir) => readdirSync(dir)).map((file) => normalize(file.replace(/\.\w+$/, "")));
  }
  if (!commandPath("fc-list")) throw new Error("fc-list (fontconfig) not found; cannot tell which fonts are installed");
  return execFileSync("fc-list", [":", "family"], { encoding: "utf8" }).split("\n").flatMap((line) => line.split(",")).map(normalize);
}

// Word font -> font LibreOffice will use. A Word font that is installed maps to itself.
export function fontPlan(families = installedFamilies(), platform = process.platform) {
  const has = (name) => families.some((family) => family === normalize(name) || family.startsWith(normalize(name)));
  const pick = (candidates, role) => {
    const found = candidates.find(has);
    if (!found) throw new Error(`No installed ${role} font to stand in for Word's; install one of: ${candidates.join(", ")}`);
    return found;
  };
  if (platform === "darwin") {
    return {
      [WORD_FONTS.body]: has("Aptos") ? WORD_FONTS.body : pick(["Helvetica Neue", "Helvetica"], "sans"),
      [WORD_FONTS.heading]: has("Aptos Display") || has("AptosDisplay") ? WORD_FONTS.heading : pick(["Helvetica Neue", "Helvetica"], "sans"),
      [WORD_FONTS.mono]: has("Consolas") ? WORD_FONTS.mono : pick(["Menlo", "Monaco"], "monospace"),
    };
  }
  if (platform !== "linux") throw new Error(`PDF export supports Linux and macOS, not ${platform}`);
  const sans = has("Aptos") ? null : pick(LINUX_SANS, "sans");
  return {
    [WORD_FONTS.body]: sans ?? WORD_FONTS.body,
    [WORD_FONTS.heading]: has("Aptos Display") ? WORD_FONTS.heading : sans ?? pick(LINUX_SANS, "sans"),
    [WORD_FONTS.mono]: has("Consolas") ? WORD_FONTS.mono : pick(LINUX_MONO, "monospace"),
  };
}

async function withFonts(docxPath, plan, outPath) {
  const zip = await JSZip.loadAsync(readFileSync(docxPath));
  const names = Object.keys(zip.files).filter((name) => name.endsWith(".xml"));
  for (const name of names) {
    const xml = await zip.file(name).async("string");
    const swapped = xml.replace(/="(Aptos Display|Aptos|Consolas)"/g, (match, font) => `="${plan[font]}"`);
    if (swapped !== xml) zip.file(name, swapped);
  }
  writeFileSync(outPath, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

function fontconfigFile(work) {
  const dirs = MAC_FONT_DIRS.filter(existsSync).map((dir) => `<dir>${dir}</dir>`).join("");
  const path = join(work, "fonts.conf");
  writeFileSync(path, `<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n<fontconfig>${dirs}<cachedir>${join(work, "fc-cache")}</cachedir></fontconfig>\n`);
  return path;
}

function embeddedFonts(pdfPath) {
  if (!commandPath("pdffonts")) throw new Error("pdffonts (poppler) not found; cannot check the PDF's fonts");
  const lines = execFileSync("pdffonts", [pdfPath], { encoding: "utf8" }).split("\n").slice(2);
  return [...new Set(lines.map((line) => line.trim().split(/\s+/)[0]).filter(Boolean).map((name) => name.replace(/^[A-Z]{6}\+/, "")))];
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const plan = fontPlan();
  const work = mkdtempSync(join(tmpdir(), "word-docs-pdf-"));
  try {
    const stem = basename(args.input).replace(/\.docx$/i, "");
    const copy = join(work, `${stem}.docx`);
    await withFonts(args.input, plan, copy);
    const env = { ...process.env };
    if (process.platform === "darwin") env.FONTCONFIG_FILE = fontconfigFile(work);
    execFileSync(findSoffice(), [`-env:UserInstallation=${pathToFileURL(join(work, "profile")).href}`, "--headless", "--convert-to", "pdf", "--outdir", work, copy], { env, stdio: "pipe", timeout: CONVERT_TIMEOUT_MS });
    const pdf = join(work, `${stem}.pdf`);
    if (!existsSync(pdf)) throw new Error("LibreOffice did not produce a PDF");
    try {
      renameSync(pdf, args.output);
    } catch {
      copyFileSync(pdf, args.output);
    }
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
  const fonts = embeddedFonts(args.output);
  const allowed = [...new Set(Object.values(plan)), ...args.allowFonts].map(normalize);
  const unexpected = fonts.filter((font) => !allowed.some((family) => normalize(font).startsWith(family)));
  process.stdout.write(`wrote ${args.output}\nfonts: ${fonts.join(", ")}\n`);
  for (const [word, used] of Object.entries(plan)) {
    if (word !== used) process.stdout.write(`note: ${word} is not installed here, so the PDF uses ${used}. Line breaks can differ from Word.\n`);
  }
  if (unexpected.length) {
    process.stderr.write(`export-pdf: unexpected fonts in the PDF: ${unexpected.join(", ")}. Some text did not get the planned font. Find which style it is, or pass --allow-font NAME if it is expected.\n`);
    process.exit(1);
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    process.stderr.write(`export-pdf: ${error.message}\n`);
    process.exit(1);
  });
}
