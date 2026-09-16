---
name: research-notes
description: "Use when a deliverable must be grounded in code, documentation, conversations, or the web before it is written: learning material, a design brief, an architecture summary, an assessment, interview preparation. Also use when asked to research a topic, gather sources, take notes from a chat export, meeting transcript, or command output, or when an existing document's claims need provenance."
---

# Research Notes

## Overview

Research is a separate job from writing. Research produces notes: one file per source or subsystem, and every claim on its own line with its source and how sure you are. The writing skills, learn and word-docs, work from notes. Other sessions can pick the notes up, and nothing is researched twice.

Script paths are relative to this skill's directory.

## Declare the plan first

Before reading anything, state in one message and proceed unless the user redirects:

- **Topic** in one sentence, and the **goal**: interview preparation, design review, operating the system, or a decision. The goal decides depth and what "done" means.
- **Sources**, each named: code paths, web or not, existing documents, conversations. Never assume a source the user did not name or the request does not imply. When the request says "how does this work here", code is required. When it says "how does this work in general", web is required. Both when it says both, and the notes keep them apart.
- **Out of scope**: what you will not read, in one line. Start from the source the user named. When that source points to another, such as a linked document or a wider channel, record the pointer in Open questions. Ask before reading it.
- **Depth**: `quick` is web only in one pass. `standard` is all named sources in one pass. `deep` is standard plus an independent verification pass on load-bearing claims.
- **Output folder**: `notes/` next to the deliverable unless told otherwise.

## Method by source kind

| Source | Ground truth for | Method | Citation form |
|---|---|---|---|
| Code | How it works here | If a code-index or grounding skill exists for the repo, use it first. Otherwise dispatch read-only Explore agents, one per subsystem, each returning claims with file and line. For a codebase above roughly 20 subsystems, offer a multi-agent workflow and wait for the user to opt in | `path/to/file.py:123` |
| Web | How it works in general, the standard, the vendor's stated behavior | Primary sources first: vendor docs, the project's own repository, papers, Context7 for library docs. Use secondary sources such as blogs only to find primary ones | `https://... (read YYYY-MM-DD)` |
| Existing document | What its author claims | Read it. Extract claims. Tag them `doc`, not `verified`, unless you confirm them elsewhere. Where the document marks a claim as its own inference, tag it `inferred` and cite `(from design.md:40, the document's own inference)` | `docs/design.md:40`, or for a PDF `file.pdf:12` with the page number |
| Conversation: chat export, meeting transcript, email thread | Who said what, and when | Save the export under `sources/` with one message per line, then cite lines. That a person said something is `verified`: "Dana said the retry cap is 3." What they said, stated as a fact about the system, is `doc` until code or a live check confirms it | `sources/chat-export.md:14` |
| Live check: a command, query, or API call whose answer can change | State at one moment, such as access, query results, or open items | Save the output as `evidence/YYYY-MM-DD-<name>.txt` under a four-line header: `# command:`, `# host:`, `# time:` in UTC, `# exit:`. Cite it as `verified` and put the date in the claim, because the state can change after you look | `evidence/2026-09-15-access-check.txt:7` |
| Code on a branch that is not checked out | How it works on that branch | Export each file with `git -C <repo> show <ref>:<path> > sources/<ref>/<path>`, cite the copy, and name the ref in the claim | `sources/feature-x/lb/controller.go:210` |

Each subagent gets the note template and the tag rules below, and returns claims already tagged.

## The note format

Use `templates/note.md`. One note per source or subsystem. Each claim is one bullet, starts with a confidence tag, ends with its citation in parentheses:

```markdown
- [verified] The driver rejects a request over the KV budget with RESOURCE_EXHAUSTED. (engine/driver.cc:412)
- [doc] Route weights are recomputed every 60 seconds. (docs/routing.md:88)
- [web] vLLM hashes prefixes at block granularity. (https://docs.vllm.ai/... , read 2026-09-14)
- [inferred] The 60-second cadence bounds how stale a weight can be. (from docs/routing.md:88 and lb/controller.go:210)
- [thin] Spillover changes ring weights. (one runbook line, no code found)
```

| Tag | Meaning |
|---|---|
| `verified` | You read it in code or a test, and cite the line |
| `doc` | A document states it, and code does not confirm it yet |
| `web` | A primary web source states it |
| `inferred` | You derived it from two or more cited facts, and you name them |
| `thin` | One weak source, or a gap you could not close |

Rules:

- One claim per bullet. A bullet with "and" joining two facts is two bullets.
- A number, name, port, or default appears only with a citation. No citation, no number.
- Notes hold what is true of the system, not of one example. A formula belongs in the notes. Applying it to a worked example's illustrative values belongs in the deliverable.
- General-concept claims and this-system claims go under separate headings in the same note when both exist.
- Terms get a definition in the note's Terms section the first time they appear, as `- **Term**: definition. (citation)`. The checker requires the citation, because writing skills take their glossaries from here.
- When sources disagree, record each side as its own claim with its own citation, next to each other. Then add an Open questions entry that starts `Conflict:` and cites both sides. The checker requires two citations. Do not pick a winner in the notes.
- Cite a line range, `file:12-20`, when a fact spans lines, such as a commit whose subject holds the PR number that its body explains.
- A claim about state that can change carries the date you observed it. The checker requires a date on every claim that cites `evidence/`.
- Every note ends with Open questions: what you could not find, and where you looked.
- Sub-headings inside a claims section are fine, such as one per hop or per module. The checker follows them. A heading at the same level as the claims section starts a new section.

## Depth `deep`: verify before you trust

A load-bearing claim is one the deliverable's argument depends on. For each one, dispatch a second agent that has not seen the first agent's note. Give it only the claim and the citation, and ask it to confirm or refute the claim from the source. Downgrade any claim it cannot confirm to `thin` and record why.

## Check the notes

```bash
python3 scripts/check-notes.py notes/ --sources <folder holding the cited files>
```

The check fails on:

- a claim with no tag, an unknown tag, or no citation
- a note without Open questions, a Terms entry without a citation, or a `Conflict:` entry with fewer than two citations
- a claim that cites `evidence/` without a date
- a citation past the end of its file, or a line range that ends before it starts
- with `--sources`, which is repeatable: a `verified`, `doc`, or `web` claim whose numbers are not in the cited lines or within two lines of them

That catches invented numbers and drifted line references. Numbers inside code spans are skipped, so a model name such as `gpt-5.6-luna` does not count. A `web` claim is number-checked only when it also cites a saved copy of the page. Save a page you cite for numbers under `sources/`, and cite the copy after the URL.

An `inferred` claim with a number absent from its sources is listed for review. Keep it if the arithmetic is general, and move it to the deliverable if it computes a worked example. The check proves a number is absent. The check cannot tell whether a present number belongs to the right noun, so still read what you cite. PDF and other binary citations cannot be read by line, so they count as not checked. Fix and rerun until it passes. Do not hand notes to a writing skill until it passes.

### Check the deliverable against the notes

When the document or lesson is written, check it against the notes:

```bash
python3 scripts/check-notes.py notes/ --deliverable doc.md
```

Every multi-digit number and every code span in the deliverable must appear in some note. Front matter, fenced code, HTML comments, link targets, and list numbers are skipped. For a lesson, add `--skip-section "Worked example"`, because that section's values are illustrative. For each finding, add the claim to the notes with its citation, or take it out of the deliverable.

## Common mistakes

| Mistake | Fix |
|---|---|
| A paragraph of prose instead of tagged bullets | Split it. The value of the notes is that each line stands alone with its source |
| `verified` on something read in a design doc | That is `doc`. Verified means you saw the code |
| Citation is a directory or a repo name | Cite the file and line. A reader must be able to open it |
| Code and web claims mixed in one list | Separate headings: "In general" and "In this system" |
| Research restarted in a later session | Look for an existing `notes/` folder first and extend it |
| Notes grew past the source the user named | Record the pointer in Open questions and ask before reading further |
| "Dana said X" tagged `verified` in one claim and `doc` in another | The attribution is `verified`. The content is `doc` until confirmed |
| A live check that exists only in the chat | Save its output to `evidence/` with the header, then cite it with the date |
| A name or number in the deliverable that came from memory | Run the deliverable check. Add the claim with a citation, or delete it |
