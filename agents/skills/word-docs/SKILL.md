---
name: word-docs
description: "Use when the deliverable is a Word document (.docx): design doc, proposal, report, memo, spec, one-pager, decision doc. Also use when asked to turn Markdown or notes into a Word file with standard Word styles, a header with author and date, page numbers, tables, or figures."
---

# Word Docs

## Overview

Write the document as Markdown with YAML front matter, then build it with `scripts/build-docx.mjs`. The builder applies Word's current default styles (Aptos body, Aptos Display headings, Office theme colors), a running header with author and date, page numbers, numbered figure captions, and file properties. The result opens in Word with the normal Styles gallery, so anyone can restyle it.

**REQUIRED SUB-SKILL:** plain-prose for all body text.
**REQUIRED SUB-SKILL:** doc-diagrams for any figure.

Script paths below are relative to this skill's directory. First use on a machine: `bash scripts/setup.sh`.

## Workflow

1. **Outline first.** Title, one-sentence purpose, section headings, and which sections need a table or figure. Keep the outline in your head or in the file; do not write prose yet.
2. **Write the Markdown** in the working folder, applying plain-prose. Front matter carries title, author, date. Body starts at `# Heading 1`; the document title is not a heading.
3. **Draw figures** with doc-diagrams. Reference the PNG on its own line: `![What the reader should see](figure.png)`. The alt text becomes the caption, prefixed "Figure N."
4. **Build:** `node scripts/build-docx.mjs doc.md` (writes `doc.docx` next to it; `-o` overrides).
5. **Preview and look at every page:** `bash scripts/preview.sh doc.docx` renders page JPEGs. Read them. Check heading hierarchy, table widths, figure size, page breaks, and the header. LibreOffice substitutes another font for Aptos; judge layout, not glyphs.
6. **Deliver the path.** If the user is remote, send the file with SendUserFile.

## Front matter

| Key | Required | Meaning |
|---|---|---|
| `title` | yes | Document title (Title style) and header text |
| `author` | no | Byline and header. Default comes from `scripts/defaults.json` (Andrey Moor) |
| `date` | no | `YYYY-MM-DD`. Default is today. Rendered as "September 14, 2026" |
| `subtitle` | no | Subtitle style under the title |
| `status` | no | Draft, Review, Final. Appears in the byline |
| `toc` | no | `true` adds a Contents section. Word asks to update fields on first open; LibreOffice previews show it empty |
| `page` | no | `letter` (default) or `a4` |
| `header` | no | `running` (default: page 1 has no header, later pages show title, author, date) or `all` (page 1 header shows author and date too) |
| `footer` | no | Left footer text, for example `Company Confidential`. Page numbers are always present |
| `description`, `keywords` | no | File properties only |

## Markdown supported

| Markdown | Word result |
|---|---|
| `#` to `######` | Heading 1 to Heading 6 (built-in styles, appear in the navigation pane and TOC) |
| Paragraphs, `**bold**`, `*italic*`, `` `code` ``, `[link](url)` | Normal text, Strong, Emphasis, Code Char, Hyperlink |
| `-` lists, `1.` lists, nested up to three levels | Word bullets and numbering. Each numbered list restarts at 1 |
| GFM table with header row | Table, 0.5pt grid, bold shaded header, widths proportional to content |
| Fenced code block | Code Block style (Consolas 9.5pt, shaded) |
| `> quote` | Quote style |
| `![caption](file.png)` alone on a line | Centered figure up to 6.5in wide, alt text set, caption "Figure N. caption" |
| `---` | Thin horizontal rule |
| `<!-- pagebreak -->` | Page break |

Images must live in the document's folder or below it; a path outside it is refused. A file name with spaces goes in angle brackets: `![caption](<my figure.png>)`. A link that wraps an image on its own line is treated as the figure.

Not supported: inline images inside a sentence, raw HTML, footnotes, multi-paragraph list items with tables. The builder stops with a clear error on a missing or malformed image, an image outside the folder, or invalid front matter.

## Rules that keep documents standard

- The title comes from front matter. Never write it as `# Title`.
- Do not skip heading levels. `#` then `##`, not `#` then `###`.
- Figures are PNG at 3x (the builder assumes this; pass `--image-scale 1` for screenshots at natural size).
- Numbers that readers compare go in a table, not a paragraph.
- Keep the document short. A decision doc is two to four pages. If the outline has more than eight `#` sections, cut or split.
- To edit an existing .docx, use the document-skills:docx skill. This skill builds new files.

## Verification before delivering

```bash
node scripts/build-docx.mjs doc.md && bash scripts/preview.sh doc.docx
```

Then Read each `preview/page-N.jpg`. Do not report the document as done without looking at the pages.

## Common mistakes

| Mistake | Fix |
|---|---|
| Wrote the title as a heading, so it appears twice | Remove the `# Title` line; front matter owns it |
| Figure too small to read | Diagram used the standard type ramp or too many nodes. Redraw per doc-diagrams: `doc-inline` size, presentation ramp, at most seven nodes |
| Table columns cramped | Shorten cell text or drop a column; six columns is the practical limit at 6.5in |
| Empty Contents section in preview | Expected. Word fills it on open. Set `toc: false` for short docs |
| Author name wrong | Set `author:` in front matter or change `scripts/defaults.json` |

## Reference

`references/word-defaults.md` lists the exact style values (fonts, sizes, colors, spacing) the builder emits and where they came from.
