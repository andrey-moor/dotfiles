import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { splitByHeading, plain, FACT_LABELS, headingNumber } from "./sections.mjs";

export const LIMITS = { maxSteps: 8, maxParts: 7, minQuestions: 6, maxQuestions: 10 };
const EXTERNAL = /^(https?:|mailto:|#)/i;

// Checks the rules the learn skill states. Errors stop the build because the page would be wrong
// (a figure out of step with the text, a lesson too big to hold); warnings are printed.
export function lintStudy(sections, figures, inputPath, walkthroughLabel = "Step") {
  const errors = [];
  const warnings = [];
  const byKey = Object.fromEntries(sections.map((s) => [s.key, s]));

  if (byKey.gist && !plain(byKey.gist.tokens).includes("Remember:")) {
    warnings.push('Gist has no "**Remember:**" line.');
  }
  lintExample(byKey.example, figures, errors, warnings, walkthroughLabel);
  lintParts(byKey.parts, errors, warnings);
  if (byKey.check) {
    const count = splitByHeading(byKey.check.tokens, 2).groups.length;
    if (count < LIMITS.minQuestions || count > LIMITS.maxQuestions) {
      warnings.push(`Check yourself has ${count} questions; aim for ${LIMITS.minQuestions} to ${LIMITS.maxQuestions}.`);
    }
  }
  for (const title of figures.partsWithoutList) {
    warnings.push(`Part "${title}" did not render as a labeled list. Put each bold label at the start of a sentence, outside links and emphasis.`);
  }
  lintLinks(sections, dirname(resolve(inputPath)), warnings);
  return { errors, warnings };
}

function lintExample(example, figures, errors, warnings, label) {
  if (!example) return;
  const { lead, groups } = splitByHeading(example.tokens, 2);
  if (groups.length > LIMITS.maxSteps) {
    errors.push(`Worked example has ${groups.length} steps; the limit is ${LIMITS.maxSteps}. Split the topic into two lessons.`);
  }
  if (!lead.some((token) => token.type !== "space")) {
    warnings.push("Worked example has no lead sentence declaring its illustrative values.");
  }
  groups.forEach((group, index) => {
    if (label.toLowerCase() !== "step" && /^step\s*\d/i.test(group.title)) {
      warnings.push(`Worked example heading "${group.title}" says Step, but walkthrough is ${label}.`);
    }
    if (headingNumber(group.title, label).number !== index + 1) {
      warnings.push(`Worked example heading ${index + 1} reads "${group.title}"; expected "${label} ${index + 1}: ...".`);
    }
  });
  for (const count of figures.stepCounts) {
    if (count !== groups.length) {
      errors.push(`The stepped figure has ${count} steps but the worked example has ${groups.length}. Give the figure one data-step per example step.`);
    }
  }
}

function lintParts(parts, errors, warnings) {
  if (!parts) return;
  const { groups } = splitByHeading(parts.tokens, 2);
  if (groups.length > LIMITS.maxParts) {
    errors.push(`Parts has ${groups.length} parts; the limit is ${LIMITS.maxParts}. Split the topic into two lessons.`);
  }
  for (const group of groups) {
    const leadRaw = splitByHeading(group.tokens, 3).lead.map((token) => token.raw ?? "").join("");
    const missing = FACT_LABELS.filter((label) => !new RegExp(`(\\*\\*|__)${label}:\\1`).test(leadRaw));
    if (missing.length) warnings.push(`Part "${group.title}" is missing the bold label(s): ${missing.map((l) => `**${l}:**`).join(", ")}.`);
  }
}

function lintLinks(sections, baseDir, warnings) {
  const visit = (tokens) => {
    for (const token of tokens ?? []) {
      if (token.type === "link" && /^[a-z][a-z0-9+.-]*:/i.test(token.href) && !/^(https?|mailto):/i.test(token.href)) {
        warnings.push(`Link shown as plain text because its scheme is not http, https, or mailto: ${token.href}`);
      } else if (token.type === "link" && !EXTERNAL.test(token.href)) {
        const path = token.href.split("#")[0];
        let target = path;
        try { target = decodeURI(path); } catch { /* keep the raw path */ }
        if (path && !existsSync(resolve(baseDir, target))) warnings.push(`Link target not found: ${token.href}`);
      }
      visit(token.tokens);
      visit(token.items);
      if (token.type === "table") {
        visit(token.header);
        visit(token.rows?.flat());
      }
    }
  };
  sections.forEach((section) => visit(section.tokens));
}
