---
name: doc-diagrams
description: "Use when a document, report, slide, or wiki page needs a diagram (architecture, flow, sequence, state, timeline, comparison, layers) delivered as an image file, or when asked to draw a diagram and render it to PNG or SVG for Word, PowerPoint, or PDF."
---

# Doc Diagrams

## Overview

Draw the diagram with the diagram-design plugin (editorial SVG in HTML), recolor it to the document's profile, check it, render it to PNG, look at the PNG, then embed it. Word gets the PNG, not SVG: Word's SVG renderer cannot load web fonts, so SVG text would fall back to whatever font the reader has. A learn page embeds the HTML itself, in step mode.

**REQUIRED SUB-SKILL:** diagram-design (plugin) for drawing. Invoke it with the Skill tool as `diagram-design:diagram-design`. In Copilot CLI it is the plugin skill named `diagram-design`. If the skill is not listed (a plugin installed during the current session appears only after a restart), read its SKILL.md directly: `~/.claude/plugins/cache/diagram-design/diagram-design/<version>/skills/diagram-design/SKILL.md` (Claude Code) or `~/.copilot/installed-plugins/_direct/cathrynlavery--diagram-design/skills/diagram-design/SKILL.md` (Copilot). Either way, load the type reference for the chosen diagram type before drawing.

Script paths are relative to this skill's directory. First use on a machine: `bash scripts/setup.sh` (installs the renderer and the `word-office` profile).

## Does the diagram earn its place?

Draw only when a reader learns more from the picture than from a sentence or a table. A list of things is a table. A before/after is a table. One box is a sentence. Above seven nodes at the type sizes below, it is two diagrams.

## Steps

1. **Confirm the plugin is installed:** a directory exists under `~/.claude/plugins/cache/diagram-design/` (Claude Code) or `~/.copilot/installed-plugins/_direct/cathrynlavery--diagram-design/` (Copilot). If not, tell the user to install it (`/plugin marketplace add cathrynlavery/diagram-design` then `/plugin install diagram-design@diagram-design` in Claude Code; `copilot plugin install cathrynlavery/diagram-design` for Copilot), and stop.
2. **Mark the profile.** In the folder that holds the document or lesson, write `.diagram-design` containing exactly `profile: word-office`. The diagram-design skill reads it to skip its first-run style prompt. `apply-profile.py` and `check-figure.py` read it to pick the palette: white paper and Office theme colors (navy ink, orange accent, blue links) that match Word's headings.
3. **Choose type and size.** Pick the type from diagram-design's guide. Use the `doc-inline` width of 960 units. Size the height to the content plus the 40px margins, rounded to a multiple of 4. Use this type ramp for every text role:

   | Role | Size |
   |---|---|
   | Node names | 16px |
   | Sublabels, arrow labels, legend text, zone and eyebrow labels | 12px |
   | Node boxes | 64px tall |
   | Gaps between nodes | 40px |
   | Label masks | 16px tall, with at least 16px between a zone label's mask and the first node below it |

   The 960 units span 6.5in on the page, so 16px prints at about 10pt and 12px at about 8pt. The plugin's standard ramp prints 8px labels at 5pt. At this ramp seven nodes fit legibly; the plugin's nine-node budget assumes its smaller ramp. Use `doc-wide` (1280x720) only for landscape pages or slides.
4. **Draw** the HTML file following diagram-design's rules: 4px grid, one accent on at most two elements, orthogonal connectors, labels off the lines, a legend strip at the bottom, and no empty band above the content. Name the accessible-name IDs after the file: `figure.html` needs `figure-title` and `figure-desc`.
5. **Recolor:** `python3 scripts/apply-profile.py figure.html` replaces every shipped plugin color that the profile changes, in CSS, SVG attributes, and `rgba()` tints. Run it after drawing, and again after each fix. The first run marks the file with an `apply-profile` comment. If the profile reuses a shipped color, later runs leave that color alone and say so, so set new uses of it by hand.
6. **Check:** `python3 scripts/check-figure.py figure.html` runs the plugin's self check, geometry check, motion check for step-mode figures, and skin linter in one pass. It also checks the 16px label masks that the plugin's geometry check skips, judges colors against the profile, and fails if a shipped color is left. Fix every finding and rerun. It cannot judge crowding or legibility, so step 8 still matters.
7. **Render:** `node scripts/render-diagram.mjs figure.html --scale 3` writes `figure.png` at viewBox times scale. Add `--svg` for a standalone SVG when a deck or Figma also needs it.
8. **Look at the PNG** with Read. Check that every label is legible, no arrow crosses text, no two arrows overlap, the accent is on the focal element only, and nothing touches the edge. Fix the HTML, then repeat steps 5 to 8.
9. **Embed.** In Markdown for word-docs: `![One sentence saying what the reader should see](figure.png)` on its own line. In a deck, insert the PNG at full slide width. In a learn study file, reference `figure.html`.

## Step mode, for lessons and walkthroughs

When the figure will be stepped through (the learn skill's worked example, a policy trace, a comparison), draw it in diagram-design's `step` motion mode. Copy `assets/template-motion.html` from the plugin and keep its controller script verbatim, because the plugin linter rejects modified controllers. Tag each semantic group `data-motion-item data-step="N"` in narrative order: at most eight steps and twelve items. Rename the template's slug-prefixed IDs to the file's slug. The static frame stays complete, so the same file still renders to PNG, and `check-figure.py` runs the motion check.

In a learn page the figure keeps the plugin's 720px minimum width and scrolls sideways inside its own box on a narrow screen, so labels stay readable. Its buttons and the lesson's step text move together in both directions. Under reduced motion the figure stays complete and the text still steps.

## Requirements

- A Chromium binary. The renderer checks `CHROME_PATH`, then `/usr/bin/chromium`, `/usr/bin/google-chrome`, and the macOS app paths.
- Python 3.10 or later for the recolor and check scripts. They use only the standard library.
- Network access at render time, for Google Fonts (Instrument Serif, Geist, Geist Mono). The renderer runs Chromium sandboxed and allows requests only to the two Google Fonts hosts; everything else in the HTML is blocked. Offline, it prints a font warning and the PNG uses substitute fonts. Say so when delivering.

## Common mistakes

| Mistake | Fix |
|---|---|
| Grey paper, tangerine, or slate in a Word document | The shipped palette is still in the file. Add the `.diagram-design` marker and run `apply-profile.py` |
| `check-figure.py` reports an a11y finding about IDs | Rename the title, description, and marker IDs to start with the file's slug |
| Text unreadable at page width | Drawn with the plugin's standard ramp or too many nodes. Redraw at `doc-inline` with the ramp above and at most seven nodes |
| Empty band above the diagram | Content placed low in the viewBox. Move it up to the 40px margin, or shrink the viewBox height to the content |
| Arrows run through boxes or over each other | Violates diagram-design connector rules. Reroute; if it cannot be routed, split the diagram |
| Rendered before fonts loaded | The script waits for `document.fonts.ready`; if fonts still fail, check network access |
| Exported SVG into Word | Use the PNG. Keep SVG for Figma or slides that can embed fonts |
