# KB Hardening Phase 6 — UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The loop gives value back — digest v2 (this-week, bounded queue, 3
resurfacings, health line, synthesis nudge), MOCs that read as maps, one overview
truth, a thin split CLI — **and the threshold-contraction fix first**, before the
next scheduled weekly run compounds the shed.

**Architecture:** Evolves `kb-engine/` in place. New `commands/` package (cli.py
split); `notes.date_added` column feeds time-based digest sections; growth-gated
threshold re-derive stops the p25 contraction loop; `topics/areas.py`-style retirements
for the vestigial multi-chunk path.

**Tech Stack:** unchanged (Python 3.12, click, sqlite3, numpy, pytest, uv).

## Global Constraints

- **Eval gate:** recall@5 1.00 (8/8) at every task/phase boundary. Current MRR ~0.66.
- **TDD; suite green before each commit** (`cd kb-engine && uv run pytest`). Current:
  493 passed, 2 deselected (permanent integration gates).
- **No LLM/network in unit tests**; FakeLLM/FakeEmbedder/FakeClusterer.
- **Files-as-truth; nothing lost; decisions human-gated**; vault writers use
  `vault.load_post`/`write_post_atomic`.
- **Digest determinism:** the body below `## Status` must be reproducible for fixed
  inputs — time-based sections take an explicit `today: date | None` parameter
  (pipeline passes the real date; tests pass a fixed one; None skips those sections).
- **Frozen dataclasses; functions ≤50 lines; files ≤800 lines** — this phase FIXES the
  cli.py exception (1,541 lines → thin CLI + command modules, each ≤800).
- **Vault path** `/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main`
  (quote it); **DB** `~/.local/state/kb-engine/kb-engine.db` (`immutable=1` ad-hoc).
- **Commit per task**, conventional commits, no attribution footer.

## Plan-time live data (2026-07-10, post-Phase-5)

- **Threshold contraction (P5 exit finding, drives Task 1):** `high = p25(member
  sims)` puts each topic's bottom quartile below its own bar by construction →
  observed 332→258 assigned (-22%) in one derive-assign cycle. Weekly cadence would
  contract topics to cores over ~4-6 weeks. Fix chosen: **growth-gated re-derive** —
  a shed can never trigger tightening; growth re-derives healthily. (Freeze-forever
  rejected: anchors keep moving with new members, bars must be able to follow growth.
  Ratchet-down `min(new, old)` rejected: over-inclusion creep.)
- **Secondary-only area hole (P5 minor):** ~55 notes whose only memberships are
  secondaries get no area from either writer (apply = primaries; mop-up = topicless).
- **`date_added` frontmatter is universal** (583/583 root Knowledge notes) — parsed by
  YAML as `datetime.date` objects (stringify on ingest!). Not yet in the store.
- **events table:** 1 search row — resurfacing seeds must combine recent search
  `top_path`s WITH recent captures (spec: "recent search/capture vectors").
- **`chunk_note`/`DEFAULT_CHUNK_TOKENS`/`Config.chunk_tokens`: zero production
  callers** (grep: only config.py's own field + chunking.py definitions + tests).
- **cli.py = 1,541 lines**, 18 top-level commands + the 15-subcommand `topics` group.
- **`_system/index.md`** is a stale hand-schema (2026-06-15, "125 notes") — replaced
  by a thin generated pointer.
- **Content coverage metric for the health line:** derivable NOW via
  `LENGTH(chunks.text)` (FTS text = title+body): % of notes with ≥500 chars.
  Spec's "backfill %" is served by this (notes carrying real content).
- `synthesis_candidates(store, vault_path, min_members=5) -> [Candidate(slug, label,
  size)]` biggest-first exists; `surface.related_to_note(store, note_path, limit)`
  exists; `store.last_run(command)` returns the runs row with `counts` = {step:
  detail-string}.

## File structure

| File | Change |
|---|---|
| `store.py` | `topics.threshold_derived_n` col; `notes.date_added` col; `set_topic_thresholds` gains derived_n; `summaries_for`, `note_dates`, `content_coverage` helpers |
| `topics/thresholds.py` | `persist_thresholds(..., only_grown=False)` growth gate |
| `topics/weekly.py` | persists thresholds with `only_grown=True` |
| `topics/apply.py` | secondary-only area FILL (add-only) |
| `sync.py` | ingest `date_added` (stringified) |
| `topics/render.py` | MOC v3 (summary one-liners + `<details>`); thin `_system/index.md` pointer |
| `importing/digest.py` | digest v2 (rewrite of build_digest) |
| `pipeline.py` | passes `today=date.today()` to write_digest |
| `cli.py` → `commands/` package | split: thin cli + `commands/{_shared,core,reports,topics_cmds,ingest,run}.py` |
| `chunking.py`, `config.py` | remove `chunk_note` / `DEFAULT_CHUNK_TOKENS` / `chunk_tokens` |
| `filing.py` | house I/O swap (latent `content:`-key crash) |
| `README.md` | model + commands refresh |

---

### Task 1: Threshold contraction fix — growth-gated re-derive

**Files:** `models.py`, `store.py`, `topics/thresholds.py`, `topics/weekly.py`;
tests: `test_thresholds.py`, `test_weekly.py`, `test_store.py` (append), `test_cli.py`
(thresholds command help/behavior unchanged — verify only).

**Interfaces:**
- `Topic.threshold_derived_n: int | None = None` (LAST field, defaulted).
- `topics.threshold_derived_n INTEGER` in BOTH `_SCHEMA` and `_ensure_column`.
- `Store.set_topic_thresholds(slug, high, secondary, derived_n)` — the member count
  the derivation saw (existing callers updated; column written).
- `persist_thresholds(store, stats, only_grown: bool = False) -> int`: when
  `only_grown`, write a topic's thresholds ONLY if its stored `threshold_derived_n`
  is None (never derived) OR `stats.n_members > stored threshold_derived_n`
  (strict growth). Returns rows written.
- `weekly_topic_pass` persists with `only_grown=True`. CLI `topics thresholds` keeps
  unconditional persist (the manual reset tool — extend its docstring/help:
  "re-derives unconditionally; the weekly pass only re-derives on member growth").

**The property to test (the actual fix):** two consecutive
`weekly_topic_pass` runs over an unchanged corpus assign the SAME notes — no
quartile shed on the second pass. Plus unit selectivity tests: never-derived
topic → written; shrunk membership → skipped (thresholds AND derived_n unchanged);
grown → re-written with the new derived_n.

Steps: failing store test (roundtrip derived_n; migration backfill on a pre-P6
topics table) → failing thresholds selectivity tests → failing weekly
no-contraction test (seed 2 fixture-vector topics à la `test_weekly.py`'s helper,
run `weekly_topic_pass` twice with `NoiseClusterer`, assert pass-2 `assigned` ==
pass-1 `assigned` AND the assigned note-sets match via `topic_members`) → implement
(model field → schema both places → set_topic_thresholds signature + callers →
persist gate → weekly flag) → full suite → commit
`fix(kb-engine): growth-gated threshold re-derive stops membership contraction`.

**Live note for Task 8:** the live DB's topics already carry post-shed thresholds
with NULL derived_n → first live weekly pass re-derives once more (NULL = never),
THEN freezes. Acceptable: one more bounded shed (~-15%), then stable. To avoid even
that, Task 8 stamps `threshold_derived_n` = current member counts via one UPDATE
before the next run (controller step, listed there).

---

### Task 2: Secondary-only area fill in apply

**Files:** `topics/apply.py`; tests: `test_apply.py` (append).

**Semantics:** notes whose memberships are ALL secondary (no primary anywhere) and
whose best-scoring secondary's topic has an area, AND which currently have NO
`area/*` tag → gain that area tag (append). FILL-ONLY: never replaces an existing
`area/*` (unlike the primary path, which owns/replaces). Primary path unchanged.
Implementation: `_secondary_fill_by_note(store, only_status) -> dict[str, str]`
(best secondary by score desc then slug, only topics with area, minus notes that
have any primary); `_apply_to_note` gains `fill_area_slug: str | None` applied only
when no `area/*` tag present. Keep ≤50 lines via the existing `_with_area_tag`
helper plus a tiny `_has_area_tag(tags) -> bool`.

Tests: secondary-only note gains area; existing `area/*` preserved (fill skipped);
note with a primary elsewhere excluded from fill; idempotent. Commit
`fix(kb-engine): apply fills areas for secondary-only notes (add-only)`.

---

### Task 3: MOC render v3 — maps, not debug dumps

**Files:** `topics/render.py`, `store.py` (`summaries_for`); tests:
`test_render.py`, `test_store.py`.

**Interfaces:**
- `Store.summaries_for(paths: list[str]) -> dict[str, str]` (empty-string rows
  omitted; empty input → {}; mirrors `note_vectors_for`'s IN-clause pattern).
- `_render_topic_moc(topic, members, summaries)` new layout:

```markdown
# <Label>

<one-liner: the topic's keywords sentence — keep the existing `- slug:` line OUT>

## Notes

- [[Knowledge/foo.md]] — First sentence of its summary, truncated ≥120 chars with …
- [[Knowledge/bar.md]]            ← member without a summary: link only

## Also relevant

- [[Knowledge/baz.md]] — …

<details>
<summary>Details</summary>

- slug: `<slug>` · kind/status: manual/active · anchor: members
- keywords: kw1, kw2, …
- scores: foo.md 0.72 · bar.md 0.61 · baz.md 0.48 (secondary)

</details>
```

  One-liner rule: `summary.split(". ")[0]` capped at 120 chars with a `…` marker;
  deterministic. Section rules (primary/secondary/empty) unchanged from today.
  `render_topics` fetches `summaries_for` once over all member paths.

Steps: failing store test → `summaries_for` → failing render tests (one-liner
truncation pinned; no-summary member link-only; `<details>` contains scores +
keywords and the body section does NOT; determinism double-render) → implement →
suite → commit `feat(kb-engine): MOC v3 — summary one-liners, details block`.

---

### Task 4: Digest v2

**Files:** `store.py` (`notes.date_added` col + `note_dates` + `content_coverage`),
`sync.py` (ingest), `importing/digest.py` (rewrite), `pipeline.py` (today param);
tests: `test_store.py`, `test_sync.py`, `test_digest.py` (substantial rewrite),
`test_pipeline.py` (digest still written; new sections tolerated).

**Store/sync plumbing:**
- `notes.date_added TEXT` (both `_SCHEMA` + `_ensure_column`); `upsert_note` gains
  `date_added: str | None = None`; `sync._index_note` passes
  `str(note.frontmatter.get("date_added"))` when present else None (YAML parses
  dates as `datetime.date` — ALWAYS stringify; a malformed value string-ifies
  harmlessly).
- `Store.note_dates() -> dict[str, str]` ({path: date_added}, NULLs omitted).
- `Store.content_coverage(min_chars: int = 500) -> tuple[int, int]` —
  (notes whose chunks text length ≥ min_chars, total notes) via one SQL join.

**`build_digest(store, vault_path, inbox_count, unfiled, status=None, today=None)`
— section order (spec §6 Phase 6):**
1. `## Status` — unchanged (when status given).
2. `## This week` (only when `today` given): notes with `date_added` within 7 days,
   grouped by their `area/*` tag (else "(no area)"), each
   `- [[path]] — summary one-liner` (reuse Task 3's one-liner rule via a shared
   `_one_liner(text)` helper — put it in digest.py and import from render.py, or
   a tiny shared `topics/_text.py`; implementer's call, no duplication). Empty
   week → `_Nothing new this week._`
3. `## Review queue` — EXISTING rendering, already top-10 by confidence + overflow
   line; add the totals line `N awaiting decision` under the header. (Old `##
   Borderline queue` heading renamed → update tests.)
4. `## Resurfacing` (only when `today` given; up to 3 lines, each unique, skip
   gracefully):
   - related-to-recent-work: seeds = up to 5 most recent `events` search
     `top_path`s + the 3 newest captures; first `related_to_note` hit not among
     seeds/this-week → `- [[hit]] — related to what you've been working on`.
     NOTE: `related_to_note` needs no embedder (vector math over the store).
   - aging: the oldest `date_added` note never appearing as any event `top_path` →
     `- [[path]] — captured <date>, never resurfaced`.
   - anniversary: a note whose `date_added` month/day == today's (≥90 days old),
     oldest first → `- [[path]] — one year ago today` (or `N months/years ago`).
   - New store helper for the events side: `Store.event_top_paths(kind="search",
     limit=5) -> list[str]` (most recent first, NULLs skipped).
5. `## Health` — one line:
   `recall@5 <r> · areas <n>/<total> · content <c>% · inbox <i> · unfiled <u> · evicted <e>`
   — recall parsed from `store.last_run("pipeline")`'s counts["eval"] detail string
   (regex `recall@5 ([0-9.]+)`; absent → `—`); areas = the existing notes-with-area
   count; content = `content_coverage` percent (0 decimals); evicted parsed from
   counts["sync"] (`(\d+) evicted`; absent → `—`). Unfiled count LINKS the MOC:
   `unfiled [<u>](_system/topics/_unfiled-by-area.md)` → actually use a wikilink:
   `unfiled <u> → [[_system/topics/_unfiled-by-area]]`. The old `## Unfiled notes`
   25-item list is REMOVED (the MOC is the list — one overview truth).
6. `## Synthesize` — `synthesis_candidates(store, vault_path)[:2]`, each
   `- /kb:synthesize <slug> — <label> (<size> notes)`; none → omit section.
7. The old `## Summary` + `## Needs review` checklist sections are RETIRED (their
   counts live in Health/queue/This-week now). `count_proposals` stays exported
   (cli `status` uses it — verify).

**pipeline.py:** `write_digest(cfg, store, status=status, today=date.today())`
(import `date` at module top; `write_digest` signature gains + forwards `today`).

Steps: store/sync failing tests → plumbing → digest failing tests (fixed
`today=date(2026, 7, 10)`; cover: this-week grouping + empty; queue totals; all
three resurfacing kinds + graceful absence; health line parsing incl. missing runs
row; synthesize top-2; determinism for fixed inputs; `today=None` → time sections
absent) → rewrite build_digest with small helpers (each ≤50 lines) → adapt
test_pipeline digest assertions → suite → commit
`feat(kb-engine): digest v2 — this-week, resurfacing, health line, synthesis nudge`.

---

### Task 5: One overview truth — thin `_system/index.md`

**Files:** `topics/render.py`; tests: `test_render.py`.

`render_topics` (inside the existing seeded-areas gate) writes `_system/index.md`:

```markdown
---
type: system
generated: true
---
# Knowledge Base

- **Today:** [[_system/kb-digest]] — status, this week, review queue, resurfacing
- **Browse:** [[_system/topics/index]] — areas → topics map
- **Loose ends:** [[_system/topics/_unfiled-by-area]]
- **Vocabulary:** [[_system/_taxonomy]] — areas, topics, facets
```

Exact content above, deterministic, no stats (stats live in the digest — one truth).
`RenderResult` gains `overview_path: str = ""`. Tests: written when areas seeded
(content pinned), NOT written when not seeded (pre-cutover behavior untouched);
idempotent. Commit `feat(kb-engine): _system/index.md becomes a thin generated pointer`.

---

### Task 6: Split cli.py

**Files:** `cli.py` (rewritten thin), new `src/kb_engine/commands/{__init__.py,
_shared.py,core.py,reports.py,topics_cmds.py,ingest.py,run.py}`; tests: NONE
changed — the 493-test suite passing UNMODIFIED is the spec.

**Contract:** `from kb_engine.cli import main` keeps working; every command name,
option, default, help text, and behavior byte-identical. Before starting: grep
`tests/` for `from kb_engine.cli import` — every imported name must remain
importable from `kb_engine.cli` (re-export in cli.py if a helper moved).

**Layout:**
- `commands/_shared.py`: `_build_embedder`, `_build_clusterer`, `_emit`, and any
  constants/imports multiple modules need (moved verbatim from cli.py).
- `commands/core.py`: sync, search, rebuild, status, eval, log-event.
- `commands/reports.py`: dedup-report, synthesis-candidates, surface, digest,
  doctor (whatever reporting/read-only top-level commands exist — derive the exact
  list from cli.py; the grouping rule: read-only reporting).
- `commands/topics_cmds.py`: the ENTIRE `topics` group (all 15 subcommands) —
  defines the `topics` `click.Group` locally.
- `commands/ingest.py`: import-mail, backfill-content, import-things, file,
  inbox-check, capture/url-import commands (the ingestion/mutation family).
- `commands/run.py`: pipeline.
- `cli.py`: the `main` group + `Config` ctx callback (unchanged), then
  `main.add_command(...)` for every command/group imported from `commands/*`.
  No command bodies remain in cli.py.

Pattern per module: commands defined with `@click.command("name")`/`@click.group()`
exactly as today (decorator bodies moved verbatim, only the `@main.command` line
becomes `@click.command`), `@click.pass_obj` unchanged. NO logic edits — this is a
pure move; resist every cleanup temptation (note them in the report instead).

Steps: grep test imports → move family by family, running
`uv run pytest tests/test_cli.py -x -q` after EACH family → full suite → verify
every file ≤800 lines (`wc -l src/kb_engine/cli.py src/kb_engine/commands/*.py`) →
commit `refactor(kb-engine): split cli.py into thin CLI + command modules`.

---

### Task 7: Housekeeping

**Files:** `chunking.py`, `config.py`, `filing.py`, `topics/*` docstrings,
`README.md`, `tests/test_chunking.py`, `tests/test_filing.py`, `tests/test_digest.py`.

- Remove `chunk_note` + the `semantic_text_splitter` import from chunking.py,
  `DEFAULT_CHUNK_TOKENS` + `chunk_tokens` field from config.py (grep first —
  plan-time verified zero production callers; also drop `semantic-text-splitter`
  from pyproject deps if nothing else imports it — grep), and their tests. The
  `Chunk` model stays (store uses the concept).
- `filing.py`: `frontmatter.load(src)` → `load_post(src.read_text())`;
  `dst.write_text(frontmatter.dumps(post) + "\n", ...)` → `write_post_atomic(dst,
  post)` then `src.unlink()` (order preserved: write dst before unlink src). Add
  the `content:`-key regression test (mirror P4.T1's).
- Module docstrings for any `topics/*` module lacking one (check: assignment,
  apply, discover, labeling, clustering, taxonomy, suggest — one honest paragraph
  each where missing).
- `test_digest.py`: drop the dead `topic_slugs` arg passed to registry-only
  `save_areas` (P5.T1 Minor).
- `README.md`: refresh the model section (areas → topics hierarchy, area/topic
  tags, weekly pass, digest v2 sections, threshold growth-gate) + command table
  (new commands since last polish: dedup-report, topics
  reanchor/thresholds/confirm/seed-areas/set-area/propose-migration/migrate) +
  keep the bootstrap runbook intact.
- Commit `chore(kb-engine): retire multi-chunk path, filing house I/O, docstrings, README`.

---

### Task 8: Live pass + phase exit (controller-led)

- [ ] **Step 1: Stamp derived_n live** (prevents the one extra shed — Task 1's
  live note): one `immutable=0` UPDATE via a uv-run script: for each topic with
  non-NULL threshold_high, set `threshold_derived_n` = its CURRENT member count.
- [ ] **Step 2: date_added backfill** (one-shot, no re-embed): script reads each
  indexed note's frontmatter `date_added`, `UPDATE notes SET date_added=?` — the
  sync ingests it for future changes; this covers the unchanged backlog.
- [ ] **Step 3: Live weekly pipeline** (secrets sourced). Verify: `topics` step
  assigned count ≈ previous run (no contraction — THE check); digest v2 renders
  all sections with real data; areas mop-up small; eval 8/8.
- [ ] **Step 4: Render + read test.** `topics render`; read the digest + one MOC +
  index.md top-to-bottom — the ≤5-minute-with-something-worth-clicking exit
  criterion, judged honestly (report what the resurfacing lines actually surfaced).
- [ ] **Step 5: Suite + doctor + file-size rule**
  (`wc -l` over src — all ≤800 now).
- [ ] **Step 6: Vault commit; ledger PHASE 6 EXIT; artifacts →
  `.superpowers/sdd/phase6/`; ff main; memory update; phase-exit summary.**
- [ ] **Step 7 (wave closure, after phase exit): final whole-branch review on
  Fable** — `scripts/review-package $(git merge-base main-at-wave-start HEAD) HEAD`
  … in practice: package `7f59992..HEAD` (the wave's phases 4-6) plus the ledger's
  full carried-Minors list and the standing findings (threshold contraction
  post-fix behavior, secondary-only fill, extraction-quality gate idea,
  doctor-in-daily, refusal-guard asymmetry, exhausted-stub retry, apply YAML churn)
  — dispatched to a FABLE-model subagent per the wave's escalation policy.
