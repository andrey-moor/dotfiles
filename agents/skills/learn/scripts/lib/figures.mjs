import { readFileSync } from "node:fs";

// Embed a diagram-design HTML file (static or step-mode) inside the study page.
// The diagram's CSS is scoped with CSS nesting; its :root variables move onto the wrapper.
// The plugin's controller script is returned separately so the page includes it once.
export function embedDiagram(path) {
  const html = readFileSync(path, "utf8");
  const hasRoot = /<main\b[^>]*data-motion-root/.test(html);
  let markup;
  if (hasRoot) {
    const root = html.match(/<main\b[^>]*data-motion-root[\s\S]*?<\/main>/);
    if (!root) throw new Error(`Diagram ${path} opens <main data-motion-root> but never closes </main>`);
    if ((html.match(/<main\b[^>]*data-motion-root/g) ?? []).length > 1) {
      process.stderr.write(`warning: ${path} has more than one motion root; only the first is embedded\n`);
    }
    markup = root[0];
  } else {
    const svg = outerSvg(html);
    if (!svg) throw new Error(`No diagram found in ${path} (expected <main data-motion-root> or a complete <svg>)`);
    markup = html.slice(svg.start, svg.end);
  }
  const svg = outerSvg(markup);
  if (!svg) throw new Error(`Diagram ${path} has no complete <svg> element`);
  markup = `${markup.slice(0, svg.start)}<div class="svg-scroll">${markup.slice(svg.start, svg.end)}</div>${markup.slice(svg.end)}`
    .replace(/^<main/, "<div")
    .replace(/<\/main>$/, "</div>")
    .replace(/<h1\b([^>]*)>/g, '<p class="figure-title"$1>')
    .replace(/<\/h1>/g, "</p>");
  const { scoped, hoisted } = scopeCss([...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]).join("\n"));
  const controller = extractController(html, path);
  const fontLink = html.match(/<link[^>]*fonts\.googleapis\.com[^>]*>/)?.[0] ?? "";
  const isStepped = /data-motion-mode="step"/.test(markup);
  const stepCount = Number(markup.match(/data-step-count="(\d+)"/)?.[1] ?? 0);
  return { markup: `<div class="diagram-embed">${markup}</div>`, css: `${hoisted}\n.diagram-embed { ${scoped} }`, controller, fontLink, isStepped, stepCount };
}

// The first <svg> element including any nested <svg> icons, found by counting open and close tags.
function outerSvg(text) {
  const start = text.search(/<svg\b/i);
  if (start < 0) return null;
  const tag = /<svg\b[^>]*?(\/?)>|<\/svg\s*>/gi;
  tag.lastIndex = start;
  let depth = 0;
  for (let match = tag.exec(text); match; match = tag.exec(text)) {
    if (match[0].startsWith("</")) depth -= 1;
    else if (match[1] !== "/") depth += 1;
    if (depth === 0) return { start, end: match.index + match[0].length };
  }
  return null;
}

// CSS nesting cannot hold @keyframes or @font-face; they are hoisted to the top level.
// :root variables move onto the wrapper so the nested rules still resolve them.
function scopeCss(css) {
  const hoisted = [];
  const scoped = css.replace(/@(keyframes|font-face)[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}/g, (block) => {
    hoisted.push(block);
    return "";
  });
  return { scoped: scoped.replace(/:root\s*\{/g, "& {"), hoisted: hoisted.join("\n") };
}

// The controller's own source may contain the text "</script>"; extend to the first closing tag
// that leaves the script syntactically complete.
function extractController(html, path) {
  const start = html.search(/<script[^>]*data-diagram-controls[^>]*>/);
  if (start < 0) return "";
  const openEnd = html.indexOf(">", start) + 1;
  let from = openEnd;
  while (true) {
    const close = html.indexOf("</script>", from);
    if (close < 0) throw new Error(`Diagram ${path}: controller <script> is never closed`);
    const body = html.slice(openEnd, close);
    try {
      new Function(body); // parse only; nothing runs
      return html.slice(start, close + "</script>".length);
    } catch {
      from = close + 1;
    }
  }
}
