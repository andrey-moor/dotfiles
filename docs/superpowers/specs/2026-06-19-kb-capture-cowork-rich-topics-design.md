---
type: design-spec
project: knowledge-base
status: draft
created: 2026-06-19
---

# KB Capture, Rich Topics & Cowork Integration — Design

**Goal:** Turn the KB from a pile of captured links into a *live, navigable* system where (1) every capture records *why* it was saved, (2) topics are a stable, rich, LLM-curated structure you can browse, and (3) when you start a project you can pull both **references** and **inspiration** from everything you've ever saved — operated primarily through **Claude Cowork**.

**Architecture:** Evolve the existing local `kb-engine` (files-as-truth, summary-anchored embeddings, hybrid search, primary/secondary topics, by-category fallback). Add: a capture front door (Obsidian Web Clipper + a "why" field), an LLM-curated topic layer (classification into a stable taxonomy, with clustering demoted to gap-discovery), a first-class **projects** axis, and a **kb-engine MCP server** so Cowork is the operations cockpit. The engine stays local and deterministic; the LLM (Haiku) is a *curator*, never a silent decider.

**Tech stack:** Python `kb_engine` (sqlite3 vectors + FTS5, local jina-v3 embeddings, UMAP/HDBSCAN, click CLI); Obsidian Web Clipper (Safari desktop + iOS); Claude Cowork (local agentic surface, Live Artifacts, MCP); Anthropic Haiku for classification/labeling; MCP (local server).

---

## Motivation

After v2 (summary embeddings + primary/secondary topics + by-category fallback), retrieval is strong but **topic structure is noisy and unstable**: bottom-up HDBSCAN over ~585 short, heterogeneous web clips produces arbitrary clusters with keyword-mash labels (`fzf-kata-zoxide-alt-ripgrep`), and ~43% of notes don't cleanly cluster. That's fatal for *navigation* (a topic you recognize must still exist next month) and for the real goal: **"when I decide to build a video game, surface everything I saved that's a reference or could spark an idea."**

Three root causes, three moves:
1. **Clustering is the wrong primary structure.** → Flip to a *stable taxonomy you classify into*; demote clustering to a gap-finder.
2. **No record of intent.** → Capture *why am I saving this* at the source; it's the strongest signal for both topic and project routing.
3. **No goal-oriented view.** → Add a *projects* axis, rendered as a live, auto-refreshing workbench in Cowork.

## Core invariant (everything serves this)

**The LLM proposes; it never silently assumes; and no note is ever unreachable.**
- A confident match is auto-filed (by embedding similarity or LLM).
- *Any* ambiguity goes to a **review queue** the human resolves (in Cowork / `/kb:review`) — never an auto-guess.
- A note matching nothing is **not dropped** — it stays in search and appears in the by-category / unclassified view. "Lost" is structurally impossible: every note is reachable by ≥1 path at all times.
- Cost is not a constraint; the LLM is gated on **confidence**, solely to prevent wrong assumptions.

## The two axes

Two orthogonal structures over the same notes:

| Axis | Question | Source | Stability |
|------|----------|--------|-----------|
| **Topics** | what a note is *about* | curated taxonomy, LLM-classified | stable, browsable |
| **Projects** | what a note is *for* | user-declared goal + retrieval + accrual | grows deliberately |

A note can be `topic: graphics` **and** pulled into `project: retro-platformer`.

### Topics — classify into a stable taxonomy (not cluster)
- A named taxonomy is the navigable structure. Each note gets a **primary** topic + ≤2 **secondaries** (the v2 model), assigned by: deterministic embedding-similarity for confident matches; **Haiku** classification for ambiguous ones (using title + summary + the "why").
- **Clustering is demoted to discovery.** `topics suggest` (already built) clusters only the unclassified residual at `min_cluster_size=2` to *propose new taxonomy entries*; Haiku names the candidate; the human approves it into the taxonomy. This is the hybrid: *embeddings find gaps, LLM + human curate, classification files.*
- Anything not confidently classified → review queue + by-category fallback (never dropped).

### Projects — hybrid membership, references + inspiration
- Created with a short brief. On creation, **retrieval seeds it from the whole history** (solves "I just decided to build a game — show me everything I ever saved").
- New captures **accrue** via their "why" + classification. The human can **pin/mute** to correct membership.
- Two retrieval lanes:
  - **References** — directly relevant (nearest-neighbor, same topic/high cosine).
  - **Inspiration** — adjacent/analogous (mid-similarity, *cross-topic*, diversity-sampled for serendipity). This is a distinct retrieval mode, not nearest-neighbor.

## Capture front door — Obsidian Web Clipper + "why"

Standardize on the **Obsidian Web Clipper** (Safari desktop + iOS share sheet) as the primary capture surface:
- Clips **straight into** `Knowledge/inbox/` as a real note — no import hop.
- A template field captures **"why am I saving this?"** alongside the page content, in one step.
- Captures **content in your already-authed browser**, which is expected to obviate the fragile fetch tier (tweets/402, `t.co` redirects, paywalled/JS pages, Reddit edge-block).
- Things 3 import remains **legacy/backlog-only**.
- **Graceful degradation:** if the clipper can't reliably prompt for free-text "why" (esp. on iOS), the "why" moves to a 5-second triage step in review — the design still holds.

## Cowork as the operations cockpit

Claude Cowork (local desktop agentic surface; reads local files; supports MCP; Live Artifacts re-execute on open; scheduled tasks) is the primary way to *operate* the KB:
- **kb-engine MCP server** (new) exposes structured ops to Cowork (and Code/Chat): `search`, `surface`, `related`, `topics`, `notes_without_topic`, the **review/ambiguity queue**, and (Phase 2) **project query → references + inspiration**.
- **Review/governance** runs as a Cowork task ("review my KB"): read inbox + ambiguity queue → propose classifications → human resolves → write back. The LLM-curated, human-resolves-ambiguity flow lives here naturally.
- **Project workbench = a Live Artifact**: an HTML page that, on each open, re-runs project retrieval via the MCP and renders the References + Inspiration lanes — always current. We supply data; Cowork renders + refreshes. (Validate that a Live Artifact can refresh from a *custom local* MCP; fallback = a scheduled/on-demand Cowork task regenerates it.)
- The engine itself stays **local + deterministic**; Cowork/Haiku is the curation+UI layer on top.

## Confidence-gating & the review queue
- Classification (topic and project) carries a confidence; ≥ threshold → auto-apply; below → a queue item ("this could be `gamedev` *or* `graphics` — which? both?").
- The queue is a first-class engine concept (a persisted set of pending decisions), surfaced in Cowork/`/kb:review`. Resolving writes the decision back via existing engine commands (`topics add`/`apply`, project pin).

## Decisions (resolved during brainstorming)
- **Interaction model:** browse + on-demand + projects first-class (option C).
- **Project membership:** hybrid — retrieval-seeded + accrual + pin/mute (option 3).
- **LLM boundary:** confidence-gated; human resolves all ambiguity; nothing lost; cost not a constraint.
- **Capture surface:** standardize on Obsidian Web Clipper + "why" field; gated behind a feasibility spike.
- **Operations surface:** Claude Cowork, via a local kb-engine MCP server; projects render as Live Artifacts.
- **MCP timing:** thin read+review MCP slice in Phase 1; project ops in Phase 2.
- **Topics:** classification into a stable taxonomy; clustering demoted to gap-discovery (reuse `topics suggest`).

---

## Phasing

This is too large for one spec/plan; decompose into independently-shippable phases, each with its own plan. **Phase 0 gates the rest** — if capture is leaky or Cowork can't reach the MCP, we adjust before building on top.

### Phase 0 — Validation spikes (gates; mostly collaborative)
Prove feasibility before committing. No production code beyond throwaway probes.

**0a. Capture feasibility (Web Clipper).** Across the matrix:
- *Sources:* plain article, Twitter/X tweet+thread, GitHub repo, YouTube, Reddit thread, paywalled/JS page, a `t.co`/shortened link, Instagram (allowed to fail), a page opened from an email link.
- *Devices:* macOS Safari (behemoth) + iPhone Safari → both land in the same iCloud inbox.
- *Must-pass:* (1) "why" promptable at clip time (or confirm the degraded path); (2) writes the KB inbox frontmatter schema (`source`, `title`, date, `status`, + `why`); (3) body clean enough to summarize/embed; (4) iOS clips well-formed via iCloud; (5) engine ingests + dedups (normalized URL).
- *Split:* user installs the extension + clips the test set; assistant builds the clipper **template** + verifies ingest/dedup + troubleshoots.

**0b. Cowork ↔ MCP feasibility.** Confirm: (1) Cowork connects to a local kb-engine MCP server and can call a tool; (2) a Live Artifact can refresh from that custom local MCP (else record the scheduled-task fallback).

**Exit criteria:** capture matrix green (or degraded paths chosen explicitly); MCP reachable from Cowork; refresh mechanism for live artifacts chosen.

### Phase 1 — Capture-"why" + LLM-curated topics + read/review MCP
The navigable-topics win plus the signal and cockpit that power it.
- **Capture-"why" ingestion:** a `why` (intent) frontmatter field flows from clip → inbox → note; threaded into the embedding input and the classifier. Legacy/bulk notes get an LLM-*proposed* "why" flagged for confirmation.
- **LLM-curated topic classification:** embedding-similarity assigns confident primary/secondary; Haiku classifies the ambiguous; `topics suggest` proposes new taxonomy entries (Haiku-named, human-approved). Confidence-gating + the **review queue** + the no-loss guarantee.
- **kb-engine MCP server (read + review slice):** `search`, `surface`, `related`, `topics`, `notes_without_topic`, and review-queue ops. Cowork becomes the retrieval + governance cockpit.

### Phase 2 — Projects as Live Artifacts
The reference + inspiration workbench, built on Phase 1's richer topics + "why".
- Project entity (brief + membership); retrieval-seeded creation; accrual via "why"/classification; pin/mute.
- Reference lane (nearest-neighbor) + Inspiration lane (mid-similarity, cross-topic, diversity-sampled).
- MCP project ops + the Live-Artifact workbench (auto-refresh, or scheduled-task fallback from 0b).

---

## Phase 1 detail

**Components (each small, single-purpose):**
- `kb_engine` capture/ingest: accept + persist the `why` field (frontmatter + `notes` table column); include it in `embedding_text`; expose via `note_texts`/MCP.
- `kb_engine/topics/classify.py` (new): given a note (title + summary + why) and the taxonomy, return primary + secondaries **with confidence**. Two backends: deterministic embedding-similarity (no LLM) and an LLM (Haiku) backend for ambiguous cases. The engine stays LLM-free by default; the LLM backend is invoked from the review/Cowork layer (or an opt-in command), preserving the deterministic core.
- Review queue: a persisted set of pending decisions (note + candidates + reason), with engine commands to list/resolve.
- `kb_engine/mcp/` (new): a local MCP server wrapping read ops + review-queue ops. Runs via a Nix-managed local process; registered as a Claude Desktop/Cowork local MCP server.

**Data flow:** clip → `Knowledge/inbox/<note>.md` (with `why`) → sync embeds (title+summary+why) → deterministic assign (confident → applied; ambiguous → review queue) → human resolves in Cowork → tags + `primary_topic` written → unclassified residual reachable via by-category + feeds `topics suggest`.

**Testing:** keep the torch-free `FakeEmbedder`/`FakeClusterer` discipline; add a `FakeClassifier` (deterministic, no API) so classification logic is unit-tested without Haiku; gate any real-LLM checks behind an env flag (mirrors `KB_RUN_INTEGRATION`). MCP server gets contract tests against its tool schemas. Each phase lands with the suite green and is independently shippable.

## Out of scope (YAGNI)
- Multi-user / sharing (Live Artifacts are device-local; single-user is fine).
- Reworking hybrid-search RRF or the embedding model.
- Auto-merging taxonomy ↔ topics.
- Unattended LLM classification in the weekly cron (kept human-gated by the core invariant).
- Project-specific MCP ops and the Live-Artifact workbench (Phase 2, not Phase 1).

## Risks / open questions
- **"Why" promptability** in Web Clipper, esp. iOS — pivotal; Phase 0a resolves it (degraded path defined).
- **Live Artifact ↔ custom local MCP refresh** — Phase 0b resolves it (scheduled-task fallback defined).
- **Taxonomy bootstrap:** seed Phase 1's stable taxonomy from the 24 existing active topics; let `suggest` grow it. Avoid a big-bang re-taxonomy.
- **Classification stability:** classification (vs clustering) should be stable run-to-run; verify the taxonomy doesn't churn as notes are added.
- **Engine LLM dependency:** keep it out of the deterministic core; the LLM backend lives at the review/Cowork edge so the engine stays offline-capable and testable.
