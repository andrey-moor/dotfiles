import { parse } from "yaml";

const FRONT_MATTER = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?/;
const PAGE_SIZES = new Set(["letter", "a4"]);
const HEADER_MODES = new Set(["running", "all"]);

export function splitFrontMatter(source) {
  const match = source.match(FRONT_MATTER);
  if (!match) return { meta: {}, body: source };
  const meta = parse(match[1]) ?? {};
  if (typeof meta !== "object" || Array.isArray(meta)) {
    throw new Error("Front matter must be a YAML mapping (key: value lines).");
  }
  return { meta, body: source.slice(match[0].length) };
}

const TRUE_WORDS = new Set([true, "true", "yes", "on"]);
const FALSE_WORDS = new Set([false, "false", "no", "off", undefined, null, ""]);

function parseFlag(name, value) {
  const key = typeof value === "string" ? value.trim().toLowerCase() : value;
  if (TRUE_WORDS.has(key)) return true;
  if (FALSE_WORDS.has(key)) return false;
  throw new Error(`Front matter "${name}" must be true or false, got: ${value}`);
}

function parseDate(value) {
  if (value === undefined || value === null || value === "") return new Date();
  if (value instanceof Date) return value;
  const text = String(value).trim();
  const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (iso) return new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    throw new Error(`Front matter "date" is not a date: ${text}. Use YYYY-MM-DD.`);
  }
  return parsed;
}

export function resolveMeta(meta, defaults) {
  const merged = { ...defaults, ...meta };
  if (!merged.title || typeof merged.title !== "string") {
    throw new Error('Front matter needs a "title:" line.');
  }
  if (!merged.author || typeof merged.author !== "string") {
    throw new Error('Front matter needs an "author:" line (or set it in defaults.json).');
  }
  const page = String(merged.page).toLowerCase();
  if (!PAGE_SIZES.has(page)) {
    throw new Error(`Front matter "page" must be one of: ${[...PAGE_SIZES].join(", ")}.`);
  }
  const header = String(merged.header ?? "running").toLowerCase();
  if (!HEADER_MODES.has(header)) {
    throw new Error(`Front matter "header" must be one of: ${[...HEADER_MODES].join(", ")}.`);
  }
  const date = parseDate(merged.date);
  const dateText = new Intl.DateTimeFormat(merged.locale, { dateStyle: "long" }).format(date);
  return {
    title: merged.title.trim(),
    subtitle: merged.subtitle ? String(merged.subtitle).trim() : "",
    author: merged.author.trim(),
    status: merged.status ? String(merged.status).trim() : "",
    footer: merged.footer ? String(merged.footer).trim() : "",
    keywords: merged.keywords ? String(merged.keywords) : "",
    description: merged.description ? String(merged.description) : "",
    toc: parseFlag("toc", merged.toc),
    page,
    header,
    date,
    dateText,
  };
}
