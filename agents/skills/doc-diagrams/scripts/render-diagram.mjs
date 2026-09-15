#!/usr/bin/env node
// Render a diagram-design HTML file to a PNG at viewBox x scale pixels (and optionally a standalone SVG).
// The PNG has no page background; the SVG's own paper rect (white under the word-office profile) remains.
// Usage: node render-diagram.mjs diagram.html [-o out.png] [--scale 3] [--svg]
// Uses the system Chromium (CHROME_PATH or common locations); no browser download needed.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { chromium } from "playwright-core";

const DEFAULT_SCALE = 3; // print quality; docs embed at ~6.5in wide
const MAX_SCALE = 4;
const ALLOWED_HOSTS = new Set(["fonts.googleapis.com", "fonts.gstatic.com"]);
const CHROMIUM_CANDIDATES = [
  process.env.CHROME_PATH,
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
  "/usr/bin/google-chrome",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
].filter(Boolean);

function parseArgs(argv) {
  const args = { scale: DEFAULT_SCALE, svg: false };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "-o" || arg === "--output") args.output = argv[++i];
    else if (arg === "--scale") args.scale = Number(argv[++i]);
    else if (arg === "--svg") args.svg = true;
    else if (arg.startsWith("-")) throw new Error(`Unknown option: ${arg}`);
    else if (!args.input) args.input = arg;
    else throw new Error(`Unexpected argument: ${arg}`);
  }
  if (!args.input) throw new Error("Usage: render-diagram.mjs diagram.html [-o out.png] [--scale N] [--svg]");
  if (!existsSync(args.input)) throw new Error(`Input not found: ${args.input}`);
  if (!Number.isFinite(args.scale) || args.scale < 1 || args.scale > MAX_SCALE) {
    throw new Error(`--scale must be between 1 and ${MAX_SCALE}`);
  }
  args.output ??= args.input.replace(/\.html?$/i, "") + ".png";
  return args;
}

function findChromium() {
  const found = CHROMIUM_CANDIDATES.find((path) => existsSync(path));
  if (!found) {
    throw new Error(
      `No Chromium found. Set CHROME_PATH or install one of: ${CHROMIUM_CANDIDATES.join(", ")}`,
    );
  }
  return found;
}

// Extract the first <svg> as a standalone file, per diagram-design's export reference:
// XML-escaped font import, rgba() colors converted for strict SVG consumers.
function standaloneSvg(html) {
  const match = html.match(/<svg[\s\S]*?<\/svg>/);
  if (!match) throw new Error("No <svg> element found in the HTML");
  let svg = match[0];
  if (!/xmlns="http:\/\/www\.w3\.org\/2000\/svg"/.test(svg)) {
    svg = svg.replace(/<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
  }
  const fontLink = html.match(/href="(https:\/\/fonts\.googleapis\.com\/css2[^"]*)"/);
  if (fontLink) {
    const style = `<style>@import url('${fontLink[1].replace(/&/g, "&amp;")}');</style>`;
    svg = /<defs>/.test(svg) ? svg.replace(/<defs>/, `<defs>${style}`) : svg.replace(/(<svg[^>]*>)/, `$1<defs>${style}</defs>`);
  }
  svg = svg.replace(
    /(fill|stroke)="rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d*\.?\d+)\s*\)"/g,
    (_, attr, r, g, b, a) =>
      `${attr}="#${[r, g, b].map((n) => Number(n).toString(16).padStart(2, "0")).join("")}" ${attr}-opacity="${a}"`,
  );
  svg = svg.replace(/(fill|stroke)="transparent"/g, '$1="none"');
  return `<?xml version="1.0" encoding="UTF-8"?>\n${svg}`;
}

async function renderPng(inputPath, outputPath, scale) {
  // Sandbox stays on. Diagram HTML may come from anyone, so only font hosts may be fetched.
  const browser = await chromium.launch({ executablePath: findChromium() });
  try {
    const page = await browser.newPage({ deviceScaleFactor: scale });
    await page.route("**/*", (route) => {
      const url = new URL(route.request().url());
      const isAllowed = url.protocol === "file:" || ALLOWED_HOSTS.has(url.hostname);
      return isAllowed ? route.continue() : route.abort();
    });
    await page.goto(`file://${resolve(inputPath)}?motion=static`);
    await page.waitForLoadState("networkidle");
    await page.evaluate(() => document.fonts.ready);
    const failed = await page.evaluate(() => [...document.fonts].filter((f) => f.status === "error").map((f) => f.family));
    if (failed.length) process.stderr.write(`warning: fonts failed to load: ${[...new Set(failed)].join(", ")}\n`);
    const svg = page.locator("svg").first();
    if ((await svg.count()) === 0) throw new Error("No <svg> element found in the page");
    // Templates stretch the SVG to a 1200px frame; pin it to its viewBox so PNG size = viewBox x scale.
    const viewBox = await svg.evaluate((el) => {
      const parts = (el.getAttribute("viewBox") ?? "").trim().split(/[\s,]+/).map(Number);
      if (parts.length !== 4 || parts.some(Number.isNaN)) return null;
      const [, , width, height] = parts;
      el.style.width = `${width}px`;
      el.style.height = `${height}px`;
      el.style.minWidth = "0";
      el.style.maxWidth = "none";
      return { width, height };
    });
    if (!viewBox) throw new Error("The <svg> has no valid viewBox; diagram-design templates always set one");
    await page.setViewportSize({ width: Math.ceil(viewBox.width) + 80, height: Math.ceil(viewBox.height) + 80 });
    await svg.screenshot({ path: outputPath, omitBackground: true });
    const box = await svg.boundingBox();
    return { width: Math.round(box.width * scale), height: Math.round(box.height * scale) };
  } finally {
    await browser.close();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const size = await renderPng(args.input, args.output, args.scale);
  process.stdout.write(`wrote ${resolve(args.output)} (${size.width}x${size.height} @${args.scale}x)\n`);
  if (args.svg) {
    const svgPath = args.output.replace(/\.png$/i, "") + ".svg";
    writeFileSync(svgPath, standaloneSvg(readFileSync(args.input, "utf8")));
    process.stdout.write(`wrote ${resolve(svgPath)}\n`);
  }
}

main().catch((error) => {
  process.stderr.write(`render-diagram: ${error.message}\n`);
  process.exit(1);
});
