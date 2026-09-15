---
name: research-notes
description: "Use when a deliverable must be grounded in code, documentation, or the web before it is written: learning material, a design brief, an architecture summary, an assessment, interview preparation. Also use when asked to research a topic, gather sources, or when an existing document's claims need provenance."
---

# Research Notes

## Overview

Research is a separate job from writing. It produces notes: one file per source or subsystem, every claim on its own line with where it came from and how sure you are. The writing skills (learn, word-docs) work from notes, other sessions can pick them up, and nothing is re-researched.

Script paths are relative to this skill's directory.

## Declare the plan first

Before reading anything, state in one message and proceed unless the user redirects:

- **Topic** in one sentence, and the **goal** (interview preparation, design review, operating the system, a decision). The goal decides depth and what "done" means.
- **Sources**, each named: code paths, web (yes or no), existing documents. Never assume a source the user did not name or the request does not imply. When the request says "how does this work here", code is required. When it says "how does this work in general", web is required. Both when it says both, and the notes keep them apart.
- **Depth**: `quick` (web only, one pass), `standard` (all named sources, one pass), `deep` (standard plus an independent verification pass on load-bearing claims).
- **Output folder**: `notes/` next to the deliverable unless told otherwise.

## Method by source kind

| Source | Ground truth for | Method | Citation form |
|---|---|---|---|
| Code | How it works here | If a code-index or grounding skill exists for the repo, use it first. Otherwise dispatch read-only Explore agents, one per subsystem, each returning claims with file and line. For a codebase above roughly 20 subsystems, offer a multi-agent workflow and wait for the user to opt in | `path/to/file.py:123` |
| Web | How it works in general, the standard, the vendor's stated behavior | Primary sources first: vendor docs, the project's own repository, papers, Context7 for library docs. Secondary sources (blogs) only to find primary ones | `https://... (read YYYY-MM-DD)` |
| Existing document | What its author claims | Read it. Extract claims. Tag them `doc`, not `verified`, unless you confirm them elsewhere. Where the document marks a claim as its own inference, tag it `inferred` and cite `(from design.md:40, the document's own inference)` | `docs/design.md:40`; for a PDF, `file.pdf:12` with the page number |

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
| `doc` | A document states it; not confirmed in code |
| `web` | A primary web source states it |
| `inferred` | You derived it from two or more cited facts; name them |
| `thin` | One weak source, or a gap you could not close |

Rules:

- One claim per bullet. A bullet with "and" joining two facts is two bullets.
- A number, name, port, or default appears only with a citation. No citation, no number.
- Notes hold what is true of the system, not of one example. A formula belongs in the notes; applying it to a worked example's illustrative values belongs in the deliverable.
- General-concept claims and this-system claims go under separate headings in the same note when both exist.
- Terms get a definition in the note's Terms section the first time they appear, as `- **Term**: definition. (citation)`. The checker requires the citation, because writing skills take their glossaries from here.
- When sources disagree, record each side as its own claim with its own citation, next to each other. Then add an Open questions entry that starts `Conflict:` and cites both sides; the checker requires two citations. Do not pick a winner in the notes.
- Every note ends with Open questions: what you could not find, and where you looked.
- Sub-headings inside a claims section are fine (one per hop, per module); the checker follows them. A heading at the same level as the claims section starts a new section.

## Depth `deep`: verify before you trust

For each load-bearing claim (one the deliverable's argument depends on), dispatch a second agent that has not seen the first agent's note, with the claim and the citation only, and the instruction to confirm or refute it from the source. Downgrade any claim it cannot confirm to `thin` and record why.

## Check the notes

```bash
python3 scripts/check-notes.py notes/ --sources <folder holding the cited files>
```

The check fails on an untagged claim, a claim with no citation, an unknown tag, or a note without Open questions. With `--sources` (repeatable; pass the repo root or the documents folder), it also opens each cited file and fails a `verified` or `doc` claim whose numbers do not appear within two lines of the citation. That catches invented numbers and drifted line references. An `inferred` claim with a number absent from its sources is listed for review: keep it if the arithmetic is general, move it to the deliverable if it computes a worked example. The check cannot tell whether a number that is present belongs to the right noun, so still read what you cite. It is weaker for sources written one paragraph per line, because the window is then a whole paragraph. PDF and other binary citations cannot be read by line, so they are counted as not checked. A citation past the end of its file always fails. With `--sources` or without, it also fails a Terms entry without a citation and a `Conflict:` entry that cites fewer than two sources. Fix and rerun until it passes. Do not hand notes to a writing skill until it passes.

## Common mistakes

| Mistake | Fix |
|---|---|
| A paragraph of prose instead of tagged bullets | Split it. The value of the notes is that each line stands alone with its source |
| `verified` on something read in a design doc | That is `doc`. Verified means you saw the code |
| Citation is a directory or a repo name | Cite the file and line. A reader must be able to open it |
| Code and web claims mixed in one list | Separate headings: "In general" and "In this system" |
| Research restarted in a later session | Look for an existing `notes/` folder first and extend it |
