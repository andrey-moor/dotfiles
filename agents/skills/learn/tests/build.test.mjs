// learn builder tests: node --test "tests/*.test.mjs"
import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SKILL = join(dirname(fileURLToPath(import.meta.url)), "..");
const BUILD = join(SKILL, "scripts", "build-study.mjs");
const TEMPLATE = readFileSync(join(SKILL, "templates", "study.md"), "utf8");

function buildStudy(text) {
  const dir = mkdtempSync(join(tmpdir(), "learn-test-"));
  try {
    writeFileSync(join(dir, "study.md"), text);
    return spawnSync(process.execPath, [BUILD, join(dir, "study.md")], { encoding: "utf8" });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test("the template builds without warnings", () => {
  const result = buildStudy(TEMPLATE);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, / 0 warnings\)/);
  assert.equal(result.stderr, "");
});

test("nine steps stop the build", () => {
  const steps = Array.from({ length: 9 }, (_, i) => `## Step ${i + 1}: stage ${i + 1}\n\nThe request moves on.\n`).join("\n");
  const text = TEMPLATE.replace(/# Worked example[\s\S]*?(?=\n# Parts)/, `# Worked example\n\nThe values are illustrative.\n\n${steps}`);
  const result = buildStudy(text);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /9 steps; the limit is 8/);
});

test("a missing required section stops the build", () => {
  const result = buildStudy(TEMPLATE.replace(/\n# Glossary[\s\S]*?(?=\n# |\s*$)/, "\n"));
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /missing required sections: .*Glossary/i);
});

test("SKILL.md calls sibling skills by relative path, not through ~/.claude/skills", () => {
  const skill = readFileSync(join(SKILL, "SKILL.md"), "utf8");
  assert.doesNotMatch(skill, /~\/\.claude\/skills\//);
});
