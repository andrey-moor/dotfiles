---
name: doc-diagrams
description: "Use when a document, report, slide, lesson, or wiki page needs a diagram, such as an architecture, flow, sequence, state, timeline, Gantt, comparison, or layer diagram, delivered as an image. Also use when asked to draw a diagram for Word, PowerPoint, or PDF and render it to PNG or SVG. Use this skill before diagram-design whenever the figure goes into a document."
---

# Doc Diagrams

## Overview

Draw the diagram with the diagram-design plugin and recolor it to the document's profile. Then check it, render it to PNG, look at the PNG, and embed it. Word gets the PNG, not SVG, because Word's SVG renderer cannot load web fonts. A learn page embeds the HTML itself, in step mode.

**REQUIRED SUB-SKILL:** diagram-design, the plugin, for drawing rules. Invoke it with the Skill tool as `diagram-design:diagram-design` after this skill, not instead of it. In Copilot CLI it is the plugin skill named `diagram-design`. If the skill is not listed, read its SKILL.md directly. Claude Code keeps it at `~/.claude/plugins/cache/diagram-design/diagram-design/*/skills/diagram-design/SKILL.md`, one folder per version, so take the newest match. Copilot keeps it at `~/.copilot/installed-plugins/_direct/cathrynlavery--diagram-design/skills/diagram-design/SKILL.md`. Load the type reference for the chosen diagram type before drawing.

Script paths are relative to this skill's directory. First use on a machine: `bash scripts/setup.sh`, which installs the renderer and the `word-office` profile.

## Does the diagram earn its place?

Draw only when a reader learns more from the picture than from a sentence or a table. A list of things is a table. A before and after is a table. One box is a sentence. Above seven nodes at the type sizes below, it is two diagrams.

## Steps

1. **Confirm the plugin is installed.** A folder exists under `~/.claude/plugins/cache/diagram-design/` for Claude Code, or `~/.copilot/installed-plugins/_direct/cathrynlavery--diagram-design/` for Copilot. If not, tell the user to install it and stop. In Claude Code that is `/plugin marketplace add cathrynlavery/diagram-design` then `/plugin install diagram-design@diagram-design`. In Copilot it is `copilot plugin install cathrynlavery/diagram-design`.
2. **Mark the profile first.** In the folder that holds the figure, write `.diagram-design` containing exactly `profile: word-office`. Write the marker before invoking diagram-design, because it stops the plugin's first-run style question. `apply-profile.py` and `check-figure.py` read the marker to pick the palette: white paper and Office theme colors that match Word's headings. Both scripts look for the profile in `~/.diagram-design/profiles/`, then in this skill's `profiles/`.
3. **Start from the template.** For an architecture or flow figure, copy `templates/doc-inline.html` and rename its `doc-inline-` IDs to the file's slug. The template already has the canvas, type sizes, zone, arrow labels, masks, and legend below, and it passes `check-figure.py`. For another type, start from the plugin's template for that type and apply the sizes below.
4. **Use the doc-inline sizes.** The canvas is 960 units wide with 40px margins. Size the height to the content plus the bottom margin, rounded to a multiple of 4. Every text role uses this ramp:

   | Role | Size |
   |---|---|
   | Node names | 16px |
   | Sublabels, arrow labels, legend text, zone and eyebrow labels | 12px |
   | Node boxes | 64px tall |
   | Gaps between nodes | 40px, or 80px where an arrow carries a label |
   | Label masks | 16px tall, with at least 16px between a zone label's mask and the first node below it |
   | Gantt and timeline label column | 160px |
   | Gantt and timeline bars | 32px tall, on a 56px row pitch |
   | Gantt and timeline day width | 40px per day, which fits 18 days in the 720px beside the label column |
   | Axis labels | 12px |
   | Legend | At most five items per row. Start a second row 24px below the first |

   The 960 units span 6.5in on the page, so 16px prints at about 10pt and 12px at about 8pt. The plugin's standard ramp prints 8px labels at 5pt. At this ramp seven nodes fit legibly. The plugin's nine-node budget assumes its smaller ramp. Use `doc-wide`, 1280 by 720, only for landscape pages or slides.
5. **Draw** following diagram-design's rules. Keep to the 4px grid and one accent on at most two elements. Use orthogonal connectors, keep labels off the lines, and leave no empty band above the content. Name the accessible-name IDs after the file: `figure.html` needs `figure-title` and `figure-desc`.
   - **Charts with values.** For a Gantt, a timeline, or any chart, compute every x, y, and width from the data with a short script instead of typing coordinates. On a day axis, x is the label column plus the day offset times the day width. A bar's width is its length in days times the day width. A figure can pass every check and still be a day off.
   - **Masks inside zones.** A label mask inside a tinted zone is two rects of one size: a paper rect, then a rect with the zone's tint. A plain paper mask shows as a pale patch on white paper.
   - **Legend.** Keep the legend strip when the figure uses two or more node styles besides the accent. With one node style plus the accent, drop the legend and say what the accent marks in the caption, which saves about 60px.
6. **Recolor:** `python3 scripts/apply-profile.py figure.html` replaces every shipped plugin color that the profile changes, in CSS, SVG attributes, and `rgba()` tints. Run it after drawing, and again after each fix. The first run marks the file with an `apply-profile` comment. If the profile reuses a shipped color, later runs leave that color alone and say so, so set new uses of it by hand.
7. **Check:** `python3 scripts/check-figure.py figure.html` runs the plugin's self check, geometry check, motion check for step-mode figures, and skin linter in one pass. The script also checks the 16px label masks that the plugin's geometry check skips. The script judges colors against the profile, flags a mask that shows as a patch, and fails if a shipped color is left. Fix every finding and rerun. The script cannot judge crowding, legibility, or whether a bar matches its data, so step 9 still matters.
8. **Render:** `node scripts/render-diagram.mjs figure.html --scale 3` writes `figure.png` at viewBox times scale. Add `--svg` for a standalone SVG when a deck or Figma also needs it.
9. **Look at the PNG** with Read. Check that every label is legible and that no arrow crosses text or another arrow. Check that the accent is on the focal element only and that nothing touches the edge. For a chart, check one bar's start and end against the axis. Fix the HTML, then repeat steps 6 to 9.
10. **Embed.** In Markdown for word-docs, put `![One sentence saying what the reader should see](figure.png)` on its own line. In a deck, insert the PNG at full slide width. In a learn study file, reference `figure.html`.

## Step mode, for lessons and walkthroughs

Draw a figure that readers step through in diagram-design's `step` motion mode. Examples are the learn skill's worked example, a policy trace, and a comparison. Copy `assets/template-motion.html` from the plugin and keep its controller script verbatim, because the plugin linter rejects modified controllers. Tag each semantic group `data-motion-item data-step="N"` in narrative order, with at most eight steps and twelve items. Rename the template's slug-prefixed IDs to the file's slug. The static frame stays complete, so the same file still renders to PNG, and `check-figure.py` runs the motion check.

In a learn page the figure keeps the plugin's 720px minimum width. On a narrow screen it scrolls sideways inside its own box, so labels stay readable. Its buttons and the lesson's step text move together in both directions. Under reduced motion the figure stays complete and the text still steps.

## Requirements

- A Chromium binary. The renderer checks `CHROME_PATH`, then `/usr/bin/chromium`, `/usr/bin/google-chrome`, and the macOS app paths.
- Python 3.10 or later for the recolor and check scripts, which use only the standard library.
- Network access at render time, for Google Fonts: Instrument Serif, Geist, and Geist Mono. The renderer runs Chromium sandboxed and allows requests only to the two Google Fonts hosts. Offline, it prints a font warning and the PNG uses substitute fonts. Say so when delivering.

## Common mistakes

| Mistake | Fix |
|---|---|
| diagram-design asked a style question and nothing was drawn | Write the `.diagram-design` marker first, and invoke this skill before the plugin |
| Grey paper, tangerine, or slate in a Word document | The shipped palette is still in the file. Add the marker and run `apply-profile.py` |
| `check-figure.py` reports an a11y finding about IDs | Rename the title, description, and marker IDs to start with the file's slug |
| Text unreadable at page width | Drawn with the plugin's standard ramp or too many nodes. Start from the template, or redraw at the sizes above with at most seven nodes |
| A pale patch around a zone label | Layer the zone's tint over the paper mask, as `check-figure.py` suggests |
| A bar a day too long, or starting on the wrong day | Positions were typed by hand. Compute them from the dates with a script |
| Legend items run past the right margin | Five items per row, then a second row |
| Empty band above the diagram | Content placed low in the viewBox. Move it up to the 40px margin, or shrink the viewBox height to the content |
| Arrows run through boxes or over each other | Violates diagram-design connector rules. Reroute, or split the diagram if it cannot be routed |
| Rendered before fonts loaded | The script waits for `document.fonts.ready`. If fonts still fail, check network access |
| Exported SVG into Word | Use the PNG. Keep SVG for Figma or slides that can embed fonts |
