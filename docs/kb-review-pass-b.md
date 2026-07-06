# Pass B — Review of kb-engine against the independent Pass-A design

*Grounded in: all three specs; firsthand reads of `search.py`, `chunking.py`, `sync.py`,
`embeddings.py`, `vault.py`, `config.py`; three read-only sweeps (topics/store/security,
importing/pipeline/tests, skills/vault artifacts); live DB introspection; live launchd/log
forensics; and 8 retrieval probes + a topic-anchor measurement run against the real index.
Yardstick: `docs/kb-design-independent.md` (Pass A, written before reading any of this).*

---

## 1 · Verdict

**The approach is sound — and I can say that with unusual confidence, because designing
independently I converged on ~70% of it, and the live probes empirically vindicate the
core retrieval bet.** Files-as-truth Markdown + a rebuildable SQLite cache outside the
vault, local jina-v3 embeddings, hybrid BM25∪cosine with RRF, dedup at ingest, an
LLM-curated taxonomy you classify into with clustering demoted to gap-finding, a weekly
digest-driven ~5-minute review, no GUI, Claude as the interface — that is, near-verbatim,
the system I designed before looking. The v1-failure acceptance query ("how to give an AI
assistant long-term memory") now returns exactly the right notes in 0.15s.

**The build is not healthy where it matters most: the operational loop.** Verified live
today:

- The weekly pipeline is **crashing silently** (`launchctl` last exit status 1;
  `OSError: [Errno 11] Resource deadlock avoided` from `vault.py:43 read_bytes()` on an
  iCloud dataless file; no per-file error handling, so one bad read aborts the whole run).
- Because the digest is regenerated *last*, a crashed run **freezes the digest at
  its last-good numbers**: it currently reports "Inbox backlog: 0 · proposals: 0" while
  **12 files sit in `Knowledge/inbox/`** and **28 proposed topics sit in the DB**. The
  pipeline log has been empty since Jun 22.
- This is, item for item, the failure v2's own spec diagnosed in v1 ("the index is stale
  and silently wrong — '0 inbox' while 36 sit there") — reproduced *inside the machinery
  built to prevent it*. Re-dormancy isn't a risk; its mechanism is live right now.

Second-order problems, also verified: the default search verb `/kb:search` never calls
the engine (0 references to `kb-engine` — it still runs the Obsidian-MCP keyword search v2
was built to replace); topic assignment is measurably miscalibrated (5 of the biggest
topics have median member-cosine *below* the 0.55 threshold); there is no way to measure
whether retrieval works (I had to build the probe run myself); and enrichment (summaries,
why, classification) is coupled to the weekly human ritual, so retrieval quality degrades
exactly when the ritual lapses.

**Bottom line: keep the architecture, fix the loop.** Nothing foundational needs a
rewrite. The P1 list is: make the pipeline crash-proof and self-reporting, wire hybrid
search into the front door, add the eval harness, re-anchor topic assignment, and decide
the enrichment-timing fork.

---

## 2 · Diff — Pass-A design vs. the build

### Convergences (independent validation — neither of us copied the other)

| Choice | Both designs |
|---|---|
| Markdown files as truth; SQLite as disposable cache **outside the vault** (`~/.local/state/kb-engine/`) | ✓ |
| Local embedding model, zero marginal cost, offline | ✓ (his jina-v3 · 1024d, task-typed queries/passages — better specified than my sketch) |
| Hybrid retrieval: BM25 (FTS5) ∪ cosine, RRF fusion, no rerank until proven needed | ✓ (his k=60) |
| Dedup at ingest: canonical URL + channel-native id (message-id) | ✓ |
| Stable, human-approved topic vocabulary; **clustering demoted to a proposal/gap engine** | ✓ — he arrived by evidence (keyword-mash labels, ~43% unclustered), I by principle; same endpoint |
| Weekly digest + ~5-min batched human review; machine does mechanics unattended | ✓ |
| "Nothing is ever lost"; unfiled explicitly surfaced, never dropped | ✓ |
| No bespoke GUI; Claude Code as interface; Obsidian as read surface (Bases render natively on iPhone) | ✓ |
| Idempotent, regenerable rendered artifacts (MOCs, digest, `_taxonomy.md` with stable markers) | ✓ |
| launchd-scheduled automation | ✓ |

### Divergences — adjudicated

1. **Content policy: summary-as-body vs full-content-in-note.** Most of the corpus
   (the June import) has 2–3-sentence summaries as the entire body; "FTS indexes the full
   body" is therefore vacuous for the majority. My design kept full extracted text in
   every note as the recall floor and link-rot insurance. **Adjudication: I'm right about
   the floor, but his position is closer to defensible than it looks** — his
   summary-anchored *vectors* are correct (my probes confirm gist retrieval works, and his
   Phase-1 dilution analysis was sound), and his Web Clipper front door *does* capture full
   rendered DOM going forward. The gap is the missing policy: fetched/clipped content is
   sometimes persisted (older notes, e.g. the Reddit SEO playbook — which is why the
   body-detail probe "MaxSim operation" found the ColBERT note), sometimes discarded (June
   bulk). **→ TWEAK: adopt an explicit rule — full text (capped) always persists in the
   note under `## Content` (or is at minimum FTS-indexed); vectors stay summary-anchored.**
2. **Enrichment timing: review-gated vs automatic.** His invariant "the LLM proposes,
   never silently guesses" is applied to *everything*, so summaries/why/classification wait
   for `/kb:review`. My design auto-enriched at ingest and reserved gating for decisions.
   **Adjudication: his invariant conflates decisions with descriptions.** A topic
   assignment is a decision (gate it — he's right, and my Pass A had the same human veto).
   A summary is a description: auto-drafting one, marked `provenance: auto`, loses nothing
   and decouples retrieval quality from ritual discipline. The 280-char body fallback
   currently papering over missing summaries is thin (16 notes embed on title+280 chars
   today; every new capture does until reviewed). **→ TWEAK (see fork F1).**
3. **Default retrieval path.** `/kb:search` = Obsidian-MCP full-text; hybrid search is
   only reachable via `/kb:surface` or the CLI. This isn't a design divergence — his spec
   agrees with me ("Claude Code is the engine entry point... semantic search") — it's a
   wiring defect. **→ REDO the wiring (trivial).**
4. **Assignment mechanism: label-text vector anchors + one global threshold.** Manual
   topics embed `"{label}. {description}"` as their centroid (`cli.py:626`) and never
   re-anchor on confirmed members. Measured today: median member-cosine for the 5 biggest
   topics is *below* the 0.55 auto-assign bar (indie-hacking 0.531, prompt-engineering
   0.520, rust-tooling 0.504, saas-startups 0.484, cooking-coffee 0.483), while narrow
   anchors like claude-code-tips would grab 44 notes ≥0.55 against 12 members. A single
   global threshold over label-text anchors is simultaneously too strict and too loose.
   My design classified via LLM against the vocabulary; his capture spec plans the same
   (Haiku for the ambiguous middle) but it's unbuilt. **→ TWEAK: re-anchor manual topics on
   member centroids after each apply (the machinery exists — discovered topics already use
   member centroids), add per-topic thresholds (e.g. a percentile of the member-similarity
   distribution), and ship the planned classifier for the middle band.**
5. **Cadence: weekly monolith vs frequent-cheap + weekly-judgment.** Weekly is right for
   topics/digest; but sync+dedup+inbox-count are cheap and serve capture (dedup answers,
   fresh digest). One Monday crash currently costs a whole week of everything. **→ TWEAK:
   split into a daily cheap tier (sync, inbox count, digest header) and the weekly topic
   tier.**
6. **Organizational axes.** He has curated taxonomy tags (`AI/Agents`) + topics
   (`topic/ai-agents`) + areas (0 live) + planned projects. I had one vocabulary + facets.
   His two-tier coarse/fine defense ("that's coarse-vs-fine, not redundancy") is coherent
   on paper, but in production all 24 topics are *manual*, several duplicate taxonomy
   subcategories almost 1:1, and areas are empty. Three navigation vocabularies for 585
   notes is over-structure. **→ TWEAK toward consolidation (fork F3).**
7. **Evaluation.** He has none — no probe set, no search logging, no way to know whether
   the KB "works" beyond anecdote. Pass A made this the fitness function. **My position
   stands; his omission is the single cheapest high-leverage gap.** Today's 8 probes are
   the seed set.
8. **Digest content.** His digest is counts + a wall ("File 275 unfiled note(s)" +25
   listed). Mine was resurfacing-centric (related-to-now, aging gem, anniversary) + a
   health line. A 275-item guilt wall as the sole action item is the v1 killer wearing a
   new shirt; his own spec set the bar at ~5 min. **→ TWEAK: value-out digest.**
9. **The `why` field.** Same bet in both designs; his Phase-0 evidence (forgotten 5/6 at
   clip time → review-time backfill primary) is *better grounded* than my capture-time
   optimism — his adaptation wins. But today `why` is written by importers and used by
   nothing (not in `embedding_text`, not in ranking, not in classification — all planned,
   unbuilt). Ceremony without payoff. **→ finish the thread or stop collecting.**
10. **iCloud robustness.** I designed single-writer + append-only inbox but did *not*
    anticipate dataless-file reads crashing a full-vault walk; he didn't either (no
    `.icloud`/error handling in `sync.py`/`vault.py`, confirmed no tests). His build now
    owns the evidence. **→ REDO the sync walk (see P1).**

### What his build has that my design lacked

- **In-browser capture (Obsidian Web Clipper)** — captures the already-rendered, authed
  DOM, obviating the fetch tier entirely (tweets/402s, t.co, paywalls, JS). Phase-0-proven
  on Mac+iPhone. Strictly better than my server-side fetch for hostile sources; I'd adopt it.
- **The projects axis with References + Inspiration lanes** (retrieval-seeded, accrual via
  why, pin/mute; inspiration = mid-similarity, cross-topic, diversity-sampled). A genuinely
  novel retrieval mode my design didn't have — it operationalizes his actual north-star use
  case ("I decided to build a game — show me everything"). Worth building.
- **Jaccard taxonomy diff + proposals table with stable markers** — clean governance UX.
- **319 torch-free tests** (FakeEmbedder/FakeClusterer discipline, gated integration) —
  engineering rigor beyond my sketch.
- **Cowork Live-Artifact cockpit, validated by probe** (host-side MCP reached from the VM;
  live refresh confirmed) — a plausible richer ops surface than my CLI+skills-only stance.
- **inbox-check as a schema gate** with actionable dup/schema reporting.

### What my design has that his lacks

- **Eval probes + usage telemetry** (searches/week, hit-rate, recall@5 in the digest).
- **Automatic enrichment** decoupled from ritual (auto summaries at ingest).
- **A consistent full-content persistence policy** (recall floor + link-rot insurance).
- **Resurfacing** as the digest's centerpiece (his has zero resurfacing today).
- **Near-dup vector dedup** — his URL+message-id dedup can't see re-clipped/re-imported
  content twins; probe results showed `-2` duplicate pairs in 3 of 8 top-5 lists.
- **A dead-man's switch** on the automation (my digest health line carried "index
  freshness"; honestly, my design also lacked an explicit watchdog — his outage taught me
  that lesson too. Both designs need it; only his is currently bleeding from it.)

---

## 3 · Decision audit

| # | Decision | Verdict | Reasoning (→ alternative & blast radius where REDO) |
|---|---|---|---|
| 1 | **Bespoke engine** vs Smart Connections / Copilot / Readwise / Karakeep / claude-mem | **KEEP** | The moat is the governed taxonomy + multi-channel capture + agent-native ops, which nothing off-the-shelf gives over files-as-truth. Smart Connections would have delivered in-vault semantic search for ~zero build, but none of the loop. Probes prove the bespoke core earns its keep. |
| 2 | **Local jina-v3, 1024d, task-typed** | **KEEP** | Probes green; 0.15s/query; free; task-typed query/passage encoding is correctly used (`embeddings.py:52-61`). Pin + `rebuild` = drift insurance. Vendor the HF weights dir into backups (single external dep). CC-BY-NC weights: fine for personal use. |
| 3 | **Files-as-truth; SQLite cache outside vault; lossless rebuild** | **KEEP** | Convergent with Pass A and with his own most-saved sources (file-over-app). |
| 4 | **SQLite BLOBs + FTS5, brute-force cosine, no ANN** | **KEEP** (tweak at scale) | Right for 585–5k. The per-row Python loop (`search.py:18-22`) should become one `mat @ q` before ~5k; ANN only at ~50k. |
| 5 | **Hybrid RRF k=60, no reranker** | **KEEP** | All 8 probes hit in top-5; complexity stays out until an eval set says otherwise. |
| 6 | **Summary-anchored single vector per note** | **KEEP** | Empirically works (incl. cross-vocabulary probes); his dilution analysis was right. Contingent on #7 and on threading `why` in when present. |
| 7 | **Summary-as-body / no content-persistence policy** | **TWEAK** | Persist full clipped/fetched text in the note (capped) or at minimum FTS-index it. Detail-level recall ("MaxSim") only worked where a rich body happened to survive. Cheap: policy + `/kb:process` change, no engine change. |
| 8 | **LLM-curated taxonomy you classify into; clustering demoted to gap-finder** | **KEEP** | The load-bearing bet, independently reached in Pass A, justified by his own cluster-quality evidence. |
| 9 | **Label-text anchors + global 0.55 threshold for manual topics** | **REDO (small)** | Measured miscalibration both directions (§2.4). → Member-centroid re-anchoring post-apply + per-topic thresholds; ship the planned classifier for the ambiguous band. Blast radius: `topics add`/`apply`/`assign` + a re-render; ~1–2 days. |
| 10 | **Weekly LLM-free deterministic pipeline** | **TWEAK** | Split daily-cheap (sync, dedup, digest header) from weekly-judgment (topics). Keep determinism for decisions; see fork F1 for descriptions. |
| 11 | **Enrichment gated on `/kb:review`** (summaries/why backfill) | **TWEAK** | Decision/description split: auto-draft summaries + proposed-why marked `provenance: auto`; review confirms instead of authors. Retrieval stops depending on the ritual. |
| 12 | **Multi-channel capture → one inbox contract (Clipper / JMAP mail / Things)** | **KEEP** | Best-engineered part of the build (normalize_url, message-id, cache∪inbox dedup, trafilatura bodies, 1.4s idempotent runs). Unify: Things stubs omit `why`/`project` fields that mail writes. |
| 13 | **Capture-everything / nothing-lost** | **KEEP** (with counterweight) | Right instinct; collector's fallacy is real but the fix is ranking + resurfacing + near-dup merge, not gating capture. Add cosine-based near-dup suppression (dupes visible in live results). |
| 14 | **iCloud vault substrate + read-everything sync walk** | **REDO (the sync walk, not the substrate)** | Dataless reads crash the pipeline today (`vault.py:43`, EDEADLK; zero error handling; no `.icloud` awareness; no mtime prefilter — every run reads all 585 files). → Per-file try/except (skip+report, never abort), mtime+size prefilter before hashing, optional `brctl download` prewarm, alternatively disable "Optimize Mac Storage". Blast radius: `sync.py` + `vault.py` + tests; ~a day. |
| 15 | **Weekly digest as the nudge** | **TWEAK** | Right artifact, wrong content: add last-run timestamp + status banner (esp. FAILED), cap the unfiled wall, add 2–3 resurfacings (related-to-current-work / aging-unopened / anniversary), report search usage once telemetry exists. |
| 16 | **No evaluation instrumentation** | **REDO (add; small)** | You cannot trust — or tune — what you can't measure, and trust is the anti-dormancy currency. → `probes.yaml` + `kb-engine eval` (recall@5/MRR) + a search-log table; digest health line. Seeded by today's 8 probes. ~1 day. |
| 17 | **GUI-less; Claude Code + planned Cowork MCP cockpit** | **KEEP** (guardrail) | Cockpit stays an optional layer; the loop must stay headless-complete (it is today — keep it that way; claude.ai-authed MCPs are absent in cron, which his spec already noted). |

**Constraints I am assuming fixed that he could lift:**
- **iCloud as sync substrate** — liftable three ways: turn off "Optimize Mac Storage"
  (eviction is the crash trigger), move the vault to Obsidian Sync or git; each dissolves
  the P1 rather than engineering around it.
- **"The engine is LLM-free"** — a chosen principle, not physics; fork F1 relaxes it for
  descriptions only.
- **Weekly human review actually happening** — the design should survive months of absence
  (auto-enrichment + graceful digest degradation), not assume attendance.
- **Things as a live channel** — it's legacy/backlog-only per spec; retiring it removes a
  schema variant.
- **Flat `Knowledge/`** — fine at 585; year-partition before ~5k for iCloud/Obsidian sanity.
- **jina-v3 forever** — `rebuild` makes the model swappable; treat it as pinned, not fixed.

---

## 4 · What his own vault says about KBs — and whether the build listens

From the Pass-A corpus reading (his curated sources on this exact topic):

- **File-over-app, explicit inspectable memory, BYOAI** (Karpathy wiki-gist + Farzapedia
  thread, saved 3×) — **the build honors this fully**: plain Markdown, native tags, MOCs,
  Bases; the SQLite cache is disposable. Strongest alignment.
- **"The LLM is the librarian; you rarely edit the wiki manually"** — **half-honored.**
  Organization is machine-rendered, but enrichment and synthesis wait for a human ritual;
  wiki output is idle again (2 articles, both pre-import, 7+ qualifying topics — the same
  idleness v2's own review flagged in v1). The build is more human-gated than his sources
  advocate.
- **Hybrid, token-frugal, infra-light retrieval** (claude-mem's SQLite hybrid +
  progressive disclosure; ColBERT explicitly as a *reranker option*; GraphRAG-vs-vector
  skepticism) — **honored**: RRF hybrid on SQLite, no graph DB, no reranker. My probes
  say that restraint was correct.
- **Karpathy's "no fancy RAG needed at this scale"** — both he and I overrode this on
  mechanism (the index exists) while keeping agent-over-files UX; the probe results justify
  the override (garbage tweet titles + 585 life-wide notes need the index).
- **Curation over dump** (commonplace-book thread) — **tension**: the 496-URL bulk import
  (boots, wreaths, bathroom fans beside ColBERT) is a dump by his sources' standard. The
  build's counterweights (topics, by-category, digest) mitigate; near-dup merge and
  resurfacing would close the loop. The corpus's own meta-evidence (duplicate `-2/-3`
  saves, empty `context:` fields) argued for exactly the dedup-with-answer-back and
  effortless-why designs both Pass A and his capture spec landed on.

---

## 5 · Per-pillar findings

### Approach

- **A1 · The central bet is validated.** Taxonomy-you-classify-into + clustering-as-
  gap-finder matches my independent design and survived contact with real data (clustering
  alone produced keyword-mash labels and ~43% residual — capture spec, Motivation).
  All 8 live probes hit. *Suggestion:* none — keep. **P3 (record it in DECISIONS.md).**
- **A2 · Anti-dormancy is designed but not closed-loop.** The pipeline can die silently
  and the digest freezes at rosy numbers — happening now (launchctl exit 1; log empty
  since Jun 22; digest: "inbox 0/proposals 0" vs reality 12/28). Every safeguard lives
  *inside* the failing unit. *Suggestion:* dead-man's switch outside the pipeline: digest
  gets a `last_run`/status header written even on failure (wrap steps); `/kb:*` skill
  preflight checks digest age and screams if >8 days; optionally a `launchd` success-touch
  file checked by `kb:lint`. **P1.**
- **A3 · Buy-vs-build: defensible, now prove it stays cheap.** The differentiators
  (capture channels, governance, agent-native ops) justify bespoke; the risk is carrying
  cost (bus factor: Nix+uv+launchd+iCloud+Claude-specific). *Suggestion:* keep the engine
  boring (it is: 4.4k lines, stdlib+4 deps); document a "rebuild from vault on any machine"
  runbook. **P3.**
- **A4 · The `why` bet is right, the thread is unfinished.** Phase-0 evidence (5/6
  forgotten) correctly demoted clip-time why to bonus; but today `why` is persisted by
  importers and consumed by nothing (`embedding_text` = title+summary only,
  `chunking.py:15-25`; no ranking boost; classifier unbuilt). *Suggestion:* thread why into
  embedding text + (later) classification, or stop writing empty `why:` fields. **P2.**
- **A5 · Review burden violates its own ~5-min budget.** The digest's single action item
  is "File 275 unfiled note(s)". That's a guilt wall, not a nudge — the documented v1
  killer. *Suggestion:* digest proposes a *bounded* batch (e.g. "10 highest-confidence
  classifications to confirm"), plus resurfacings; unfiled total becomes a health metric,
  not a todo. **P1-adjacent (pairs with A2 fix).**

### Implementation

- **I1 · Pipeline fragility + zero observability (the outage).** No try/except around
  steps (`pipeline.py:65-98`); sync aborts on the first unreadable file (`vault.py:43`);
  no run record anywhere (agent-verified: no `last_synced_at`, nothing in DB; empty logs).
  *Suggestion:* per-file error tolerance in the walk (collect+report failures in
  SyncStats); pipeline always writes digest with status banner; record `pipeline_runs`
  (started, finished, counts, errors) in the DB; surface in `status`. **P1.**
- **I2 · Assignment miscalibration (measured).** §2.4 table: 5/24 topics have median
  member-cos < high(0.55); narrow anchors over-grab 3–6×. Root cause: anchors =
  `embed("label. description")` (`cli.py:626`), never re-anchored on members; one global
  threshold. Note also `is_primary=1` on all 671 membership rows — the spec'd
  primary/secondary model isn't operative (pipeline uses sticky single-topic mode:
  `sticky.py:51-52` forces `secondary=high=low`). *Suggestion:* recompute manual-topic
  centroids from confirmed members after each apply; per-topic thresholds from the member
  similarity distribution; then let the pipeline use real `assign` (primary+secondary)
  instead of sticky-single. **P1 for topic-layer usefulness.**
- **I3 · `/kb:search` bypasses the engine.** `grep -c kb-engine search.md` → 0; the skill
  routes "find notes about X" to Obsidian-MCP full-text — precisely the ranking v2's spec
  documented as failing. Hybrid search hides behind `/kb:surface`/CLI. *Suggestion:*
  `/kb:search` calls `kb-engine search --json` first, MCP full-text as fallback/filter
  layer. **P1, ~an hour.**
- **I4 · DB concurrency is unguarded.** No WAL, no `busy_timeout` (store init:
  `PRAGMA foreign_keys` only, `store.py:90`). Monday-9am pipeline vs an MCP server query
  vs an `import-mail` run = `SQLITE_BUSY` crashes. *Suggestion:* `journal_mode=WAL` +
  `busy_timeout=5000` at connect. **P2, one line.**
- **I5 · Near-dup content duplicates pollute results.** 3 of 8 probe top-5 lists contained
  `-2` twin pairs (URL dedup can't catch different-URL/same-content or pre-dedup legacy
  imports). *Suggestion:* one-off vector near-dup sweep (cos>0.95 → merge/archive) + a
  search-time suppression of >0.97 twins. **P2.**
- **I6 · Test discipline is real but geometry-blind.** 319 tests, torch-free fakes, 2
  gated integration tests — good. But FakeEmbedder vectors are hash-random: thresholds and
  cluster behavior are never exercised against real embedding geometry — which is exactly
  where I2 slipped through. *Suggestion:* commit a small fixture of ~50 real jina vectors
  (`.npy`) and test assignment/thresholds against it (no torch needed at test time). **P2.**
- **I7 · Security posture: good, one loose end.** Token via env only (`cli.py:837-841`),
  no secrets in repo; path traversal guarded (`render.py:240-243`, `apply.py:122-126`,
  `filing.py:19-34`); FTS input quoted (`store.py:79-82`); no subprocess use. The loose
  end: the Fastmail token that transited a chat session earlier — still valid per project
  memory. *Suggestion:* revoke/rotate it (1Password → new token; env unchanged). **P1
  hygiene, one minute.**
- **I8 · Minor:** `cli.py` at 1,156 lines (his own 800 cap); `chunk_note`/multi-chunk
  machinery vestigial post-summary-anchoring (`sync.py:55` writes exactly one chunk);
  unchanged-note metadata writes on every sync (585 commits/run, `sync.py:74-76`);
  `topics/*` modules lack docstrings. **P3 housekeeping.**

### UX & compile→use loop

- **U1 · The loop works when it runs — and the artifacts mostly earn their place.**
  Bases views render natively incl. iPhone; taxonomy browse is clean; `## Related` blocks
  with reasons are exactly right (88% coverage per index). Keep.
- **U2 · MOCs are link dumps with leaked debug.** Topic MOCs list `[[path]] (0.77)` plus
  c-TF-IDF keywords like "elevenlabs, agent, netflix, agency, **blaho**" (an author's
  surname) — machine internals where a reader wants orientation. Frontmatter summaries
  exist for 569/585 notes and aren't shown. *Suggestion:* render each member as
  `[[note]] — <summary one-liner>`; keywords/scores behind a `<details>` or dropped. **P2,
  render-only change.**
- **U3 · Two overview artifacts, one stale.** `index.md` (says 125 notes,
  `last_updated: 2026-06-15`) vs digest (585-corpus era). The stale one is the more
  polished. *Suggestion:* fold index generation into the pipeline (deterministic parts) or
  mark it deprecated; one source of overview truth. **P2.**
- **U4 · Synthesis is idle again.** 2 wiki articles (Mar 31 / Apr 5), 7+ candidates,
  `synthesis-candidates` CLI exists but nothing nudges. His own v2 review called wiki the
  best months-later surface. *Suggestion:* digest lists top-2 synthesis candidates with a
  one-tap `/kb:synthesize` suggestion. **P2.**
- **U5 · How does he actually find things?** Today: `/kb:search` (keyword, degraded),
  Obsidian native search (over summary-bodies — thin), `/kb:surface` (good but
  discovery-hidden), Cowork MCP (probe-only). After I3, conversational search-with-
  citations becomes the primary path, which both his sources and my Pass A design say is
  the killer app. **Covered by I3.**

### Evaluation & scale

- **E1 · No instrumentation → add the harness.** `probes.yaml` (query → expected paths),
  `kb-engine eval` reporting recall@5/MRR, run on model/threshold changes + monthly; log
  every search (query, top hit, clicked/opened if knowable) to an `events` table; digest
  health line reports both. Seed with today's 8 (all currently pass; the ColBERT
  body-detail probe is the canary for the content-policy fix). Every future real-world
  retrieval miss becomes a probe. **P1, ~a day.**
- **E2 · Scale path is fine with two pre-commitments.** 5k: matrix-ize cosine (one
  `mat @ q`), batch per-note commits, year-partition `Knowledge/`. 50k: ANN (sqlite-vec /
  HNSW), UMAP/HDBSCAN discovery goes minutes-scale (acceptable weekly; or cluster only the
  residual, which it already does), review burden is the real wall — which the classifier
  (I2) and auto-enrichment (F1) are the answer to, not more human minutes. iCloud walk
  cost is O(corpus) per run until the mtime prefilter lands (I1). **P2 notes, no action
  now.**
- **E3 · Model/embedding drift.** jina-v3 pinned; `rebuild` is the escape hatch (~minutes
  at 585, ~½–1h CPU at 50k). Vendor the HF snapshot into backups; record `model_name` in
  the DB (it's in config only). **P3.**
- **E4 · Backup/recovery is the un-designed pillar.** The vault — the *truth* — is on
  iCloud only: no git, no versioned snapshots; a bad `apply`/`file` run or an iCloud sync
  accident is unrecoverable beyond APFS/Time Machine luck. The engine is rebuildable; the
  truth isn't. *Suggestion:* `git init` the vault (private; obsidian-git or a launchd
  `git commit -am` nightly). This also makes render/apply runs *diffable* — pure upside
  for a files-as-truth system. **P1-adjacent (cheap, protects everything else).**

---

## 6 · 🔀 Brainstorm forks (his call — options, no forced pick)

**F1 — Where does enrichment run?** (the deepest fork)
- *(a) LLM-in-cron for descriptions:* pipeline drafts summaries/why for new notes, marked
  `provenance: auto`; review confirms. + Retrieval never starves; − relaxes "deterministic
  LLM-free engine" (API key in launchd, nondeterminism in cron).
- *(b) Strictly-human (status quo):* + invariant purity, zero unattended API calls;
  − retrieval quality tied to ritual attendance; new captures search poorly until Monday.
- *(c) No-LLM auto-enrichment:* embed full clipped content (chunk vectors alongside the
  gist vector) so unreviewed notes are findable by their text, summaries stay human-paced.
  + deterministic, offline; − partially reverts the Phase-1 dilution decision (needs the
  two-vector design: gist for topics, chunks for recall).

**F2 — Content persistence policy.**
- *(a) Full text in the note* (capped ~3–5k words, `## Content`): grep/Obsidian-search
  floor, link-rot insurance; − bigger vault, iCloud sync weight.
- *(b) Summary-body + full text only in FTS* (store it in SQLite, not the note): search
  works, notes stay clean; − violates files-as-truth (content lives only in the cache).
- *(c) Status quo* (keep whatever the clipper happened to capture): zero work; − recall
  floor stays accidental.

**F3 — Axis consolidation.**
- *(a) One vocabulary:* promote topics to be the taxonomy (hierarchy = area/topic); tags
  become `topic/*` only. Cleanest mental model; migration touches every note (mass retag —
  cheap by design).
- *(b) Keep two-tier, wire them:* explicit taxonomy↔topic mapping table; digest flags
  drift. Preserves both; permanent double bookkeeping.
- *(c) Taxonomy = facets only* (source/domain), topics = the only aboutness vocabulary.
  Closest to Pass A; medium migration.

**F4 — iCloud substrate.**
- *(a) Fix in place:* error-tolerant walk + mtime prefilter + `brctl download` prewarm.
- *(b) Turn off "Optimize Mac Storage"* on behemoth: eviction (the crash trigger) largely
  disappears; costs disk.
- *(c) Move the vault off iCloud* (Obsidian Sync / git-based): best engine ergonomics,
  touches his iPhone workflow — biggest life change, only worth it if (a)+(b) disappoint.

**F5 — Digest delivery & flavor.** Vault-note only (status quo) vs + Claude session-start
echo vs + email. And: does he want resurfacing (my Pass-A bet) or strictly operational
counts? Taste decision; resurfacing is what makes the digest *give* value rather than ask
for work.

**F6 — Cowork cockpit timing.** Build the read/review MCP server now (spec Phase 1) vs
harden the loop first (P1s above) and keep the probe. Given the pipeline is currently
dead, sequencing the loop first is my recommendation — but the cockpit is his stated
excitement, and motivation is an anti-dormancy input too. Honest trade-off.

---

## 7 · Top findings, ranked

1. **The pipeline is dead and nothing told him** — iCloud dataless read → EDEADLK →
   unhandled abort → digest frozen at "all healthy" since ≤Jun 29 (12 inbox items + 28
   proposals invisible). Fix = error-tolerant walk + always-write digest-with-status +
   run record + skill-preflight staleness check. *This is v1's documented death mechanism
   running inside v2.* (**P1**, ~1–2 days)
2. **`/kb:search` doesn't use the engine** — the #1 v2 deliverable (hybrid semantic
   search) is not wired into the verb his muscle memory will use. One-hour fix, immediate
   daily payoff. (**P1**)
3. **No eval harness** — retrieval quality is unmeasured; my 8 probes (all passing) are a
   free seed set; add `kb-engine eval` + search logging + digest health line so trust is
   earned by numbers, not vibes. (**P1**, ~1 day)
4. **Topic assignment is measurably miscalibrated** — label-text anchors + global 0.55
   leave the 5 biggest topics unable to auto-claim their own median member; re-anchor on
   member centroids + per-topic thresholds; ship the planned classifier. Until then the
   topic layer under-delivers its navigation promise (275 unfiled). (**P1**)
5. **Enrichment is coupled to the ritual (F1)** — decide the decision/description split so
   summaries (and thus vectors) never wait for Monday-plus-human. Any of F1's three
   options beats the status quo. (**P1/P2 fork**)
6. **The vault has no backup/versioning** — the truth layer is one iCloud accident from
   unrecoverable; `git init` + nightly commit also makes every engine write diffable.
   (**P1-adjacent, ~an hour**)
7. **Digest is a guilt wall, not a nudge** — bounded review batches + resurfacings +
   health/last-run banner; this is the artifact that decides whether the ritual survives.
   (**P2**)
8. **Revoke the exposed Fastmail token** — read-only, but it transited a chat; rotation is
   one minute. (**P1 hygiene**)

---

## Flagged as unverified / not run

- The exact "106 vs 310" figure from the brief — I could not reproduce 106 from the DB;
  I verified the *mechanism* instead (median member-cosine below threshold for 5 topics;
  score histogram: 49 memberships <0.5, 133 in the 0.5 band).
- The 3m29s cold-walk timing — superseded by stronger evidence (today's EDEADLK crash);
  I did not re-run a full `sync` against the crashed-state DB mid-review.
- `/kb:review` end-to-end (LLM flow) and the Cowork Live-Artifact refresh — described
  from specs/skills and Phase-0 records, not re-executed.
- Whether the Jun 29 Monday run also failed (log empty since Jun 22; only the latest
  exit status is observable) — bounded as "last full success ≤ Jun 29".
- `import-mail` live JMAP behavior — reviewed from code/tests only (it's also covered by
  prior session records as live-tested).
