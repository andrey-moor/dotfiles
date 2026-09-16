// Builder tests: node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { build, parts, paragraphs, gridColumns, imageSizes, png, SKILL_DIR } from "./helpers.mjs";
import { join } from "node:path";
import { cpSync, readFileSync } from "node:fs";

const FRONT = "---\ntitle: Test document\ndate: 2026-09-15\n---\n\n";

async function built(markdown, options) {
  const result = build(FRONT + markdown, options);
  assert.equal(result.status, 0, `build failed: ${result.stderr}`);
  const { document, styles } = await parts(result.docx);
  return { ...result, document, styles, paras: paragraphs(document) };
}

const byText = (paras, needle) => paras.find((p) => p.text.includes(needle));

test("the shipped example builds", async () => {
  const result = build(readFileSync(join(SKILL_DIR, "templates", "example.md"), "utf8"));
  assert.equal(result.status, 0, result.stderr);
  const { document } = await parts(result.docx);
  assert.match(document, /Reconciliation Pipeline Design/);
});

test("headings keep with the next paragraph through their style", async () => {
  const { styles } = await built("# Heading\n\nBody.\n");
  const heading1 = styles.match(/<w:style [^>]*w:styleId="Heading1"[\s\S]*?<\/w:style>/)[0];
  assert.match(heading1, /<w:keepNext\/>/);
});

test("a code block of 40 lines or fewer stays together", async () => {
  const lines = Array.from({ length: 40 }, (_, i) => `line ${i + 1}`).join("\n");
  const { paras } = await built("Intro.\n\n```\n" + lines + "\n```\n");
  const code = paras.filter((p) => p.style === "CodeBlock");
  assert.equal(code.length, 40);
  assert.deepEqual(code.map((p) => p.keepNext), [...Array(39).fill(true), false]);
});

test("a code block over 40 lines keeps only its first and last two lines together", async () => {
  const lines = Array.from({ length: 140 }, (_, i) => `line ${i + 1}`).join("\n");
  const { paras } = await built("Intro.\n\n```\n" + lines + "\n```\n");
  const code = paras.filter((p) => p.style === "CodeBlock");
  assert.equal(code.length, 140);
  const kept = code.flatMap((p, i) => (p.keepNext ? [i] : []));
  assert.deepEqual(kept, [0, 138]);
});

test("a lead-in ending with a colon keeps with the table, code, list or figure after it", async () => {
  const markdown = [
    "The table looks like this:", "", "| A | B |", "|---|---|", "| 1 | 2 |", "",
    "Run this command:", "", "```", "export --all", "```", "",
    "The steps are:", "", "1. Open the app.", "2. Close it.", "",
    "The page looks like this:", "", "![The page](shot.png)", "",
    "Note this:", "", "A plain paragraph follows.", "",
    "No colon here", "", "| C | D |", "|---|---|", "| 3 | 4 |", "",
  ].join("\n");
  const { paras } = await built(markdown, { files: { "shot.png": png(300, 200) } });
  for (const lead of ["The table looks like this:", "Run this command:", "The steps are:", "The page looks like this:"]) {
    assert.equal(byText(paras, lead).keepNext, true, `${lead} should keep with next`);
  }
  assert.equal(byText(paras, "Note this:").keepNext, false);
  assert.equal(byText(paras, "No colon here").keepNext, false);
});

test("images use the global scale unless the title sets scale or width", async () => {
  const markdown = [
    "![Diagram at the default scale](diagram.png)", "",
    "![Screenshot at 1x](shot1.png \"scale=1\")", "",
    "![Screenshot at 2x](shot2.png \"scale=2\")", "",
    "![Fixed width](shot1.png \"width=3in\")", "",
  ].join("\n");
  const files = { "diagram.png": png(1500, 600), "shot1.png": png(500, 300), "shot2.png": png(1000, 600) };
  const { document } = await built(markdown, { files });
  assert.deepEqual(imageSizes(document), [
    { width: 500, height: 200 },
    { width: 500, height: 300 },
    { width: 500, height: 300 },
    { width: 288, height: 173 },
  ]);
});

test("image title text that is not an attribute is still the caption fallback", async () => {
  const { paras } = await built("![](shot.png \"Fallback caption\")\n", { files: { "shot.png": png(100, 50) } });
  assert.ok(byText(paras, "Figure 1. Fallback caption"));
});

test("an unknown image attribute or a bad value stops the build", () => {
  const files = { "shot.png": png(100, 50) };
  const unknown = build(FRONT + "![Shot](shot.png \"scale=2 zoom=3\")\n", { files });
  assert.notEqual(unknown.status, 0);
  assert.match(unknown.stderr, /zoom/);
  const bad = build(FRONT + "![Shot](shot.png \"scale=0\")\n", { files });
  assert.notEqual(bad.status, 0);
  assert.match(bad.stderr, /scale/);
});

test("images never exceed the text width of the page size", async () => {
  const letter = await built("![Wide](wide.png \"scale=1\")\n", { files: { "wide.png": png(2000, 400) } });
  assert.equal(imageSizes(letter.document)[0].width, 624);
  const a4 = build("---\ntitle: A4\npage: a4\n---\n\n![Wide](wide.png \"scale=1\")\n", { files: { "wide.png": png(2000, 400) } });
  assert.equal(a4.status, 0, a4.stderr);
  const { document } = await parts(a4.docx);
  assert.equal(imageSizes(document)[0].width, 602);
});

test("a tall image is scaled to fit the page height", async () => {
  const { document } = await built("![Tall](tall.png \"scale=1\")\n", { files: { "tall.png": png(400, 3000) } });
  const size = imageSizes(document)[0];
  assert.ok(size.height <= 768, `height ${size.height} should fit below 8in`);
  assert.ok(Math.abs(size.width / size.height - 400 / 3000) < 0.01);
});

test("no column of a three-column table takes more than 45 percent", async () => {
  const code = "`state_<run time>_email<E>_cal<C>_meet<M>.md`";
  const markdown = [
    "| Name | File title | What it holds |", "|---|---|---|",
    `| State | ${code} ${code} | The state snapshot written at the end of each run. |`,
    `| Manifest | ${code} | The list of files the run wrote, with a checksum for each one. |`,
  ].join("\n");
  const { document } = await built(markdown + "\n");
  const [columns] = gridColumns(document);
  const total = columns.reduce((a, b) => a + b, 0);
  assert.equal(total, 9360);
  for (const width of columns) assert.ok(width <= 0.45 * total + 1, `column ${width} of ${total}`);
});

test("link targets do not count toward column width, and no column is starved", async () => {
  const markdown = [
    "| Source | What it covers |", "|---|---|",
    "| [Plugin evals guide](https://code.claude.com/docs/en/plugin-evals#compare-against-a-no-plugin-baseline-and-read-the-results-table) | How the no-plugin baseline is scored |",
    "| [Skills reference](https://code.claude.com/docs/en/skills#evaluate-and-iterate-on-a-skill-with-a-baseline-comparison) | When a skill triggers and how to test it |",
  ].join("\n");
  const { document } = await built(markdown + "\n");
  const [[first, second]] = gridColumns(document);
  assert.ok(first < second, `link column ${first} should be narrower than prose column ${second}`);
  assert.ok(second >= 0.15 * 9360);
});

test("inline code is 11 point, close to the 12 point body text", async () => {
  const { styles } = await built("Use `export` now.\n");
  const codeChar = styles.match(/<w:style [^>]*w:styleId="CodeChar"[\s\S]*?<\/w:style>/)[0];
  assert.match(codeChar, /<w:sz w:val="22"\/>/);
});

test("styles that LibreOffice also defines name their font explicitly", async () => {
  const { styles } = await built("Body.\n");
  for (const id of ["Subtitle", "Quote", "Caption", "TableSpacer", "HeaderText"]) {
    const style = styles.match(new RegExp(`<w:style [^>]*w:styleId="${id}"[\\s\\S]*?</w:style>`))?.[0];
    assert.ok(style, `${id} style exists`);
    assert.match(style, /<w:rFonts [^>]*w:ascii="Aptos"/, `${id} names Aptos`);
  }
});

test("a four-backtick fence keeps an inner three-backtick fence as code", async () => {
  const { paras } = await built("````markdown\n```bash\necho hi\n```\n````\n");
  const code = paras.filter((p) => p.style === "CodeBlock").map((p) => p.text);
  assert.deepEqual(code, ["```bash", "echo hi", "```"]);
});

test("a caption fallback with key=value words is caption text when no attribute is set", async () => {
  const { paras } = await built('![](shot.png "Diagram of y=mx+b for the model")\n', { files: { "shot.png": png(100, 50) } });
  assert.ok(byText(paras, "Figure 1. Diagram of y=mx+b for the model"));
});

test("scale and caption words can share a title", async () => {
  const { document, paras } = await built('![](shot.png "scale=2 Diagram of y=mx+b")\n', { files: { "shot.png": png(400, 200) } });
  assert.deepEqual(imageSizes(document), [{ width: 200, height: 100 }]);
  assert.ok(byText(paras, "Figure 1. Diagram of y=mx+b"));
});
