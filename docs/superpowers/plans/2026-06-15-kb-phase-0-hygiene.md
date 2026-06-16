# KB Phase 0 — Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean the KB before building on it — repair the 36 stranded raw Web-Clipper inbox notes to valid schema, remove duplicates, and close the lint/index gaps that let the rot go unnoticed.

**Architecture:** Two kinds of change. (1) **Vault data migration** — a one-time normalization of inbox notes via the Obsidian MCP (no new code; the executor loops over a worklist). (2) **Skill-doc edits** — update the `kb` skill's lint/index rules in the dotfiles chezmoi source, then deploy with chezmoi. The Obsidian vault is the source of truth; its data changes are verified by MCP queries, not git commits.

**Tech Stack:** Obsidian MCP tools (`mcp__obsidian__*`), the `kb` Claude Code skill (markdown), chezmoi, `just`.

---

## Verification model (read before starting)

This phase has **no automated test suite** — it is data migration + prose skill edits. So:
- **Vault-data tasks** (Tasks 1–3) end with an **MCP verification query** (expected result stated), not a git commit. The Obsidian vault is a separate iCloud store, not this git repo — its files are never `git add`ed here.
- **Skill-edit tasks** (Tasks 4–6) edit version-controlled files under `chezmoi/private_dot_claude/` and **do** end in a git commit, then deploy via chezmoi.
- **Destructive steps** (deletions in Task 2) are **gated on explicit user confirmation** at execution time.

## File Structure

**Repo files modified (version-controlled, committed):**
- `chezmoi/private_dot_claude/skills/kb/references/lint-rules.md` — add E07/W07/W08/I05 rules, extend E05, add scope note.
- `chezmoi/private_dot_claude/commands/kb/lint.md` — mirror the new checks + scope note + auto-fix entries.
- `chezmoi/private_dot_claude/commands/kb/index.md` — add an "Inbox Health" section.

**Vault targets (data, not committed):**
- `Main/Knowledge/inbox/*.md` — 36 raw Web-Clipper notes (normalize 31, delete ~5 dupes).
- `Main/_system/index.md` — regenerated fresh.

## Canonical transformation (used by Tasks 1–3)

**Raw Web-Clipper frontmatter → target KB inbox schema.** Apply per note via
`mcp__obsidian__update_frontmatter` with **`merge: false`** (replaces the whole frontmatter object,
dropping the stale keys). The note **body is left untouched** — the clipped content is already
fetched and is valuable for later phases.

| Target field | From | Rule |
|---|---|---|
| `title` | `title` | keep verbatim |
| `url` | `source` | the URL value moves into `url` |
| `source` | `source` (URL) | infer **type** from the URL host (table below) |
| `date_added` | `created` | truncate ISO timestamp → `YYYY-MM-DD` (take first 10 chars) |
| `summary` | `description` | keep as **provisional** summary (real summary comes at process time) |
| `tags` | — | set to `[]` (drops the `Knowledge/inbox` folder-tag artifact) |
| `status` | — | set to `"inbox"` (this missing field is why the Bases dashboard renders blank) |
| `context` | — | set to `"Imported from Web Clipper backlog"` |
| `author` | `author[0]` | flatten array + strip wikilink: `["[[Avery Pennarun]]"]` → `"Avery Pennarun"` |
| `published` | — | **drop** (not in schema) |
| `created` | — | **drop** (consumed into `date_added`) |
| `description` | — | **drop** (consumed into `summary`) |

**URL host → `source` type** (from `references/schema.md`):

| Host contains | `source` |
|---|---|
| `github.com` | `github` |
| `x.com` or `twitter.com` | `tweet` |
| `youtube.com` or `youtu.be` | `youtube` |
| `arxiv.org` | `paper` |
| `substack.com`, or URL contains `newsletter` | `newsletter` |
| a podcast host (`podcasts.apple.com`, `open.spotify.com/episode`, etc.) | `podcast` |
| anything else | `article` |

---

### Task 1: Detect & build the worklist (read-only, no mutation)

**Files:** none modified. Reads `Main/Knowledge/inbox/`.

- [ ] **Step 1: List the inbox**

Run `mcp__obsidian__list_directory` with `path: "Main/Knowledge/inbox"`.
Expected: ~36 `.md` files.

- [ ] **Step 2: Pull frontmatter for every inbox note**

Call `mcp__obsidian__get_frontmatter` for each file (batch in parallel).

- [ ] **Step 3: Classify each note**

A note is **raw Web-Clipper schema** if `status` is absent **OR** `source` looks like a URL
(`http…`). Build a worklist table: `filename | url | inferred source-type | created→date_added`.
Notes that already have `status: inbox` + a proper `url` are already-normalized — exclude them.

- [ ] **Step 4: Group by URL to find duplicates**

Normalize each `url` (strip trailing `/`, drop `utm_*`/`#` fragments) and group. Any group with
≥2 notes is a duplicate set. Expected visible groups (confirm, don't assume exhaustive):
`RBAC like it was meant to be` (×2), `kepano/obsidian-skills` (×3),
`widelands` (×2), `Claude + Obsidian` (×2) → **~5 redundant copies to remove**.

- [ ] **Step 5: Present the worklist**

Show the user: total inbox count, how many are raw-schema, the duplicate groups, and the planned
~5 deletions. This is the snapshot before any mutation. No commit (read-only).

---

### Task 2: Remove duplicates (destructive — user-gated)

**Files:** deletes redundant `Main/Knowledge/inbox/*.md`.

- [ ] **Step 1: For each duplicate group, choose the keeper**

Read the body of each member via `mcp__obsidian__read_note`. Keep the canonical copy:
the one with the **most complete body** (longest content); tie-break on **earliest `created`**.
The redundant copies are usually the ` 1`/` 2`-suffixed filenames.

- [ ] **Step 2: Confirm byte-similarity**

Compare body lengths within the group. If members are byte-identical (e.g. the two RBAC clips),
deletion is safe. If they differ materially, surface the difference to the user rather than
guessing.

- [ ] **Step 3: GATE — get explicit user approval**

Present the exact list of files to delete and the keeper for each group. Ask:
"Delete these N duplicate copies? (yes / review one-by-one / skip)". **Do not proceed without a yes.**

- [ ] **Step 4: Delete approved duplicates**

For each: `mcp__obsidian__delete_note` with `path` and `confirmPath` set to the **same** path.

- [ ] **Step 5: Verify**

Run `mcp__obsidian__list_directory` on `Main/Knowledge/inbox`.
Expected: count dropped by the number deleted (≈36 → ≈31); no remaining ` 1`/` 2` duplicate filenames.

---

### Task 3: Normalize raw-schema frontmatter (the core repair)

**Files:** rewrites frontmatter of the remaining raw-schema `Main/Knowledge/inbox/*.md` (~31).

- [ ] **Step 1: Compute target frontmatter per note**

For each remaining raw-schema note, apply the **Canonical transformation** table above to produce
the complete target frontmatter object. Worked example (`RBAC like it was meant to be.md`):

```yaml
title: "RBAC like it was meant to be"
url: "https://tailscale.com/blog/rbac-like-it-was-meant-to-be"
source: "article"          # tailscale.com → article
date_added: "2026-04-20"   # from created "2026-04-20T00:00:00.000Z"
summary: "Learn about role-based access control, its use cases and benefits."
status: "inbox"
context: "Imported from Web Clipper backlog"
author: "Avery Pennarun"
tags: []
```

- [ ] **Step 2: Apply with merge:false (drops stale keys, keeps body)**

For each note: `mcp__obsidian__update_frontmatter` with `merge: false` and the full target object.
`merge: false` replaces the entire frontmatter block — so `published`/`created`/`description`
disappear — while the note body is untouched.

- [ ] **Step 3: Verify a sample**

`mcp__obsidian__get_frontmatter` on 3–4 repaired notes (one each: github, tweet, article).
Expected each: has `url`, `source` is a **type** (not a URL), `date_added` matches `YYYY-MM-DD`,
`status: inbox`, `tags: []`, and **no** `published`/`created`/`description` keys.

- [ ] **Step 4: Verify the pollution is gone**

Run `mcp__obsidian__list_all_tags`. Expected: the `knowledge/inbox` tag (was 36) is **gone or near-zero**
(it came from the `tags: ["Knowledge/inbox"]` artifact we stripped).

- [ ] **Step 5: Verify the dashboard renders**

In the Obsidian app, open `Main/Knowledge/knowledge.base` → **Inbox** view. Expected: rows now
populate `url`, `source`, `date_added`, `context` columns (previously blank). This is a manual,
human-eyes check; note it for the user to confirm.

---

### Task 4: Add "Inbox Health" to the index command, then regenerate

**Files:**
- Modify: `chezmoi/private_dot_claude/commands/kb/index.md`
- Regenerate (vault): `Main/_system/index.md`

- [ ] **Step 1: Add the computation step**

In `chezmoi/private_dot_claude/commands/kb/index.md`, in the "Compute stats" area (after step 2),
add:

```markdown
   - **Inbox health:** count notes in `Knowledge/inbox/`; of those, count any still in raw
     Web-Clipper schema (`source` is a URL or `status` missing); compute the oldest inbox note's
     age (today − min `date_added`).
```

- [ ] **Step 2: Add the template section**

In the index markdown template (step 7), insert immediately after the `## Stats` block:

```markdown
## Inbox Health
- **Inbox notes:** N (X still raw Web-Clipper schema)
- **Oldest inbox note:** D days
- Backlog: ✓ clear / ⚠ N awaiting `/kb:process`
```

- [ ] **Step 3: Commit the skill edit**

```bash
git add chezmoi/private_dot_claude/commands/kb/index.md
git commit -m "feat(kb): add Inbox Health section to index"
```

- [ ] **Step 4: Regenerate the live index**

Execute the `/kb:index` procedure against the vault (write `Main/_system/index.md` via
`mcp__obsidian__write_note`).

- [ ] **Step 5: Verify**

`mcp__obsidian__get_frontmatter` on `Main/_system/index.md`.
Expected: `last_updated` is **today** (was `2026-03-31`); the body's Stats inbox count and the new
Inbox Health count match the live `list_directory` count from Task 3.

---

### Task 5: Scope lint to Knowledge/ + add the gap rules

**Files:**
- Modify: `chezmoi/private_dot_claude/skills/kb/references/lint-rules.md`
- Modify: `chezmoi/private_dot_claude/commands/kb/lint.md`

- [ ] **Step 1: Add the scope note to `lint-rules.md`**

Insert directly under the `# Lint Rules` heading:

```markdown
## Scope

All checks run over `Main/Knowledge/` (source notes + `wiki/` + `inbox/`) **only**. Notes under
`Main/Orrery/`, `Main/Archive/`, `Main/Clippings/`, and `_system/` are excluded — their inline
hashtags are not KB taxonomy and must never be counted (this is why a whole-vault `list_all_tags`
shows phantom tags like `active`, `clippings`, `bathroomfan`).
```

- [ ] **Step 2: Extend E05 and add E07 in the Errors table of `lint-rules.md`**

Replace the E05 row, and add E07 below it:

```markdown
| E05 | Duplicate URL **or byte-identical body** across notes (including `inbox/`) | No | Manual — keep one, delete the rest |
| E07 | Inbox note still in raw Web-Clipper schema (`source` holds a URL, or `status` missing) | Yes | Normalize: `url`←`source`, `source`←inferred type, `date_added`←`created`, `status`←`inbox`, strip `Knowledge/inbox` tag, drop `published`/`created`/`description` |
```

- [ ] **Step 3: Add W07 + W08 to the Warnings table of `lint-rules.md`**

```markdown
| W07 | Stale index — `_system/index.md` `last_updated` > 14 days old, or its Stats counts diverge from live counts | Yes | Regenerate via `/kb:index` |
| W08 | Stub body on a reference note (contains "Pending processing" or "Content not yet fetched") | No | Reprocess via `/kb:process` |
```

- [ ] **Step 4: Add I05 to the Info table of `lint-rules.md`**

```markdown
| I05 | Inbox backlog — > 10 notes in `inbox/`, or oldest inbox note > 30 days | Suggest `/kb:process` |
```

- [ ] **Step 5: Mirror the checks into `lint.md`**

In `chezmoi/private_dot_claude/commands/kb/lint.md`:
- Add a `### 0. Scope` note before "Gather data" with the same Knowledge/-only restriction.
- Under "ERRORS", add: `**E07 inbox-raw-schema**: Inbox note with `source` = a URL or no `status` field — repairable by the normalization in E07.`
- Extend the E05 line to: `**E05 duplicate-url**: Same URL — or byte-identical body — across notes, including `inbox/`.`
- Under "WARNINGS", add `**W07 stale-index**` and `**W08 stub-body**` with the descriptions above.
- Under "INFO", add `**I05 inbox-backlog**`.
- In the `/kb:lint fix` auto-fixable list, add: `**E07**: normalize raw Web-Clipper schema (see transformation in lint-rules.md)` and `**W07**: regenerate the index via /kb:index`.

- [ ] **Step 6: Commit the lint edits**

```bash
git add chezmoi/private_dot_claude/skills/kb/references/lint-rules.md chezmoi/private_dot_claude/commands/kb/lint.md
git commit -m "feat(kb): scope lint to Knowledge/ and add schema/index/backlog rules"
```

---

### Task 6: Deploy and final verification

**Files:** deploys repo skill edits to `~/.claude/` via chezmoi.

- [ ] **Step 1: Apply chezmoi**

Run: `just chezmoi-apply`
Expected: `commands/kb/index.md`, `commands/kb/lint.md`, `skills/kb/references/lint-rules.md`
updated under `~/.claude/`. (Diff-preview first with `just chezmoi-diff` if unsure.)

- [ ] **Step 2: Run the lint to confirm the cleanup**

Execute `/kb:lint` against the vault. Expected report:
- **E07 inbox-raw-schema: 0** (all normalized in Task 3).
- **W07 stale-index: 0** (regenerated in Task 4).
- No phantom tags (`active`/`clippings`/`bathroomfan`) in any tag check (scope fix).
- **I05 inbox-backlog**: flags the ~31 inbox notes as awaiting `/kb:process` — this is **expected
  and correct**; full processing is Phase 3, not Phase 0.

- [ ] **Step 3: Report Phase 0 outcome**

Summarize to the user: notes normalized, duplicates removed, index freshness restored, dashboard
rendering, new lint guardrails live. Confirm the inbox is now clean inputs for Phase 1/3.

---

## Self-review notes

- **Spec coverage:** Implements spec §9 Phase 0 (repair stranded notes, fix index staleness, scope
  lint to Knowledge/) and the relevant §8 integrity rules (dedup, schema-mismatch detection,
  index-staleness, backlog-age, stub-body). Synthesis-trigger changes are intentionally deferred to
  Phase 4; full inbox processing to Phase 3.
- **Not in scope (by design):** fetching content, generating real summaries, assigning taxonomy
  tags, filing notes out of inbox, renaming files to kebab-case — all Phase 3 (processing).
- **Reversibility:** only Task 2 is destructive and it is user-gated; frontmatter rewrites are
  non-destructive to bodies; skill edits are version-controlled.
```
