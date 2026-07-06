# KB Hardening Wave — Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the six-phase hardening wave from
`docs/superpowers/specs/2026-07-06-kb-hardening-design.md` — crash-proof self-reporting
pipeline, hybrid search in the front door, ritual-independent enrichment, trustworthy
topic layer, one areas→topics hierarchy, clean fully-migrated corpus at the end.

**Architecture:** No architectural change. Evolve `kb-engine/` (Python, uv), the kb
skill/commands under `~/.claude` (chezmoi-managed via `chezmoi/private_dot_claude/` when
present there), and the Nix launchd wiring in `modules/home/`.

**Tech Stack:** Python 3.12, click, sqlite3 (FTS5 + BLOB vectors), sentence-transformers
(jina-v3, lazy), PyYAML (via python-frontmatter), httpx, pytest, uv, nix-darwin +
home-manager launchd, git.

## Global Constraints

Every task in every phase plan implicitly includes these (from the spec):

- **Eval gate:** from Phase 1 on, `kb-engine eval` recall@5 must not regress at any task
  or phase boundary. Baseline: 8/8 probes.
- **TDD:** every code task is test-first; suite green before each commit
  (`cd kb-engine && uv run pytest`).
- **Provenance rule:** auto-written descriptions always carry `provenance: auto`; human
  text (non-empty field without an auto mark) is never overwritten.
- **No LLM/API calls in unit tests:** use `FakeEmbedder`, `FakeClusterer`, `FakeLLM`;
  real-model checks stay behind `KB_RUN_INTEGRATION=1`.
- **Engine works without secrets:** absent `ANTHROPIC_API_KEY` / `FASTMAIL_API_TOKEN`,
  steps skip with a report line — never crash.
- **Files-as-truth:** vault artifacts are regenerable; the SQLite cache is disposable;
  nothing lives only in the cache (exception: telemetry `events`/`runs`, which are
  observability, not knowledge).
- **Nothing lost:** no capture/note is ever deleted by automation; merges archive with
  `duplicate_of:`; unfiled remains reachable.
- **Frozen dataclasses / immutability** per repo CLAUDE.md; files ≤ 800 lines; functions
  ≤ 50 lines.
- **Vault path:** `/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main`
  (always quote; contains spaces). **DB:** `~/.local/state/kb-engine/kb-engine.db`.
- **Commit per task**, conventional commits (`feat:`/`fix:`/`test:`/`docs:`/`chore:`),
  no attribution footer.

---

## User-action checklist (not agent tasks — surface these to Andrey)

- [ ] **Now (Phase 0):** Revoke + regenerate the Fastmail API token
      (Fastmail → Settings → Privacy & Security → API tokens). Store the new one in
      1Password. The old token transited a chat session.
- [ ] **Phase 2:** Disable "Optimize Mac Storage" for iCloud Drive on behemoth
      (System Settings → Apple ID → iCloud → Drive) — removes the eviction/EDEADLK
      trigger class. Code hardening remains as defense in depth.
- [ ] **Before Phase 3:** Create/confirm 1Password items for `FASTMAIL_API_TOKEN` and a
      dedicated `ANTHROPIC_API_KEY` for KB enrichment; they get copied once into
      `~/.config/kb-engine/secrets.env` (0600) during Phase 3.
- [ ] **Phase 5:** One review session to approve the taxonomy→topics disposition table
      before the mass retag runs.

## Execution protocol

1. Phases run **in order**; each phase is independently shippable and lands on `main`.
2. Phases 0–2 have full bite-sized plans (below). **Phases 3–6 are task skeletons**: at
   each phase boundary, invoke `superpowers:writing-plans` to expand the next skeleton
   into a full plan, using spec §6 for that phase as the source of truth plus any data
   produced by earlier phases (threshold distributions, disposition table).
3. At every phase exit: run the full suite, run `kb-engine eval` against the live vault
   (requires the real model — this one command is allowed to be slow), compare to
   baseline, and report the phase-exit summary to the user before starting the next
   phase.

## Phase index

| Phase | Plan | Status |
|---|---|---|
| 0 — Triage | `2026-07-06-kb-hardening-phase0-triage.md` | ready |
| 1 — Measure | `2026-07-06-kb-hardening-phase1-measure.md` | ready |
| 2 — Pipeline hardening | `2026-07-06-kb-hardening-phase2-pipeline.md` | ready |
| 3 — Enrichment + content | skeleton below → expand at boundary | skeleton |
| 4 — Topic layer | skeleton below → expand at boundary | skeleton |
| 5 — Axes migration | skeleton below → expand at boundary | skeleton |
| 6 — UX polish | skeleton below → expand at boundary | skeleton |

---

## Phase 3 skeleton — Enrichment + content (spec §6 Phase 3)

Ordering inside the phase is load-bearing (spec §5): enrich → backfill (one-shot drain)
→ single re-embed → eval.

- **T3.0 Record the principle amendments.** Append spec §3's three amendments to
  `<vault>/_system/DECISIONS.md` as the next numbered decisions (decisions-vs-
  descriptions with the signed-off area exception; dependency-direction-is-law;
  no-unverified-health-claims), each with a one-line rationale and a pointer to the
  spec. Vault git commit.
- **T3.1 LLM adapter.** Create `kb-engine/src/kb_engine/llm.py`: `class FakeLLM` +
  `class AnthropicLLM` behind a `Protocol` with
  `complete(system: str, user: str, max_tokens: int = 1024) -> str`; httpx POST to
  `https://api.anthropic.com/v1/messages`, model from `Config.llm_model`
  (default `"claude-haiku-4-5-20251001"`), key from `ANTHROPIC_API_KEY`; missing key ⇒
  `LLMUnavailable` exception callers treat as skip. Tests: FakeLLM contract; AnthropicLLM
  request-shape via a mocked transport (httpx `MockTransport`).
- **T3.2 Enrichment step.** Create `kb-engine/src/kb_engine/enrich.py`:
  `enrich_notes(cfg, store, llm, limit) -> EnrichStats` — selects notes with empty
  `summary` or (`provenance: auto` and changed sha); drafts summary (2–3 sentences),
  proposed `why` (one line), repaired `title` for slug-garbage; writes frontmatter with
  `provenance: auto`; never touches non-empty human fields (non-empty summary + no
  provenance mark = human). Wire as a daily-tier pipeline step (skip + report without
  key). Tests: FakeLLM, tmp vault; human-field protection; provenance flip logic left to
  `/kb:review` (skill edit).
- **T3.3 Thread `why` into retrieval.** Modify `chunking.embedding_text` to
  `title + summary + why-when-present`; update tests; do NOT re-embed yet (that happens
  in T3.6).
- **T3.4 Content policy in channels.** `/kb:process` command doc: keep fetched content
  under `## Content` (cap 4,000 words + truncation marker with URL) instead of replacing
  body with summary; verify mail path already body-first (no change); clipper template
  already keeps body (no change). Add a lint check (in `/kb:lint` command doc) for
  summary-stub notes.
- **T3.5 Backfill command.** Create `kb-engine/src/kb_engine/backfill.py` + CLI
  `backfill-content [--limit N] [--json]`: targets notes with body < 500 chars, a
  fetchable `url`, and no `content: unavailable`; fetch via httpx + trafilatura (reuse
  `importing/mail.py`'s extraction helpers — refactor them into
  `kb_engine/extract.py` shared module); per-domain rate limit (≥ 2s between hits to the
  same host); after 3 failed attempts (tracked in frontmatter `content_attempts`), mark
  `content: unavailable`; writes `## Content` section. Records a run in `runs`. Tests:
  MockTransport fixtures (success, 404, timeout), cap/truncation, attempt tracking.
- **T3.6 One-shot drain + single re-embed (supervised, live).** Run
  `backfill-content` repeatedly until drained (report coverage %); then
  `kb-engine rebuild`; then `kb-engine eval` — must hold 8/8. Commit the updated
  `_system/probes.yaml` if paths shifted.
- **T3.7 Secrets + fresh-machine provisioning.** `~/.config/kb-engine/secrets.env`
  (0600) with both tokens; Nix launchd wrappers source it (modify the kb-engine module
  in `modules/home/`); `doctor` check flips from warn to hard for the daily tier;
  bootstrap runbook section in `kb-engine/README.md` (clone → `just switch` → create
  secrets.env from 1Password → `kb-engine rebuild` → `doctor` green).

**Exit:** new capture auto-summarized + findable next day with zero touch; backfill
drained (coverage % reported); corpus re-embedded once; eval ≥ baseline.

## Phase 4 skeleton — Topic layer (spec §6 Phase 4)

- **T4.1 Near-dup sweep.** CLI `dedup-report [--threshold 0.95] [--json]` over gist
  vectors; `/kb:review` merge flow doc (human confirms; union whys; archive twin with
  `duplicate_of:` frontmatter; never delete). Search-time suppression: in
  `search.hybrid_search`, drop results whose vector cosine to a higher-ranked result
  > 0.97. Tests with real-vector fixtures (T4.4).
- **T4.2 Member-centroid re-anchoring.** After `topics apply` (and in weekly tier):
  manual topics with ≥ 3 confirmed members recompute centroid = unit-normalized mean of
  member vectors; store `anchor_source: label|members` column. Tests: fixture vectors;
  cold-start path keeps label anchor.
- **T4.3 Per-topic thresholds.** `topics thresholds --dry-run` prints per-topic member-
  similarity distribution (p25/median/p75) and derived `high = max(0.45, p25)`,
  `secondary = high - 0.08`; persisted per-topic columns; `assign` uses per-topic values
  (global CLI flags become fallback). **Derive from live data only after Phase 3's
  re-embed.** Retire sticky-single in the weekly tier: pipeline runs real
  `assign_notes` (primary + ≤ 2 secondaries, correct `is_primary`); borderline band →
  new `review_queue` table (note, candidates JSON, reason, created_at) surfaced in
  digest + `/kb:review`.
- **T4.4 Real-vector fixtures.** One-time gated script embeds ~50 real notes' texts →
  `kb-engine/tests/fixtures/real_vectors.npy` + `real_vectors.json` (texts/paths);
  threshold/assignment/dedup tests run against real geometry torch-free.

**Exit:** re-running assign preserves-or-improves coverage without tag loss; queue
populated; eval ≥ baseline; fixture-backed tests green.

## Phase 5 skeleton — Axes migration (spec §6 Phase 5)

- **T5.1 Areas registry.** Seed 9 areas from taxonomy categories; `area` column on
  topics; map all 24 topics → areas (proposal table, human approves).
- **T5.2 Classifier.** `kb-engine/src/kb_engine/topics/classify.py` (flag-gated LLM via
  `llm.py` + embedding-similarity fallback): candidates with confidence for (a)
  borderline-queue proposals (human confirms), (b) area auto-assign at high confidence
  (`provenance: auto`, digest-listed). `FakeLLM` tests.
- **T5.3 Disposition table.** `topics diff-taxonomy` output → per-tag disposition
  (becomes-topic / maps-to-existing / retires-to-area-only) rendered for **one human
  review session**.
- **T5.4 Cutover.** Dry-run diff → mass retag (add `topic/`+area tags, drop two-level
  taxonomy tags) → `_taxonomy.md` v2 (areas+topics registry) → `tags.base` area views →
  per-area MOC index pages → `_unfiled-by-category` becomes `_unfiled-by-area`. Vault
  git commit before and after (revert path).

**Exit:** every note has an area; one aboutness vocabulary; Bases/MOCs browse by
area/topic on Mac + iPhone; eval ≥ baseline.

## Phase 6 skeleton — UX polish (spec §6 Phase 6)

- **T6.1 MOC render:** members as `[[note]] — summary one-liner`; scores/keywords into
  collapsed `<details>`; per-area index pages.
- **T6.2 Digest v2:** section order = status banner → this week (by area/topic,
  one-liners) → review queue (top 10 by confidence; totals as health metric) → 3
  resurfacings (related-to-recent-work via `events` vectors; aging never-opened;
  anniversary) → health line (eval recall, coverage, backfill %, evicted) → synthesis
  nudge (top-2 candidates).
- **T6.3 One overview truth:** deterministic stats fold into digest; `_system/index.md`
  becomes a thin generated pointer.
- **T6.4 Housekeeping:** split `cli.py` (1,156 lines) into `cli.py` (thin) +
  `commands/*.py` modules; docstrings for `topics/*`; remove vestigial multi-chunk
  embedding path (`chunk_note` / `DEFAULT_CHUNK_TOKENS`) after confirming no live
  callers; README polish.

**Exit:** digest reads in ≤ 5 min with something worth clicking; MOCs read as maps;
file-size rule passes.
