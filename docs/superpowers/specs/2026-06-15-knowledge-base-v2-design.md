# Knowledge Base v2 — Design Spec

**Date:** 2026-06-15
**Status:** Design approved, pending spec review
**Author:** Andrey + Claude (brainstorming session)

---

## 1. Context & motivation

A personal Obsidian knowledge base (KB) was built ~3 months ago to capture 10–20 links/week
and retrieve them later "when context shifts" (e.g. surfacing sprite-generation links months
later during a game project). It is driven by a Claude Code `kb` skill over the Obsidian MCP,
with a manual two-level taxonomy (`Category/Subcategory`), confidence-based tagging, wiki
synthesis, and manual `## Related` graph links.

The user wanted to brainstorm improvements — headline idea: replace manual categorization with
**data-driven clustering that discovers and proposes topics**. A five-dimension multi-agent
review of the current KB was run first to ground the work.

### What the review found (the reframe)

The KB is **not miscategorized — it was abandoned**. The pipeline stopped running ~2026-03-31.
The ~100 processed notes have clean, accurate tags. The two genuinely critical problems are:

1. **Dormant pipeline.** 36 raw Web-Clipper notes piled up in the inbox (wrong frontmatter
   schema, never tagged, with byte-identical duplicates). `/kb:process` only ran on manual
   invocation, and invocation stopped. *Any feature that still needs a manual command inherits
   this failure mode.*
2. **Keyword search fails the core use case.** Re-finding a concept months later (when you've
   forgotten the exact words) doesn't work — `search_notes` ranks by raw token frequency with no
   concept model. Tested query "how to give an AI assistant long-term memory" ranked an
   irrelevant note #1 and missed the relevant ones.

Supporting findings: synthesis is the best "months later" surface but is idle (2 wiki articles
vs 7 qualifying clusters); the index is stale and silently wrong ("0 inbox" while 36 sit there);
no dedup at ingest; lint has gaps that let all of the above report as "healthy." The scary tag
cloud (`active`, `clippings`, `bathroomfan`) is a **measurement artifact** — `list_all_tags`
counts inline hashtags across the *whole* vault (Orrery, web-clip dumps, tweet bodies), not the
KB. Real KB tags are clean.

### Why we are still building clustering (scale changed the math)

The review's original "don't build clustering at 100 notes" verdict was explicitly pegged to
scale. But: a backlog of **~150–400 links** (in Things/Reminders) is about to be imported,
taking the corpus to **~250–500 notes**, growing **~500–1000/year**. That clears the threshold
(~300–400 notes) where embeddings + clustering genuinely earn their keep. The bulk import is
also the ideal forcing function — data-driven topic discovery shines on a large batch.

**Directive for this design:** time and money are not constraints. This is a long-term solution
built right — proper module boundaries, test coverage, durable architecture over expedient hacks.

---

## 2. Goals & non-goals

### Goals
- **Self-sustaining pipeline** — capture → process runs itself; backlog cannot silently build.
- **Dynamic categorization** — always discover and propose topics from the data; user can add
  their own topics that coexist as first-class citizens.
- **Concept-level retrieval** — find things months later by meaning, not exact keywords.
- **Get value out** — re-activated synthesis + proactive surfacing of relevant notes.
- **Files-as-truth** — the Obsidian vault stays authoritative and fully usable directly.
- **Bulk import** the Things/Reminders backlog cleanly (dedup, correct schema).
- **Close the integrity gaps** so the system can never again report healthy while rotting.

### Non-goals
- Not coupling to orrery-engine's internals (see §3).
- Not making the KB an Orrery substrate.
- Not building in-Obsidian UI for engine queries (Claude Code is the engine entry point — §4).
- Not replacing Obsidian as the editing/reading surface.

---

## 3. Architecture

Two layers, with the Obsidian vault as the single source of truth.

```
┌─ KB / UX layer (Obsidian + kb skill, via Obsidian MCP) ──────┐
│  Notes, frontmatter, tags, wiki, ## Related, topic/area MOCs │
│  Owns the human-facing taxonomy + governance + files-as-truth│
└───────────────────────────┬──────────────────────────────────┘
                            │ drives (CLI --json)
┌───────────────────────────▼──────────────────────────────────┐
│  kb-engine  (NEW, small Python CLI — its own project)         │
│  • jina-v3 embeddings (local) · SQLite vector cache           │
│  • HDBSCAN/BERTopic topics  +  agglomerative AREAS layer      │
│  • per-topic centroids → cheap incremental assignment         │
│  • hybrid search (semantic ∪ keyword, re-ranked)              │
│  • correction-stickiness loop (pattern borrowed from Orrery)  │
└───────────────────────────────────────────────────────────────┘

   Obsidian vault = single source of truth.
   kb-engine's SQLite is a rebuildable cache derived from the notes
   (never the other way around).
```

### 3.1 Why an independent `kb-engine`, not orrery-engine

Orrery is a **local Python engine** (`/Users/andreym/Documents/Personal/forge/orrery-engine`)
that already does local embeddings (jina-v3 via sentence-transformers), BERTopic clustering, and
cosine retrieval. An investigation evaluated reusing it. Conclusion: **reuse the libraries and
patterns, not the package.**

The user's long-term vision for Orrery is a **separate app** that integrates with Obsidian via
MCP/continuous export — so the KB must not depend on Orrery's internals. The investigation
independently reached the same conclusion on technical grounds:

- Orrery's substrate is **domain-bound** to meetings/people/interactions at every layer
  (scaffold hardcodes `interactions/`+`people/`; schema is a meeting-extraction contract; the
  embed walk only globs `interactions/`/`people/`/`docs/`).
- Its `doc add` path would **mangle Obsidian notes** — hard-fails without `## Summary`, flattens
  YAML frontmatter into body, embeds `[[wikilinks]]` raw, ignores `#tags`.
- It is **pre-1.0 and mid-migration** toward "SQLite-is-truth, markdown-is-a-projection" — which
  conflicts with Obsidian owning the files.
- It is **flat** (no topic hierarchy) and **cosine-only** (no hybrid search) — the two things we
  most need aren't there.

### 3.2 What we reuse

| Reusable | What it actually is | How we use it |
|---|---|---|
| Local embeddings | `jina-embeddings-v3` via `sentence-transformers`, on-device, no keys, 1024-dim | Use the library directly |
| Clustering | `BERTopic` + `UMAP` + `HDBSCAN`, corpus-adaptive `min_topic_size`, quality gate | Use the libraries directly |
| **Sticky topics** (the real IP) | corrections → semi-supervised UMAP `y`-labels; DB-as-truth, *render-not-append* reconciler | **Borrow the pattern**, reimplement for KB |
| Vector store | float32 BLOBs in SQLite + in-Python cosine (fine to ~5k vectors) | Same approach, our own DB |

Two things the KB adds that Orrery lacks (both additive, both needed):
- **Per-topic centroids** (Orrery persists none) → a new note is assigned to an existing topic by
  cheap cosine-to-centroid, no full re-cluster. Makes "every topic is a vector anchor" (§5)
  directly implementable.
- **Hierarchical areas** + **hybrid search** (§5, §6).

### 3.3 Interop with Orrery (future, clean)

Because both Orrery and the KB integrate through **Obsidian + MCP at the edges** (not shared
engine guts), they interoperate later without coupling: when Orrery ships its MCP/export, the KB
can semantically index Orrery's exported notes like any other source, and Orrery could query the
KB's MCP. Clean product boundaries; integration at the seams.

---

## 4. UX model — both interfaces, one source of truth

Neither interface is "primary." Both operate on the same markdown files.

| What you're doing | Obsidian app (direct) | Claude Code (`kb` skill) |
|---|---|---|
| Read / browse / navigate | ✅ native | — |
| Manually edit a note / fix a tag | ✅ native → engine re-syncs | ✅ |
| Visual graph, daily notes, mobile capture | ✅ native | — |
| Save a link | ✅ share sheet | ✅ "save this" |
| Bulk process inbox, auto-tag | — | ✅ (engine + scheduled) |
| Topic discovery / areas | *appears as notes + tags* | ✅ triggers it |
| Synthesize a wiki article | *appears as a note* | ✅ (engine + LLM) |
| Semantic "find that thing from months ago" | *(results appear as notes)* | ✅ engine entry point |

**Decision: Claude Code is the engine entry point.** Engine-powered actions (semantic search,
re-discover topics, synthesize, process) launch from Claude Code or the scheduled job. Everything
the engine *produces* is written back as native Obsidian artifacts — tags, topic/area index notes
(MOCs you click through), `## Related` links, wiki articles, optionally a Dataview/Bases
dashboard — so the whole structure is browsable in Obsidian with zero plugin.

**Cache coherence nuance:** if you edit a note directly in Obsidian, the engine hashes files and
**re-embeds only what changed** on its next sync (scheduled or on-demand) — same approach as
Orrery's `doctor` sha256 drift check. Files always win; a just-edited note simply isn't in
semantic search for the seconds until the next sync. No data ever lives only in the cache.

---

## 5. Categorization model

The unifying idea: **every topic is anchored by a vector.**
- A **discovered topic** is anchored by its cluster centroid (the engine found a dense region; an
  LLM named it).
- A **user-defined topic** is anchored by the embedding of the name + description you write.

Either way, a note belongs to a topic when it is close enough to that anchor. Adding your own
topic is "discovery in reverse" — you name it, the engine finds its members. Discovered and
manual topics live in one flat namespace, indistinguishable downstream.

### 5.1 The discover/assign loop

```
                    ┌─────────────────────────────────────┐
   all notes ──►    │  embed (jina-v3, local)             │
                    └──────────────┬──────────────────────┘
                                  ▼
   ┌───────────────────────────────────────────────────────┐
   │  ASSIGN to existing topics (user-defined + approved)    │  ← stable
   │     score ≥ high  → auto-tag                            │
   │     borderline    → queue for batched review            │
   └──────────────┬────────────────────────────────────────┘
                  ▼  (notes that fit nothing well)
   ┌───────────────────────────────────────────────────────┐
   │  CLUSTER the residual → LLM names each new cluster      │  ← dynamic
   │     → write to _taxonomy.md Proposals table             │
   └──────────────┬────────────────────────────────────────┘
                  ▼
   You approve / rename / merge / reject  (governance loop)
```

### 5.2 Two-stage structure (topics + areas), both data-driven

The full taxonomy emerges from the same vectors:
1. **Notes → topics:** HDBSCAN (density-based; handles noise/outliers; no fixed `k`) produces
   topics plus an explicit **"unfiled" residual**.
2. **Topics → areas:** **agglomerative (hierarchical) clustering** on topic centroid vectors →
   dendrogram → cut at a tunable height = "areas." One knob dials the whole taxonomy
   coarser/finer and re-previews.

Flat topics are the primary unit; areas are an optional navigation grouping. The strict
two-level `Category/Subcategory` requirement is dropped. Fragmented singletons get absorbed by a
nearby anchor or become small topics. (If BERTopic's wrapper proves cleaner than hand-rolled
HDBSCAN+agglomerative at plan time, use it — it has built-in hierarchical topic reduction. Decide
against the engine's actual capability.)

### 5.3 Fresh restructure proposal (don't seed from existing taxonomy)

We do **not** assume the current taxonomy as the foundation. Instead: cluster the whole corpus
from scratch, generate a proposed structure, and **diff it against the existing taxonomy** side
by side. Existing tags are *input to review* (and nudge the LLM's naming so labels stay familiar)
but do not constrain clustering. The user adopts/merges/keeps per topic. This is the actual
"is there a better structure?" question, answered with evidence.

### 5.4 Stability & governance

- **Sticky anchors:** approved topics (user-defined or discovered) persist. Re-runs re-assign to
  them rather than reshuffling. New topics are only *proposed* from the residual.
- **Correction loop (borrowed pattern):** approve/reject/seed corrections feed semi-supervised
  `y`-labels into the next clustering re-fit, so human decisions survive re-clustering.
- **Files-as-truth, render-not-append:** the canonical topic decisions — approved topics, names,
  merges, manual topics, and the correction log — are persisted in the vault under `_system/`
  (e.g. `_taxonomy.md` plus a topics-state file), human-readable and version-controlled. The
  engine *regenerates* `_taxonomy.md` and the topic/area MOC notes each run from its computation
  **plus** those persisted decisions (never blindly appending), preserving renames and deduping.
  The engine's SQLite holds only derived vectors/assignments and is fully rebuildable from
  {notes + `_system/` topic state} — so unlike Orrery (where `rebuild` destroys corrections), a
  KB rebuild is lossless.
- **Grounded confidence:** "high/medium/low" tagging becomes a real cosine score against the
  anchor, not LLM vibes. Borderline notes batch into one review pass.
- **Unfiled surfacing:** notes matching no topic are explicitly listed ("12 notes don't fit any
  topic yet") — never silently lost; they seed the next discovery run.

---

## 6. Retrieval

Once notes are embedded, the same vectors power retrieval:

- **Hybrid search** — semantic (jina-v3) **unioned with** keyword/full-text, then re-ranked.
  Semantic catches concepts when words are forgotten; keyword nails exact names and error
  strings. (Orrery is cosine-only; the KB adds the keyword + re-rank layer.)
- **Wiki-first** — search hits synthesized wiki articles first, then drills to source notes.
- **Path-scoped** — KB search excludes Orrery / Archive / `_system` / inbox by default (fixes the
  ~35% noise rate).
- **Proactive surfacing** (in scope) — "given what I'm working on now, what's relevant in my KB?"
  This is the original motivation (sprite-gen links surfacing during the game project). Designed
  in from day one; nearly free once vectors exist.

---

## 7. Ingestion & cadence (the "runs itself" part)

Principle: **the machine does the mechanical work unattended; the human makes judgment calls,
batched.**

### 7.1 Bulk import (one-time)

```
Things (local SQLite) / Reminders (EventKit CLI)
   → extract URLs + any note text you wrote
   → normalize URLs, content-hash dedup (review found byte-identical dupes)
   → write proper-schema inbox notes
   → [same pipeline as ongoing, below]
```
Also **repair the 36 stranded raw Web-Clipper notes** in the same pass (wrong schema is why the
index dashboard renders blank).

### 7.2 The processing pipeline — split by what needs a brain

```
DETERMINISTIC (plain script / engine, no LLM, runs unattended)
  drain inbox → fetch content → content-hash dedup → embed (jina-v3)
     → assign to existing topics by similarity
         • score ≥ high   → auto-tag, file, done
         • borderline      → park in a review queue
     → re-cluster the residual

MODEL JUDGMENT (batched, in the scheduled agent)
  name new clusters → write topic Proposals
  draft summaries / wiki updates
  build a digest:  "12 filed · 3 borderline · 2 new topics · 5 unfiled"

YOU (~5 min, your schedule)
  skim digest → approve/rename/merge proposals → resolve borderline queue
```

### 7.3 Automation level — **auto-file, batch-review the rest**

- **Unattended:** fetch, dedup, embed, auto-tag high-confidence, file.
- **Waits for you:** borderline tags, new-topic names, restructure proposals.
- Backlog cannot build silently — the digest plus a fixed lint rule scream if the inbox or review
  queue grows.

### 7.4 Scheduling

Runs weekly. The deterministic half is cheap/safe and can run more often. The LLM-judgment +
digest needs a Claude pass (engine CLI + MCP writes + naming). Concrete mechanism (launchd agent
declared in nix-darwin vs a Claude Code scheduled agent vs `claude` headless) is a plan-time
decision — see §10.

---

## 8. Integrity fixes (the "system can't lie" layer)

Low-effort, high-leverage; ride along with the scheduled run:

- **Index that can't go stale** — regenerated every run; a lint rule fires if it diverges from
  live counts.
- **Lint gap closure** — new rules: inbox note still in Web-Clipper schema; backlog older than N
  days; dedup scan; empty `## Related`; stub bodies ("Content not yet fetched"); index staleness.
  All tag analysis scoped to `Knowledge/` only (kills phantom-pollution noise).
- **Dedup at ingest** — content-hash, so byte-identical dupes never enter again.
- **Synthesis re-activated** — wiki compilation triggers off *topic* size (≥5 notes), keeping
  pace automatically. The 7 currently-qualifying clusters get compiled in the first run.

---

## 9. Phased roadmap

Large enough to decompose. Each phase is independently valuable and gets its own implementation
plan. Dependency-ordered:

- **Phase 0 — Hygiene (quick, independent).** Repair the 36 stranded inbox notes; fix index
  staleness; scope lint to `Knowledge/`. Stops the bleeding before import.
- **Phase 1 — kb-engine core.** New Python project (uv, pinned deps). Local jina-v3 embeddings;
  SQLite vector cache; **correct** Obsidian-native ingest (frontmatter, wikilinks, tags);
  files-as-truth hash-based incremental sync; **hybrid search**; CLI with `--json`. TDD.
  *Delivers semantic search — the #1 retrieval fix — and the substrate for everything else.*
- **Phase 2 — Topic intelligence.** Clustering → topics with centroids; agglomerative areas
  layer (tunable cut); manual vector-anchored topics; fresh restructure proposal + diff vs
  existing taxonomy; sticky correction loop + render-not-append reconciler; incremental
  centroid-cosine assignment; write topics/areas back as Obsidian MOCs + tags.
- **Phase 3 — Ingestion & cadence.** Things/Reminders bulk import (local extraction, dedup);
  scheduled pipeline (unattended deterministic + batched judgment + digest); auto-file +
  review queue; remaining integrity fixes.
- **Phase 4 — Synthesis & proactive surfacing.** Re-activate wiki synthesis (topic-size
  triggers); proactive "relevant to what I'm working on now" surfacing.

---

## 10. Open decisions (resolve at plan time)

1. **kb-engine repo location** — recommend a standalone repo (mirroring orrery-engine's home,
   e.g. `~/Documents/Personal/forge/kb-engine`), installed via nix/uv; dotfiles just wires it up.
   Heavy ML deps (torch/transformers/bertopic/umap/hdbscan, ~3GB) argue against vendoring into
   dotfiles.
2. **Clustering implementation** — hand-rolled HDBSCAN + agglomerative vs BERTopic's wrapper
   (built-in hierarchical reduction). Decide against measured cluster quality on the real corpus.
3. **Scheduler mechanism** — launchd (declarative in nix-darwin) triggering `claude` headless,
   vs a Claude Code scheduled cloud agent. Needs both engine CLI access and MCP writes.
4. **Embedding model** — local jina-v3 (default, durable, private, offline, zero per-item cost)
   vs a hosted embedding API (money is no constraint, but local is the better long-term fit for
   an always-on personal vault). Default: local.
5. **Things vs Apple Reminders** — confirm which app holds the backlog; extraction differs
   (Things local SQLite vs Reminders EventKit/`reminders` CLI).

---

## 11. Testing & quality bar

- TDD throughout (red → green → refactor), 80%+ coverage target per the engine's modules.
- Many small focused files; clear module boundaries (embeddings / store / clustering / areas /
  retrieval / ingest each isolated and independently testable).
- Engine CLI contracts tested via `--json` golden outputs.
- The cache is always rebuildable from the vault — {notes + `_system/` topic state} — via a
  `rebuild` command, losslessly (corrections included). Corruption is never fatal; files are truth.
- Pin orrery-engine-shared libraries; treat versions as durable choices.

---

## 12. Risks

- **Pipeline re-abandonment** — mitigated by scheduled unattended runs + a loud digest +
  backlog-age lint. This is the #1 risk; the whole cadence design exists to kill it.
- **Cluster instability on re-runs** — mitigated by sticky anchors + correction→y-label loop.
- **Cache/vault drift** — mitigated by hash-based incremental sync + `rebuild`.
- **Library churn** (sentence-transformers / BERTopic) — mitigated by pinning + the rebuild path.
- **Scope** — mitigated by the phased roadmap; each phase ships value independently.
```
