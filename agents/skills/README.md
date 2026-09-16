# Document and learning skills

Five personal skills and one plugin that share three contracts. This file says how they fit, where they live, how to test them, and how to extend or split them. Written 2026-09-14, updated 2026-09-15.

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
| `plain-prose` | How sentences are written, in any container | Python 3.10+ for the lint script | rules, `scripts/lint-prose.py` |
| `research-notes` | Gather claims from code, web, or documents, with provenance | Explore agents, a code-index skill if present, Context7 | `notes/*.md` |
| `doc-diagrams` | Draw, recolor, check, and render a figure for a document or lesson | diagram-design plugin, Chromium, Playwright core, Python 3.10+ | `figure.html`, `figure.png` |
| `word-docs` | Markdown with front matter to a .docx in Word's default styles, and a PDF when asked | plain-prose, doc-diagrams, docx, marked, jszip, LibreOffice, poppler | `doc.docx`, `doc.pdf` |
| `learn` | Teach a topic from notes as an interactive study page | research-notes, plain-prose, doc-diagrams, marked | `study.md`, `study.html` |

Rule of the design: **sourcing, wording, drawing, and rendering are separate jobs.** A skill owns one of them and requires the others by name. Nothing is duplicated across skills.

## The three contracts

Skills talk through files, not through each other's code.

1. **Notes**, shaped like `research-notes/templates/note.md`. One file per source or subsystem. Each claim is one bullet: `- [tag] claim. (citation)`. Tags: verified, doc, web, inferred, thin. A citation is a URL, a `file:line`, or a `file:start-end` range. Saved command output lives in `evidence/` with a header naming the command and time, and every claim that cites it carries a date. Conversations are saved under `sources/`: that a person said something is `verified`, and what they said is `doc`. Terms entries carry citations, and disagreeing sources are recorded as an Open questions entry starting `Conflict:` that cites both. `research-notes/scripts/check-notes.py` enforces all of it. With `--sources`, the checker verifies that cited numbers appear at the cited lines. With `--deliverable`, it checks that a finished document's numbers and code names appear in the notes.
2. **Markdown with YAML front matter.** The word-docs skill takes any Markdown plus `title`, `author`, and `date`. Its figure convention is `![caption](figure.png)` alone on a line, with an optional `"scale=N"` or `"width=Nin"` in the image title. The source lives in `build/`, and the .docx goes to the top of the folder. The learn skill takes the same Markdown in a fixed shape of level-1 sections: Gist, Mechanism, Worked example, Parts, Misconceptions, Check yourself, Glossary, Go deeper. The learn skill accepts `![caption](figure.html)` for a stepped figure. The learn builder stops when a lesson breaks a hard rule, such as a figure whose step count differs from the worked example's. The builder warns on weaker ones. `learn/templates/study.md` and `word-docs/templates/example.md` are complete examples.
3. **Figure HTML** in diagram-design's format: inline SVG, and an optional `<main data-motion-root>` with the plugin's controller script kept verbatim. A `.diagram-design` marker next to the figure names its profile. The recolor script `apply-profile.py` maps the plugin's shipped palette to that profile. `check-figure.py` runs the plugin's checks adapted to the profile, and `render-diagram.mjs` turns the file into PNG. `doc-diagrams/templates/doc-inline.html` is a starter at the document sizes that passes the checks. `learn/scripts/build-study.mjs` embeds the HTML live. The `word-office` profile, with white paper and Office colors, makes figures match Word headings.

## Where things live

| What | Path | Managed by |
|---|---|---|
| Skills | `agents/skills/<name>/` in the dotfiles repo, linked to `~/.claude/skills/<name>` | home-manager: `home/dev/claude.nix` |
| Node dependencies | `<skill>/scripts/node_modules/` | each skill's `scripts/setup.sh`, ignored by git |
| Script tests | `<skill>/tests/`, run by `run-tests.sh` | this folder |
| Eval cases | `evals/<skill>/<case>/`, with `evals/run-evals.sh` | this folder |
| Eval plugin manifest | `.claude-plugin/plugin.json`, so `claude plugin eval` can load the five skills together | this folder |
| Copilot CLI access | `~/.agents/skills/<name>` links | home-manager: `home/dev/claude.nix` |
| Global triggers for prose | Writing section of `agents/AGENTS.md`, linked into each agent's global instructions | home-manager: `home/dev/{claude,codex,copilot,opencode}.nix` |
| diagram-design plugin | Claude: `~/.claude/plugins/cache/diagram-design/`, Copilot: `~/.copilot/installed-plugins/_direct/cathrynlavery--diagram-design/` | Claude: declared in `home/dev/claude.nix`. Copilot: `copilot plugin install cathrynlavery/diagram-design`, once per machine |
| Diagram color profile | `~/.diagram-design/profiles/word-office.md`, else `doc-diagrams/profiles/` | `doc-diagrams/scripts/setup.sh` copies it |
| Default author | `word-docs/scripts/defaults.json` | edit by hand |
| A topic taught in several lessons | `<topic>/notes/` shared by all lessons, and `<topic>/lesson-<name>/` holding each lesson's `study.md`, `figure.html`, `figure.png`, and `study.html` | the learn skill |

The test and eval files sit next to `skills/`, not inside it. In the dotfiles layout that is `agents/`, beside `agents/skills/`, because home-manager links every folder inside `agents/skills/` as a skill.

System tools: node 20+, Python 3.10+, and Chromium or Chrome. Word previews and PDFs also need LibreOffice, poppler, and fontconfig on Linux. Diagram rendering needs network access for Google Fonts.

A plugin installed during a Claude Code session is not listed by the Skill tool until Claude Code restarts. The skills that depend on diagram-design say how to read its SKILL.md directly until then.

## Extending

- **A new output format**, such as an HTML report: add a renderer that reads contract 2. Reuse the parser pattern in `word-docs/scripts/lib/` and the figure embedding in `learn/scripts/lib/figures.mjs`. Do not add format rules to plain-prose or drawing rules to the renderer.
- **A new source kind**, such as a ticket system: add a row to the method table in `research-notes/SKILL.md` with its citation form. Teach `check-notes.py` to accept that form. The tags do not change.
- **A new diagram destination**, such as slides: add a row to `doc-diagrams` with its size preset, type ramp, and output format. Drawing rules stay in the plugin.
- **A new look for figures**: add a profile to `doc-diagrams/profiles/` in the plugin's style-guide format and point the `.diagram-design` marker at it. `apply-profile.py` and `check-figure.py` read any profile, so no code changes.
- **A new writing rule**: it goes in plain-prose only, and only after a baseline run shows the failure without it.

## Decomposing

Each skill can be deleted or replaced without touching the others as long as its contract holds:

- Replace the Word builder with pandoc and a reference .docx: keep contract 2, keep the figure convention.
- Replace diagram-design with another drawing system: keep contract 3's output, an HTML file with inline SVG, or change `figures.mjs` and `render-diagram.mjs` together.
- Drop learn's interactive page and keep only `study.md`: the shape is still useful as plain Markdown or as a Word document through word-docs.

## Testing a change

The method follows Anthropic's guidance on skill evals. Take a baseline before the edit, use realistic prompts, and grade with code checks where possible. Run each case several times and read the transcripts. The notes behind it are in the session's research folder, `skill-testing/notes/`.

There are two layers.

| Layer | Checks | Run | Cost |
|---|---|---|---|
| Script tests | Every script, including checkers fed planted failures | `./run-tests.sh` on every machine, after every change | free |
| Evals | That each skill still fires and still shapes what the agent writes | `evals/run-evals.sh <plugin root>` | model usage |

1. **Before editing,** copy the skills to a read-only snapshot folder at the same depth as this folder, with its own `.claude-plugin/plugin.json`. Run `evals/run-evals.sh <snapshot> --ablation none` for the baseline.
2. **Write a failing test first.** For a script, add the test that reproduces the bug and watch it fail. For a SKILL.md change, add or pick an eval case whose baseline shows the failure.
3. **Change** the skill to address that failure only.
4. **Green.** `./run-tests.sh` passes on Linux and macOS. `evals/run-evals.sh . --ablation none` scores at least the baseline on regression cases and higher on the cases for the change. Read the transcripts of failed runs before trusting a score, with `--keep-temp`.
5. **Scripts** get a code review through the `code-reviewer` agent, and every finding is reproduced before it is fixed.

Eval runs are isolated: a throwaway home, no personal skills or other plugins, and only the tools the runner grants. `run-evals.sh` copies diagram-design into `.eval-deps/` because a case may load plugins only from inside the plugin root. The script grants Write but not Bash, because `claude plugin eval` refuses Bash on a machine whose `~/.ssh` holds symlinks, as home-manager's does. Scripts are therefore covered by the script tests, not the evals. Case fixtures reach the workspace through each case's `setup-workspace.sh`. The model is pinned to `claude-opus-5` so scores stay comparable. A grader's front matter ends at the first `---`, so write `-{3}` inside a pattern.

Session notes with the reasoning behind each decision are in the memory files `word-docs-skill-set`, `learn-skill-set`, and `skills-feedback-handoff`.
