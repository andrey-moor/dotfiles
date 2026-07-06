---
type: design-spec
project: knowledge-base
status: draft
created: 2026-07-06
---

# KB Hardening & Consolidation Wave — Design

**Goal:** Fix everything the 2026-07-06 external review surfaced (P1+P2+P3): make the
pipeline crash-proof and self-reporting, wire hybrid retrieval into the default search
verb, decouple retrieval quality from the weekly ritual, make the topic layer
trustworthy, collapse three organizational axes into one hierarchy (areas → topics), and
end the wave with a fully backfilled, deduped, re-embedded, migrated corpus — "clean and
nice by the end."

**Inputs:** `docs/kb-review-pass-b.md` (evidence-grounded review; every finding cited to
file/line or live measurement) and `docs/kb-design-independent.md` (the independent
Pass-A yardstick). This spec assumes their findings; it does not restate the evidence.

**Architecture:** No architectural change. Evolve the existing in-repo `kb-engine`
(files-as-truth Obsidian vault, SQLite cache at `~/.local/state/kb-engine/`, jina-v3
local embeddings, hybrid RRF search, launchd pipeline) plus the `~/.claude` kb skill and
commands. Six dependency-ordered phases, each independently shippable.

**Execution model:** Implementation plan is written for **subagent-driven execution by
Opus** — per-phase task lists, test-first tasks, exact file paths, per-task commits.
Phases land sequentially on `main`; the user reviews at phase boundaries.

---

## 1. Context (what's broken, one paragraph)

The weekly launchd pipeline has been crashing silently on iCloud dataless-file reads
(`OSError: EDEADLK` in `vault.py:43`; no per-file or per-step error handling; last exit
status 1; log empty since Jun 22). Because the digest regenerates last, it froze at
last-good numbers ("inbox 0 / proposals 0" vs. reality 12 / 28) — v1's documented death
pattern reproduced inside v2's anti-dormancy machinery. Independently: `/kb:search` never
calls the engine (hybrid search unreachable from the muscle-memory verb); topic
assignment is measurably miscalibrated (5 of the biggest topics have median member-cosine
below the global 0.55 threshold; label-text anchors never re-anchor on members;
`is_primary=1` on all 671 membership rows); there is no eval instrumentation; enrichment
(summaries/why) waits on the weekly ritual; ~460 June-imported notes are summary-stubs
with no content; the vault (the truth layer) has no versioning; and taxonomy tags, topics,
and areas form three overlapping aboutness axes.

## 2. Success criteria

1. The pipeline **cannot die silently**: every run leaves a run record; the digest always
   regenerates with a status header (even on failure); `/kb:*` commands preflight digest
   age; `kb-engine doctor` verifies the full chain.
2. **Probe recall@5 ≥ 85%** on `_system/probes.yaml`, and no phase regresses it (eval is
   an exit criterion of every phase).
3. A new capture is **semantically findable within a day** with zero human touch
   (auto-enriched summary + why threaded into the embedding).
4. **One aboutness hierarchy**: every note has an area; topics are the only fine
   vocabulary; two-level taxonomy tags are retired; cross-cutting tags remain as facets.
5. **Fresh-machine bootstrap** is documented and `doctor`-verified (secrets, launchd,
   model cache, vault path).
6. End-of-wave corpus state: content-backfilled (minus permanently-dead links), near-dups
   merged, re-embedded once on final inputs, thresholds derived on final geometry, axes
   migrated over all of it.

## 3. Principle amendments (recorded in `_system/DECISIONS.md`)

1. **The invariant narrows to decisions.** "The LLM proposes, never silently decides"
   governs *decisions* (topic/area membership, filing, merges, taxonomy changes).
   *Descriptions* (summaries, proposed-why, title repair) may be auto-drafted unattended:
   always `provenance: auto`, never overwriting human text, flipped to `confirmed` when
   touched in review.
   - **Signed-off exception (coarse tier):** *area* assignment may auto-apply at high
     confidence — coarse, reversible, low-stakes — marked `provenance: auto` and listed
     in the digest for spot-veto. Topic assignment stays gated.
2. **Dependency direction is law.** Interfaces (Claude Code, Cowork, future MCP) consume
   the engine; the loop completes headless with the CLI alone. Cowork gets no
   load-bearing role anywhere. The cron LLM is a direct Anthropic API call from the
   engine — not Cowork, not `claude` headless.
3. **No unverified health claims.** Digest and `status` always carry last-run timestamp
   and result; stale or failed state announces itself.

## 4. Decisions resolved during brainstorming

| Fork | Decision |
|---|---|
| Scope | Everything from the review: P1 + P2 + P3, including axes consolidation |
| F1 Enrichment | **LLM-in-cron for descriptions** — Haiku via direct API, flag-gated (`ANTHROPIC_API_KEY`); engine fully functional without a key |
| F2 Content | **Full text in the note** (`## Content`, capped ~3–5k words); one-shot backfill drain during the wave |
| F3 Axes | **One hierarchy: areas → topics**; taxonomy categories become areas; two-level tags become topics or retire; cross-cutting tags stay as facets |
| F4 iCloud | Fix in place (tolerant walk + mtime prefilter + `.icloud` awareness) **plus** ops recommendation: disable "Optimize Mac Storage" on behemoth. Vault stays on iCloud |
| F5 Digest | Digest v2: status banner, bounded review batches, 3 resurfacings, health line, synthesis nudges |
| Cowork | **No dependency.** Read/review MCP server and the Cowork cockpit are out of this wave (next wave, consuming the hardened engine) |
| Fresh machine | Secrets via `~/.config/kb-engine/secrets.env` (0600), sourced by Nix launchd wrappers, provisioned once from 1Password, `doctor`-checked, runbook documented |

## 5. The ordering chain (the "clean by the end" guarantee)

Corpus-level operations run strictly downstream, each on the final output of the
previous. Nothing downstream is computed from stub-era data:

```
enrich (empty summaries, why, titles)      Phase 3
  → backfill content (ONE-SHOT drain)      Phase 3
    → single re-embed (rebuild)            Phase 3 exit   ← eval-guarded
      → near-dup sweep + merges            Phase 4 start
        → re-anchor topics + derive        Phase 4
          per-topic thresholds
          → classify + axes migration      Phase 5
```

The weekly backfill batch survives only as the ongoing mechanism for future stragglers.
Threshold derivation happens only after the re-embed (the why-threading shifts the cosine
scale — known from the topic-layer-v2 spec).

---

## 6. Phases

### Phase 0 — Triage (half a day; stops active bleeding)

- **User action:** revoke/rotate the Fastmail API token (it transited a chat session);
  place the new token in the secrets file.
- **Vault versioning:** `git init` the vault; `.gitignore` for `.obsidian/workspace*`,
  `.DS_Store`, `.trash/`; initial commit; nightly launchd auto-commit job (Nix-declared:
  `git add -A && git commit -m "auto: <date>"`, no-op when clean). Local-only repo;
  iCloud + Time Machine remain the redundancy layer. Makes every future engine write
  diffable and the Phase-5 cutover revertible.
- **DB concurrency:** `PRAGMA journal_mode=WAL` + `busy_timeout=5000` at connect in
  `store.py`.
- **Tourniquet:** minimal per-file `try/except OSError` in the sync walk
  (`vault.py`/`sync.py`) — skip + count + log path, never abort.
- **Unfreeze:** run `kb-engine pipeline` manually; verify the digest reflects reality
  (~12 inbox / 28 proposals).

**Exit:** manual pipeline green; digest truthful; vault under git; DB WAL-mode.

### Phase 1 — Measure (1 day; safety net before anything changes retrieval)

- **Probe suite:** `_system/probes.yaml` in the vault (private, files-as-truth). Format:
  `query`, `expect` (list of acceptable note paths, any-of), optional `k` (default 5).
  Seeded with the 8 Pass-B probes; grown from every future real-world retrieval miss.
- **`kb-engine eval`:** runs all probes, reports recall@5, MRR, per-probe pass/fail,
  `--json`. Run in the weekly tier; result line lands in the digest (Phase 2 hook).
- **Telemetry:** `events` table (ts, kind: search|open|capture, query, top_path,
  hit_rank). `kb-engine search` logs locally by default; the kb skill logs note-opens
  after search.
- **Front-door wiring:** `/kb:search` calls `kb-engine search --json` first; Obsidian-MCP
  full-text demoted to a tag-filter supplement; SKILL.md "find/search" triggers route to
  the engine. `/kb:surface` unchanged (context mode).

**Exit:** eval baseline recorded (8/8 today); search verb uses hybrid; events accumulate.

### Phase 2 — Pipeline hardening (1–2 days; the outage class dies)

- **Sync walk, iCloud-proof:**
  - mtime+size **prefilter** (stat-only pass; store both in `notes` via
    `_ensure_column`); read/hash only candidates whose stat changed.
  - **`.icloud` awareness:** evicted placeholders (`.*.md.icloud`) map back to their note
    path; the note counts as *evicted* — DB row kept (no delete/re-embed churn), count
    reported in digest/status.
  - Per-file errors skip + collect into `SyncStats.failures` (formalizes Phase 0, with
    tmpdir unit tests simulating `OSError` and placeholder files).
- **Run record:** `runs` table (id, command, tier, started_at, finished_at, counts JSON,
  errors JSON, ok). Written by pipeline, sync, imports, backfill. `status` shows last run
  + age + result.
- **Digest always writes:** pipeline steps individually wrapped; digest generation moves
  to `finally`; digest gains a header block: `last_run`, `result: ok | FAILED (step:
  error)`, per-step counts, evicted/skipped/failed files.
- **Daily/weekly split:** `pipeline --tier daily` = sync → import-mail → enrich (Phase 3)
  → digest. `--tier weekly` = daily + topics (apply/discover/suggest) + eval + backfill
  batch. Two Nix-declared launchd agents (daily 08:00; Monday 09:00, replacing the
  current weekly agent).
- **Dead-man's switch in the human path:** kb SKILL.md preflight — on any `/kb:*`
  invocation, check digest `last_run`; if > 8 days or FAILED, surface a banner before
  doing anything else.
- **`kb-engine doctor`:** digest age, launchd agents loaded, secrets file present &
  0600, model cache present, DB integrity (`PRAGMA integrity_check`), vault reachable,
  git auto-commit fresh. `--json` for scripting.
- **Ops note (user, once):** disable "Optimize Mac Storage" for iCloud Drive on behemoth;
  code hardening remains as defense in depth.

**Exit:** kill-test passes — a vault with an unreadable file and an `.icloud` placeholder
still produces a truthful digest with a FAILED/degraded banner and a run record.

### Phase 3 — Enrichment + content (2 days; retrieval stops waiting for Monday)

- **LLM adapter (`kb_engine/llm.py`):** minimal httpx client for the Anthropic Messages
  API; model configurable (default Haiku); key from `ANTHROPIC_API_KEY`. Absent key ⇒
  enrichment step skips with a report line — engine remains fully functional offline.
  `FakeLLM` for tests; real calls never in unit tests.
- **Auto-enrichment (daily tier):** for notes with empty summary, or `provenance: auto`
  whose content hash changed: draft 2–3 sentence summary; propose a one-line `why` (from
  content + channel context); repair slug-garbage titles. Write with `provenance: auto`.
  Human text is never overwritten (non-empty summary without an auto mark = human ⇒
  hands off). June-review summaries are treated as human-confirmed. `/kb:review` flips
  provenance to `confirmed` on touch.
- **`why` threaded into retrieval:** `embedding_text` = title + summary + why-when-
  present.
- **Content policy (all channels):** full readable text persists in the note under
  `## Content` (capped at 4,000 words by default + truncation marker with the URL). Mail already does
  (trafilatura); clipper template keeps its clip body; `/kb:process` amended to *keep*
  fetched content rather than replacing the body with the summary. FTS picks it up
  automatically (`fts_text` already indexes full body).
- **Backfill (`kb-engine backfill-content`):** targets summary-stub notes (heuristic:
  body < ~500 chars, has URL, fetchable source type). Engine-side fetch reusing the
  trafilatura path; per-item tolerant; polite per-domain rate limiting; permanent
  failures marked `content: unavailable` after 3 attempts (tweets/dead links accepted as
  stubs). **One-shot supervised drain during this phase**; the weekly batch handles
  future stragglers. Coverage % reported in the digest.
- **Single re-embed:** after enrichment + backfill land, one `rebuild`; eval must hold.
- **Fresh-machine provisioning:** `~/.config/kb-engine/secrets.env` (0600) holding
  `FASTMAIL_API_TOKEN` + `ANTHROPIC_API_KEY`; Nix launchd wrappers source it; `doctor`
  verifies; bootstrap runbook in the engine README (clone → `just switch` → create
  secrets.env from 1Password → `kb-engine rebuild` → `doctor` green).

**Exit:** a note captured today is auto-summarized and semantically findable tomorrow
with zero human touch; backfill drained; corpus re-embedded once; eval ≥ baseline.

### Phase 4 — Topic layer made trustworthy (1–2 days)

- **Near-dup sweep first:** one-shot gist-cosine report (> 0.95) → merge flow in
  `/kb:review` (merge is a decision — human confirms; union whys, archive the twin with
  `duplicate_of:`; nothing lost). Permanent search-time suppression of > 0.97 twins
  (keep the best-ranked).
- **Member-centroid re-anchoring:** manual topics recompute anchors as the mean of
  confirmed member vectors after every apply; label-text anchor only as cold-start for
  topics with < 3 members; anchor provenance stored (`label | members`).
- **Per-topic thresholds:** derived from each topic's member-similarity distribution
  (starting formula `high = max(0.45, p25(member sims))`, `secondary = high − 0.08`;
  tuned at plan time via a dry-run distribution report).
- **Real primary/secondary in the pipeline:** retire sticky-single mode; weekly tier runs
  `assign` with primary + ≤ 2 secondaries; `is_primary` semantics fixed; the borderline
  band lands in a persisted **`review_queue` table** (note, candidates, scores, reason),
  surfaced in digest + `/kb:review`.
- **Real-vector fixtures:** ~50 actual jina-v3 embeddings committed as `.npy` (+ source
  texts); threshold/assignment/near-dup tests run against real geometry, torch-free.

**Exit:** re-running `assign` reproduces (or improves) current coverage without manual
tag loss; borderline queue populated; eval ≥ baseline; fixture-backed tests green.

### Phase 5 — One hierarchy: areas → topics (2–3 days)

- **Model:** ~9 **areas** seeded from today's taxonomy categories (AI, Dev, Infra, Arch,
  GameDev, Business, Career, Home, Personal). Every topic carries `area:`. Every note
  gets an area (always) + topics (when confident). Cross-cutting tags (Reference,
  Tutorials, Inspiration, Tools) stay as orthogonal facets. Projects remain a future
  axis.
- **Classifier (`kb_engine/topics/classify.py`, flag-gated Haiku):** input = note (title
  + summary + why) + the areas/topics registry; output = candidates with confidence.
  Used for: (a) borderline-queue resolution *proposals* (human confirms — decisions stay
  gated); (b) **area** assignment — auto-applied at high confidence per the signed-off
  coarse-tier exception, `provenance: auto`, digest-listed for spot-veto; embedding
  similarity to area centroid is the no-LLM fallback.
- **Migration (existing machinery: Jaccard diff, retag, apply, render):**
  1. Map the 24 topics → areas.
  2. Jaccard-diff taxonomy tags ↔ topics → per-tag **disposition table**
     (becomes-topic / maps-to-existing / retires-to-area-only). **One human review
     session approves it.**
  3. Mass retag applies it: add `topic/<slug>` + area tags, drop two-level taxonomy
     tags.
  4. `_taxonomy.md` v2 = the areas + topics registry (generated section + governance
     tables).
  5. `tags.base` views → area filters; `knowledge.base` unchanged.
  6. MOCs gain per-area index pages; `_unfiled-by-category` → `_unfiled-by-area`.
  Single cutover; revertible via the git-versioned vault; dry-run diff before apply.

**Exit:** every note has an area; one aboutness vocabulary governs; Bases + MOCs browse
by area/topic on Mac and iPhone; eval ≥ baseline.

### Phase 6 — UX polish (1–2 days; the loop gives value back)

- **MOC render:** members as `[[note]] — summary one-liner`; scores + c-TF-IDF keywords
  into a collapsed `<details>` block; per-area index pages (topics with counts).
- **Digest v2 sections, in order:** status banner (run health) → this week (new notes by
  area/topic, one-liners) → review queue **bounded to top ~10 by confidence** (totals are
  a health metric, never a wall) → **3 resurfacings** (related-to-current-work via recent
  search/capture vectors from `events`; aging never-opened; anniversary) → health line
  (eval recall, topic coverage, backfill %, evicted count) → synthesis nudge (top-2
  candidates with ready `/kb:synthesize` invocations).
- **One overview truth:** deterministic stats fold into the digest; `_system/index.md`
  becomes a thin generated pointer (digest + topics index).
- **Housekeeping:** split `cli.py` (1,156 lines) into thin CLI + command modules; module
  docstrings for `topics/*`; remove the vestigial multi-chunk embedding path; README +
  runbook polish.

**Exit:** digest reads in ≤ 5 minutes and contains at least one thing worth clicking;
MOCs read as maps, not debug dumps; repo passes its own file-size rule.

---

## 7. Testing & quality bar (every phase)

- TDD per repo standard; suite green at each phase exit (319 existing tests + new).
- **Eval probes must not regress at any phase boundary** — the meta-guard for the wave.
- iCloud failure modes unit-tested with tmpdir fixtures (simulated `OSError`, `.icloud`
  placeholders).
- LLM paths tested via `FakeLLM`; no real API calls in unit tests; real-model checks stay
  behind `KB_RUN_INTEGRATION=1`.
- Real-vector `.npy` fixtures (Phase 4) for all geometry-sensitive logic.
- Immutability + file-size rules per repo CLAUDE.md.

## 8. Risks

- **Backfill coverage is partial** (tweets/paywalls/dead links) — accepted; reported as a
  % in the digest; clipper covers hostile sources going forward.
- **Haiku summary quality** — spot-checked via provenance flips in review; probes catch
  semantic drift; summaries are regenerable.
- **Cosine-scale shift from why-threading** — thresholds derived only after the single
  re-embed (§5 ordering).
- **Two launchd tiers double the "is it running" surface** — covered by `doctor`, the
  digest banner, and the skill preflight.
- **Axes cutover churn** — git-versioned vault + dry-run disposition table + single
  approved apply.
- **Secrets on disk** — 0600 file, local-only, documented rotation; strictly better than
  the status quo (token previously transited a chat).

## 9. Out of scope (this wave)

- Cowork read/review MCP server and the Live-Artifact cockpit (next wave; consumes the
  hardened engine).
- The projects axis (references + inspiration lanes).
- Moving the vault off iCloud; Obsidian Sync.
- ANN indexing, rerankers, embedding-model changes (revisit at ~5k notes or on eval
  regression).
- Multi-user anything.

## 10. References

- `docs/kb-review-pass-b.md` — the review this wave implements (findings cited to
  file:line and live measurements).
- `docs/kb-design-independent.md` — Pass-A independent design (the yardstick).
- Prior specs: `2026-06-15-knowledge-base-v2-design.md`,
  `2026-06-19-kb-topic-layer-v2-design.md`,
  `2026-06-19-kb-capture-cowork-rich-topics-design.md`.
