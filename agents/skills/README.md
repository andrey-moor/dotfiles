# Document and learning skills

Five personal skills and one plugin that share three contracts. This file says how they fit, where they live, and how to extend or split them. Written 2026-09-14.

## The map

```
                 research-notes ──── notes/ ────┐
                                                ▼
plain-prose ──(words in every output)──►  learn ──► study.md ──► study.html
                                          word-docs ──► doc.md ──► doc.docx
                                                ▲
                 doc-diagrams ──── figure.html / figure.png ──┘
                        │
                        └── uses the diagram-design plugin (drawing rules, step mode, checks)
```

| Skill | Job | Depends on | Produces |
|---|---|---|---|
| `plain-prose` | How sentences are written, in any container | nothing | rules only |
| `research-notes` | Gather claims from code, web, or documents, with provenance | Explore agents, a code-index skill if present, Context7 | `notes/*.md` |
| `doc-diagrams` | Draw, recolor, check, and render a figure for a document or lesson | diagram-design plugin, Chromium, Playwright core, Python 3.10+ | `figure.html`, `figure.png` |
| `word-docs` | Markdown with front matter to a .docx in Word's default styles | plain-prose, doc-diagrams, docx + marked | `doc.docx` |
| `learn` | Teach a topic from notes as an interactive study page | research-notes, plain-prose, doc-diagrams, marked | `study.md`, `study.html` |

Rule of the design: **sourcing, wording, drawing, and rendering are separate jobs.** A skill owns one of them and requires the others by name. Nothing is duplicated across skills.

## The three contracts

Skills talk through files, not through each other's code.

1. **Notes** (`research-notes/templates/note.md`). One file per source or subsystem. Each claim is one bullet: `- [tag] claim. (citation)`. Tags: verified, doc, web, inferred, thin. Terms entries carry citations, and disagreeing sources are recorded as an Open questions entry starting `Conflict:` that cites both. `research-notes/scripts/check-notes.py` enforces all of it, and with `--sources` verifies that cited numbers appear at the cited lines. Anything that needs grounded facts reads notes; nothing reads raw sources twice.
2. **Markdown with YAML front matter.** word-docs takes any Markdown plus `title`, `author`, `date`, and a figure convention: `![caption](figure.png)` alone on a line. learn takes the same Markdown in a fixed shape of level-1 sections (Gist, Mechanism, Worked example, Parts, Misconceptions, Check yourself, Glossary, Go deeper) and accepts `![caption](figure.html)` for a stepped figure. `learn/scripts/build-study.mjs` stops when a lesson breaks a hard rule, such as a figure whose step count differs from the worked example's, and warns on weaker ones. `learn/templates/study.md` and `word-docs/templates/example.md` are complete examples.
3. **Figure HTML** in diagram-design's format: inline SVG, optional `<main data-motion-root>` with the plugin's controller script kept verbatim. A `.diagram-design` marker next to the figure names its profile. `doc-diagrams/scripts/apply-profile.py` recolors the file from the plugin's shipped palette to that profile, `check-figure.py` runs the plugin's checks adapted to it, and `render-diagram.mjs` turns the file into PNG. `learn/scripts/build-study.mjs` embeds it live. The `word-office` profile (white paper, Office colors) makes figures match Word headings.

## Where things live

| What | Path | Managed by |
|---|---|---|
| Skills | `agents/skills/<name>/` in the dotfiles repo, linked to `~/.claude/skills/<name>` | home-manager: `home/dev/claude.nix` |
| Node dependencies | `<skill>/scripts/node_modules/` | each skill's `scripts/setup.sh`, ignored by git |
| Copilot CLI access | `~/.agents/skills/<name>` links | home-manager: `home/dev/claude.nix` |
| Global triggers for prose | Writing section of `agents/AGENTS.md`, linked into each agent's global instructions | home-manager: `home/dev/{claude,codex,copilot,opencode}.nix` |
| diagram-design plugin | Claude: `~/.claude/plugins/cache/diagram-design/`, Copilot: `~/.copilot/installed-plugins/_direct/cathrynlavery--diagram-design/` | Claude: declared in `home/dev/claude.nix`. Copilot: `copilot plugin install cathrynlavery/diagram-design`, once per machine |
| Diagram color profile | `~/.diagram-design/profiles/word-office.md` | `doc-diagrams/scripts/setup.sh` copies it from `doc-diagrams/profiles/` |
| Default author | `word-docs/scripts/defaults.json` | edit by hand |
| A topic taught in several lessons | `<topic>/notes/` shared by all lessons; `<topic>/lesson-<name>/` holds each lesson's `study.md`, `figure.html`, `figure.png`, and `study.html` | the learn skill |

System tools: node 20+, Python 3.10+, Chromium or Chrome, LibreOffice and poppler for Word previews, network for Google Fonts at diagram render time.

A plugin installed during a Claude Code session is not listed by the Skill tool until Claude Code restarts. The skills that depend on diagram-design say how to read its SKILL.md directly until then.

## Extending

- **A new output format** (HTML report, PDF): add a renderer that reads contract 2. Reuse the parser pattern in `word-docs/scripts/lib/` and the figure embedding in `learn/scripts/lib/figures.mjs`. Do not add format rules to plain-prose or drawing rules to the renderer.
- **A new source kind** for research (a ticket system, a wiki API): add a row to the method table in `research-notes/SKILL.md` with its citation form, and teach `check-notes.py` to accept that form. The tags do not change.
- **A new diagram destination** (slides, wiki): add a row to `doc-diagrams` with its size preset, type ramp, and output format. Drawing rules stay in the plugin.
- **A new look for figures**: add a profile to `doc-diagrams/profiles/` in the plugin's style-guide format and point the `.diagram-design` marker at it. `apply-profile.py` and `check-figure.py` read any profile, so no code changes.
- **A new writing rule**: it goes in plain-prose only, and only after a baseline run shows the failure without it.

## Decomposing

Each skill can be deleted or replaced without touching the others as long as its contract holds:

- Replace the Word builder with pandoc and a reference .docx: keep contract 2, keep the figure convention.
- Replace diagram-design with another drawing system: keep contract 3's output (an HTML file with inline SVG) or change `figures.mjs` and `render-diagram.mjs` together.
- Drop learn's interactive page and keep only `study.md`: the shape is still useful as plain Markdown or as a Word document through word-docs.

## Testing a change

Skills are tested like code, before and after:

1. **Baseline.** Give a fresh subagent the task without the skill (or with the old skill) and record what it does.
2. **Change** the skill to address that failure only.
3. **Green.** Run the same task with the skill through a fresh subagent that reports what was unclear, missing, or wrong. Fix the report.
4. **Scripts** get a code review through the `code-reviewer` agent, and every finding is reproduced before it is fixed.

Session notes with the reasoning behind each decision are in the memory files `word-docs-skill-set` and `learn-skill-set`.
