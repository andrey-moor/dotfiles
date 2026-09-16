// PDF export and page layout tests. They need LibreOffice, pdffonts and pdftotext, and skip without them.
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";
import { build, has, png, SKILL_DIR } from "./helpers.mjs";
import { fontPlan } from "../scripts/export-pdf.mjs";

const JSZip = createRequire(join(SKILL_DIR, "scripts", "package.json"))("jszip");
const EXPORT = join(SKILL_DIR, "scripts", "export-pdf.mjs");
const PREVIEW = join(SKILL_DIR, "scripts", "preview.sh");
const hasSoffice = has("soffice") || existsSync("/Applications/LibreOffice.app/Contents/MacOS/soffice");
const skip = hasSoffice && has("pdffonts") && has("pdftotext") ? false : "needs LibreOffice, pdffonts and pdftotext";
const FRONT = "---\ntitle: Export test\nsubtitle: Every style in one file\ndate: 2026-09-15\n---\n\n";

const exportPdf = (docx, ...args) => spawnSync(process.execPath, [EXPORT, docx, ...args], { encoding: "utf8" });
const pages = (pdf) => spawnSync("pdftotext", ["-layout", pdf, "-"], { encoding: "utf8" }).stdout.split("\f");
const bodyLines = (page) => page.split("\n").map((l) => l.trim()).filter((l) => l && !/^Page \d+ of \d+$/.test(l) && !/Andrey Moor/.test(l));

test("the font plan keeps installed Word fonts and substitutes missing ones", () => {
  const linux = fontPlan(["liberationsans", "liberationmono", "dejavusans"], "linux");
  assert.deepEqual(linux, { Aptos: "Liberation Sans", "Aptos Display": "Liberation Sans", Consolas: "Liberation Mono" });
  const withAptos = fontPlan(["aptos", "aptosdisplay", "liberationmono"], "linux");
  assert.deepEqual(withAptos, { Aptos: "Aptos", "Aptos Display": "Aptos Display", Consolas: "Liberation Mono" });
  const mac = fontPlan(["helveticaneue", "menlo"], "darwin");
  assert.deepEqual(mac, { Aptos: "Helvetica Neue", "Aptos Display": "Helvetica Neue", Consolas: "Menlo" });
  assert.throws(() => fontPlan(["dejavuserif"], "linux"), /No installed sans font/);
});

test("export writes the PDF next to the .docx with only the planned fonts", { skip }, () => {
  const markdown = FRONT + [
    "# Heading", "", "Body text with `inline code` and a [link](https://example.com).", "",
    "> A quoted line.", "", "- A bullet", "", "| A | B |", "|---|---|", "| `x` | y |", "",
    "![A figure](shot.png)", "", "```", "code line", "```", "",
  ].join("\n");
  const built = build(markdown, { files: { "shot.png": png(600, 300) } });
  assert.equal(built.status, 0, built.stderr);
  const result = exportPdf(built.docx);
  assert.equal(result.status, 0, result.stderr + result.stdout);
  const pdf = built.docx.replace(/\.docx$/, ".pdf");
  assert.ok(existsSync(pdf));
  assert.doesNotMatch(result.stdout, /Serif|Libertine|Hiragino/i);
});

test("an unplanned font in the document fails the export and names the font", { skip }, async () => {
  const built = build(FRONT + "```\ncode line\n```\n");
  assert.equal(built.status, 0, built.stderr);
  const zip = await JSZip.loadAsync(readFileSync(built.docx));
  const styles = await zip.file("word/styles.xml").async("string");
  zip.file("word/styles.xml", styles.replace(/="Consolas"/g, '="Courier Nonexistent"'));
  writeFileSync(built.docx, await zip.generateAsync({ type: "nodebuffer" }));
  const result = exportPdf(built.docx);
  assert.equal(result.status, 1, result.stdout);
  assert.match(result.stderr, /unexpected fonts/);
});

test("a lead-in never ends a page while its table starts the next", { skip }, () => {
  const sections = [];
  for (let k = 18; k < 32; k += 1) {
    sections.push(`# Section ${k}`, "", ...Array.from({ length: k }, (_, i) => `Filler line ${i + 1} of ${k} keeps this paragraph to one line.\n`));
    sections.push(`LEADIN-${k} the table below lists the files:`, "", "| File | Holds |", "|---|---|", "| `a.md` | first |", "| `b.md` | second |", "", "<!-- pagebreak -->", "");
  }
  const built = build(FRONT + sections.join("\n"));
  assert.equal(built.status, 0, built.stderr);
  assert.equal(exportPdf(built.docx).status, 0);
  const text = pages(built.docx.replace(/\.docx$/, ".pdf"));
  const stranded = text.map(bodyLines).filter((lines) => lines.at(-1)?.startsWith("LEADIN-"));
  assert.deepEqual(stranded.map((lines) => lines.at(-1)), []);
});

test("a heading and intro before a long code block share a page with its first lines", { skip }, () => {
  const code = Array.from({ length: 140 }, (_, i) => `source_${String(i + 1).padStart(3, "0")}: { retries: 3 }`).join("\n");
  const markdown = FRONT + "# Overview\n\nOne short paragraph.\n\n<!-- pagebreak -->\n\n# Appendix\n\nThe complete configuration file:\n\n```yaml\n" + code + "\n```\n";
  const built = build(markdown);
  assert.equal(built.status, 0, built.stderr);
  assert.equal(exportPdf(built.docx).status, 0);
  const appendixPage = pages(built.docx.replace(/\.docx$/, ".pdf")).map(bodyLines).find((lines) => lines.includes("Appendix"));
  assert.ok(appendixPage.some((line) => line.startsWith("source_001")), `appendix page: ${appendixPage.join(" | ")}`);
});

test("preview writes to a temporary folder, not next to the document", { skip: skip || (has("pdftoppm") ? false : "needs pdftoppm") }, () => {
  const built = build(FRONT + "Body.\n");
  assert.equal(built.status, 0, built.stderr);
  const result = spawnSync("bash", [PREVIEW, built.docx], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stderr, /pages are in /);
  assert.deepEqual(readdirSync(built.dir).sort(), ["doc.docx", "doc.md"]);
});
