---
name: word-docs
description: "Use when the deliverable is a Word document (.docx): design doc, proposal, report, memo, spec, one-pager, decision doc. Also use when asked to turn Markdown or notes into a Word file with standard Word styles, a header with author and date, page numbers, tables, or figures."
---

# Word Docs

## Overview

Write the document as Markdown with YAML front matter, then build it with `scripts/build-docx.mjs`. The builder applies Word's current default styles: Aptos body, Aptos Display headings, and Office theme colors. The builder also adds a running header with author and date, page numbers, numbered figure captions, and file properties. The result opens in Word with the normal Styles gallery, so anyone can restyle it. `scripts/export-pdf.mjs` turns the .docx into a PDF when one is needed.

**REQUIRED SUB-SKILL:** plain-prose for all body text.
**REQUIRED SUB-SKILL:** doc-diagrams for any figure.

Script paths below are relative to this skill's directory. First use on a machine: `bash scripts/setup.sh`.

## Workflow

1. **Name the reader, then pick the outline.** Decide whether the reader is your manager, your own team, or another team. Then take the matching outline from `references/outlines.md`: design doc, decision doc, status update, or procedural guide. The person who asked for the document is not always its reader.
2. **Write the Markdown in `build/`** inside the working folder, applying plain-prose. Front matter carries title, author, and date. The body starts at `# Heading 1`, because the document title is not a heading. Figures and screenshots go in `build/` too, next to the source.
3. **Draw figures** with doc-diagrams. Reference the PNG on its own line: `![What the reader should see](figure.png)`. The alt text becomes the caption, prefixed "Figure N."
4. **Build to the top of the folder:** `node scripts/build-docx.mjs build/doc.md -o doc.docx`. Only the .docx sits at the top, next to `build/`.
5. **Preview and look at every page:** `bash scripts/preview.sh doc.docx` writes page images to a new temporary folder and prints their paths. Read every page. Check heading hierarchy, table widths, figure size, page breaks, and the header.
6. **Export a PDF when one is asked for:** `node scripts/export-pdf.mjs doc.docx` writes `doc.pdf` next to the .docx.
7. **Deliver the path.** If the user is remote, send the file with SendUserFile.

## Front matter

| Key | Required | Meaning |
|---|---|---|
| `title` | yes | Document title in the Title style, and header text |
| `author` | no | Byline and header. The default comes from `scripts/defaults.json` |
| `date` | no | `YYYY-MM-DD`. Default is today. Rendered as "September 14, 2026" |
| `subtitle` | no | Subtitle style under the title |
| `status` | no | Draft, Review, or Final. Appears in the byline |
| `toc` | no | `true` adds a Contents section. Word asks to update fields on first open. LibreOffice previews show it empty |
| `page` | no | `letter`, the default, or `a4` |
| `header` | no | `running`, the default: page 1 has no header, and later pages show title, author, and date. `all` puts author and date in the page 1 header too |
| `footer` | no | Left footer text, for example `Company Confidential`. Page numbers are always present |
| `description`, `keywords` | no | File properties only |

## Markdown supported

| Markdown | Word result |
|---|---|
| `#` to `######` | Heading 1 to Heading 6, the built-in styles that appear in the navigation pane and the table of contents |
| Paragraphs, `**bold**`, `*italic*`, `` `code` ``, `[link](url)` | Normal text, Strong, Emphasis, Code Char, Hyperlink |
| `-` lists and `1.` lists, nested up to three levels | Word bullets and numbering. Each numbered list restarts at 1 |
| GFM table with a header row | Table with a 0.5pt grid and a bold shaded header. Widths follow the text a reader sees, so link targets do not count. No column drops below 15% of the width, and with three or more columns none passes 45% |
| Fenced code block | Code Block style, Consolas 9.5pt, shaded |
| A four-backtick fence | A code block whose content contains a three-backtick fence |
| `> quote` | Quote style |
| `![caption](diagram.png)` alone on a line | Centered figure with alt text and the caption "Figure N. caption". The file's pixels are divided by 3, the scale diagrams render at |
| `![caption](shot.png "scale=1")` | A screenshot at native size. Use `"scale=2"` for one taken on a 2x display |
| `![caption](shot.png "width=4in")` | A figure 4 inches wide. Use it to shrink a figure that leaves a gap before it |
| `---` | Thin horizontal rule |
| `<!-- pagebreak -->` | Page break |

Every figure fits the text width and the page height. Images must live in the source's folder or below it, and a path outside it is refused. A file name with spaces goes in angle brackets: `![caption](<my figure.png>)`. A link that wraps an image on its own line is treated as the figure.

Not supported: inline images inside a sentence, raw HTML, footnotes, multi-paragraph list items with tables. The builder stops with a clear error on a bad image, an unknown image attribute, or invalid front matter. A bad image is missing, malformed, or outside the folder.

## How pages break

- Headings keep with the paragraph after them.
- A paragraph that ends with a colon keeps with the table, code block, list, or figure after it.
- A code block of 40 lines or fewer stays on one page. A longer block breaks across pages and keeps only its first two and last two lines together.
- Table rows do not split across pages.
- A figure taller than the space left on a page moves to the next page and leaves a gap. Shrink it with `"width=..."` or move a paragraph after it.

## PDF export

`node scripts/export-pdf.mjs doc.docx [-o out.pdf]` converts with LibreOffice. When Aptos or Consolas is not installed, a temporary copy uses a similar installed font. That is Helvetica Neue and Menlo on macOS, and Liberation Sans and Liberation Mono on Linux. On macOS the script also gives LibreOffice a fontconfig file that lists the system font folders, because headless LibreOffice does not see them otherwise.

The script prints the fonts embedded in the PDF and fails when any other font appears, which means some text fell back to a default. Tell the user when the PDF uses a substitute font, because line breaks can differ from Word. Never run `soffice --convert-to pdf` directly: the fonts come out wrong.

## Rules that keep documents standard

- The title comes from front matter. Never write it as `# Title`.
- Do not skip heading levels. `#` then `##`, not `#` then `###`.
- Diagrams are PNG at 3x. Screenshots get `"scale=1"` or `"scale=2"` in the title, or `--image-scale` sets a different default for the whole document.
- Numbers that readers compare go in a table, not a paragraph.
- Length follows the outline in `references/outlines.md`. A document longer than about five pages gets a terms table, per plain-prose rule 7.
- To edit an existing .docx, use the document-skills:docx skill. This skill builds new files.

## Verification before delivering

```bash
node scripts/build-docx.mjs build/doc.md -o doc.docx && bash scripts/preview.sh doc.docx
```

Then Read each page image that `preview.sh` lists. Do not report the document as done without looking at the pages. For a PDF, run `export-pdf.mjs` and confirm it exits cleanly.

When the document was written from research notes, check it against them before delivering: `python3 ../research-notes/scripts/check-notes.py notes/ --deliverable build/doc.md`. Every number and code name in the document must appear in a note. Add the missing claim with its citation, or take it out of the document.

## Common mistakes

| Mistake | Fix |
|---|---|
| Wrote the title as a heading, so it appears twice | Remove the `# Title` line. Front matter owns it |
| A document framed as asks for the person who requested it | Name the reader first. A design doc for the team explains the design to the team |
| Markdown source and figures next to the .docx | Move them into `build/`, then build from the working folder with `-o doc.docx` |
| Screenshot text too small to read | Add `"scale=1"` or `"scale=2"` to the image title |
| Figure too small to read | Diagram used the standard type ramp or too many nodes. Redraw per doc-diagrams: `doc-inline` size, presentation ramp, at most seven nodes |
| A third of a page left blank before a figure | Shrink the figure with `"width=..."`, or move a paragraph after it |
| Table columns cramped | Shorten cell text or drop a column. Six columns is the practical limit at 6.5in |
| PDF in a serif font, or digits spaced out | Export with `export-pdf.mjs`, not `soffice` directly |
| Empty Contents section in preview | Expected. Word fills it on open. Set `toc: false` for short docs |
| Author name wrong | Set `author:` in front matter or change `scripts/defaults.json` |

## Reference

- `references/outlines.md`: outlines for a design doc, decision doc, status update, and procedural guide, and how the reader shapes them.
- `references/word-defaults.md`: the exact style values the builder emits and where they came from.
