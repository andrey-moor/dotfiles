---
type: design-spec
project: knowledge-base
status: draft
created: 2026-06-19
---

# KB Topic Layer v2 — Design

**Goal:** Make the KB's topic layer sharper and more navigable by (1) anchoring
embeddings on note summaries instead of full bodies, (2) letting a note belong to
more than one topic, and (3) formalizing a two-tier model where the curated
taxonomy is the always-present coarse category and discovered topics are the fine
layer.

**Architecture:** Incremental evolution of the existing in-repo `kb-engine`
(UMAP→HDBSCAN leaf clustering, SQLite vector cache, hybrid search). No new
services. Three independently-shippable phases.

**Tech stack:** Python `kb_engine` package; local jina-v3 embeddings; sqlite3
(vectors + FTS5); UMAP/HDBSCAN; `python-frontmatter`; click CLI.

---

## Motivation

After the 2026-06 inbox review (486 notes filed) and topic naming (24 active
topics, 310 notes tagged), **275 notes are unfiled** (150 reference, 125
archived). Investigation surfaced three root causes, each addressed by a phase:

1. **Diluted embeddings.** `store.note_vectors()` mean-pools *all* of a note's
   chunks into one vector. A long body smears the note's gist, weakening
   clustering. Most notes (554/583) already embed `title + summary` because
   filing wrote the summary as the body — but this is incidental, not enforced,
   and the ~29 rich-body notes are diluted.
2. **Single-topic assignment.** `assign_notes()` gives each note its single
   *nearest* topic above threshold. A note sitting near two topics (e.g. "AI
   agents in Rust") gets dropped from all but one — and if it's not the nearest
   member of any, it becomes unfiled. ~Half the unfiled reference notes are
   topic-adjacent (Claude Code / AI-agents material that just missed a cluster).
3. **No coarse fallback surfaced.** Unfiled notes already carry taxonomy tags
   (96% of unfiled reference notes do), but nothing presents that coarse tier as
   navigation, so they feel "lost."

## Current state (what exists today)

- **Embedding:** `chunking.py` builds `f"{note.title}\n\n{body}"`, chunks it,
  embeds each chunk. `store.note_vectors()` mean-pools chunk vectors → one
  note vector for clustering/assignment.
- **Search:** hybrid — vector (cosine over note/chunk vectors) ∪ BM25 over
  `chunks_fts` (FTS5 indexes full chunk text = title + body).
- **Topics:** `discover` (UMAP→HDBSCAN leaf) → proposed; `add` → manual active;
  `assign` → single nearest active/proposed topic ≥ `high` (0.55), borderline in
  `[low, high)`; `apply --status active` → writes `topic/<slug>` tags;
  `render` → MOCs in `_system/topics/` + proposals into `_taxonomy.md`.
- **Tags:** two dimensions already coexist on notes — curated **taxonomy** tags
  (`Dev/Rust`, `AI/Agents`, applied at filing) and **topic** tags
  (`topic/<slug>`, applied by `topics apply`).

## The two-tier model

| Tier | Source | Coverage | Role |
|------|--------|----------|------|
| **Coarse — taxonomy** | curated `_taxonomy.md`, applied at filing | ~always | the "category"; fallback navigation; stable |
| **Fine — topics** | discovered clusters, now multi-membership | when a note clusters | precise, emergent, cross-linking |

A note is *always* coarse-categorized (taxonomy) and *optionally* in one or more
fine topics. Taxonomy and topics overlap by design (`AI/Agents` tag ≈ `ai-agents`
topic) — that's coarse-vs-fine, not redundancy to eliminate.

---

## Phase 1 — Summary-anchored embeddings

**What:** Embed `title + summary` as a single vector per note; stop feeding the
body into the vector. Keep FTS indexing the full body.

**Why:** Removes mean-pool dilution → sharper, more homogeneous clusters and
cleaner semantic search. Confirmed by the investigation: long bodies actively
degrade topic quality today.

**Changes:**
- `chunking.py` (or a new `embedding_text()` helper): the text embedded for a
  note's semantic vector becomes `f"{title}\n\n{summary}"`. The summary is read
  from the `summary` frontmatter field.
  - **Fallback when `summary` is empty/missing:** `f"{title}\n\n{body[:280]}"`
    (first ~280 chars of body), so unprocessed/imported stubs still embed
    sensibly.
- **One vector per note** for the semantic side — the summary is short, so no
  chunking/mean-pooling is needed for the vector. `store.note_vectors()` returns
  that single vector directly (no averaging).
- **FTS unchanged:** `chunks_fts` continues to index the full body (and title),
  so keyword/BM25 recall of body detail is preserved. The semantic and keyword
  halves of hybrid search are now intentionally decoupled: vector = gist, FTS =
  detail.
- **Re-sync:** changing the embedding input invalidates the cache; a full
  re-embed runs once (~minutes). Sync's hash already covers frontmatter+body, so
  a summary edit re-embeds that note.

**Trade-off (accepted):** semantic (vector) search of body-*only* detail is lost
for notes whose body says more than their summary (~29 rich notes today).
Keyword (FTS) search of the body still finds it. Acceptable given 95% of notes
are already summary-bodied. If it ever matters, long notes can additionally
contribute body-chunk vectors — out of scope here (YAGNI).

**Data flow:** `sync` → for each changed note: compute `embedding_text` →
embed → store one note vector + FTS full body. `search`/`discover`/`assign`
consume the single note vector.

---

## Phase 2 — Primary + secondary topic assignment

**What:** A note gets one **primary** topic plus up to **2 secondary** topics.

**Assignment (`assign_notes`):**
- **primary** = nearest active topic with cosine ≥ `high`.
- **secondaries** = up to 2 *other* active topics with cosine ≥ `secondary`
  (a new threshold, `low ≤ secondary < high`), ranked by cosine.
- A note with no topic ≥ `high` has no primary → topicless (keeps taxonomy).
- Thresholds (`high`, `secondary`) are CLI-configurable and will be re-tuned
  empirically, because Phase 1 shifts the cosine scale.

**Persistence:**
- `topic_members` gains a `rank` (or `is_primary` boolean) per (topic, note) so a
  note can be a primary member of one topic and a secondary member of others.
- Frontmatter on the note:
  - `topic/<slug>` tag for **every** membership (primary + secondary) — uniform,
    searchable tags.
  - `primary_topic: <slug>` field marking the home topic (single value).

**`apply`:** writes all `topic/<slug>` tags + the `primary_topic` field
(idempotent, gated, active-only — unchanged contract otherwise).

**`render` (MOCs):** each topic's MOC lists its **primary** members under
"## Notes" and its **secondary** members under "## Also relevant", so a note
appears prominently in its home and as a cross-link elsewhere.

**Effect on unfiled:** topic-adjacent notes that single-nearest dropped now
attach as primary or secondary → unfiled set shrinks.

---

## Phase 3 — Two-tier navigation + latent topics (additive)

**3a — "By category" index for topicless notes.**
- A rendered index (e.g. `_system/topics/_unfiled-by-category.md`) groups
  notes that have **no** `topic/` tag by their taxonomy tags (`Dev/Rust`,
  `Personal/Cooking`, …), so the coarse tier is navigable.
- Pure data/render step — no ML. Reads frontmatter tags; lists notes per
  taxonomy category; skips `archived` (low value) or sections them separately.

**3b — Latent-topic surfacing.**
- Re-cluster only the **unfiled residual** at `min_cluster_size=2` to surface
  coherent mini-themes currently below the floor (observed: `AI/RAG`, `Dev/Go`,
  `GameDev`). Emit them as **proposals** (not auto-applied) for the human to name
  via the existing `/kb:topics` flow.
- Implemented as a `discover` option (e.g. `--residual-min 2`) or a dedicated
  `topics suggest` command that clusters only topicless notes.

---

## Testing strategy

- **TDD throughout.** Reuse `FakeEmbedder` (deterministic, torch-free) and
  `FakeClusterer` so unit tests need no ML deps; gate real-model checks behind
  `KB_RUN_INTEGRATION=1` as today.
- **Phase 1:** test `embedding_text()` (summary path, missing-summary fallback,
  empty body); test `note_vectors()` returns the single summary vector (no
  mean-pool); test FTS still indexes full body.
- **Phase 2:** test `assign_notes` returns primary + ≤2 secondaries with correct
  thresholds; test `topic_members` rank persistence; test `apply` writes tags +
  `primary_topic`; test MOC render splits primary/secondary sections.
- **Phase 3:** test the by-category grouping (taxonomy buckets, archived
  handling); test residual re-cluster proposes only from topicless notes.
- Each phase lands with the suite green and is independently shippable.

## Sequencing

1. **Phase 1** (summary embeddings) — foundational; sharpens the signal Phase 2
   relies on. Ships with a one-time re-sync + re-discover to observe the new
   cluster quality.
2. **Phase 2** (primary/secondary) — the main UX change; depends on Phase 1's
   cleaner vectors for good multi-assignment.
3. **Phase 3** (navigation + latent topics) — additive; can ship after 2.

## Out of scope (YAGNI)

- Separate body-chunk vectors for long notes (revisit only if semantic body
  search proves necessary).
- Reworking the taxonomy itself or auto-merging taxonomy↔topics.
- Changing hybrid-search RRF weighting.

## Risks / open questions

- **Threshold tuning:** Phase 1 changes cosine magnitudes; `high`/`secondary`
  defaults must be re-derived from real data before Phase 2 apply. Mitigate with
  a dry-run distribution report.
- **Secondary noise:** capping secondaries at 2 + a `secondary` floor bounds
  clutter; validate on real notes before applying.
- **Re-embed cost:** one-time, acceptable (~minutes for ~600 notes).
