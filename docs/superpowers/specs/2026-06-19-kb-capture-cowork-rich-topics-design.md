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

## Capture front doors → one inbox

Every capture channel writes the **same** artifact — a `Knowledge/inbox/<note>.md` carrying the inbox schema (+ a "why") — and then flows through the same `inbox-check` → `/kb:review` pipeline. Adding a channel never adds a pipeline; it adds a *feeder*.

**Uniform channel contract.** Each channel: (1) produces inbox notes via the shared `importing/inbox.py` schema; (2) dedups via `importing/urls.normalize_url` (+ a channel-native id where available); (3) is validated by `inbox-check`; (4) is processed by `/kb:review`. In code, each channel lives in `importing/<channel>.py` and (where it has one) exposes a uniform `import-<channel>` CLI command (`--json`, `pass_obj` Config, shared `_emit`). Channels today: **Web Clipper**, **email**, and **Things 3** (legacy/backlog-only).

### Web Clipper (web pages) — primary
The **Obsidian Web Clipper** (Safari desktop + iOS share sheet):
- Clips **straight into** `Knowledge/inbox/` as a real note — no import hop.
- A template field captures **"why am I saving this?"** at clip time; Phase 0 found this is easily forgotten, so the **primary `why` path is a ~5-second `/kb:review` backfill** (clip-time `why` is a bonus).
- Captures **content in your already-authed browser**, obviating the fragile fetch tier (tweets/402, `t.co` redirects, paywalled/JS, Reddit edge-block) — confirmed in Phase 0.

### Email / newsletters — second front door
For subscription reading, where the **email body is the content** (mostly) or a **link inside it** is the keeper (some):
- **Selection — a dedicated `Knowledge Base` Fastmail label** (no auto-purge), populated by **From-based allowlist rules**: per-sender precision, using Substack `+section@` variants to target reading sections and exclude roundups/podcasts; `Every` needs a subject rule (essays and "Context Window" share one From). **Pin** is the manual "also grab this one" override. This label is *ingest-intent* — orthogonal to the existing `Newsletters` *filing* label.
- **Transform — body-first:** ingest the (HTML→Markdown) email body as the note (`source: newsletter`), and **always store the canonical URL** as metadata + dedup key — so even a teaser+link email still points to the full piece. `why` is review-time backfilled.
- **Mechanism — engine-native `import-mail` over JMAP** (Fastmail's native protocol) with an API token in 1Password/Nix. The deterministic engine owns the transform; Cowork is the cockpit that triggers/reviews it. *Not* the Fastmail MCP — that is claude.ai-session-authed and absent in headless/scheduled runs.
- **Dedup:** Message-ID (always present) + normalized canonical URL (catches the same piece across channels, e.g. if also clipped).
- **Validated — read-only JMAP spike (2026-06-30, green):** auth + query-by-label + body fetch all work, and JMAP exposes **List-Id** (which the Fastmail MCP does not), giving reliable sender grouping.

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
- **Email capture:** a second capture front door — newsletters ingested by an engine-native `import-mail` over **JMAP** (not the MCP), selected by a dedicated `Knowledge Base` Fastmail label (From-based allowlist + pin override), body-first with the canonical URL as dedup key. Validated by a JMAP spike (2026-06-30).
- **Uniform channel contract:** all capture channels share the inbox-note schema, dedup, `inbox-check`, and `/kb:review`; each is an `importing/<channel>.py` with a uniform `import-<channel>` CLI.

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
- `kb_engine/importing/mail.py` + an `import-mail` command (new): a JMAP client (Fastmail API token) → per-sender transform (HTML→Markdown body, canonical-URL extraction, footer/redirect cleanup) → inbox notes, dedup'd by Message-ID + normalized URL; marks ingested (label swap or tracked ids). Mirrors `importing/things.py` and the uniform CLI pattern. Unit-tested with fixtures; a live JMAP check gated behind an env flag (mirrors `KB_RUN_INTEGRATION`).

**Data flow:** clip / `import-mail` → `Knowledge/inbox/<note>.md` (with `why`) → sync embeds (title+summary+why) → deterministic assign (confident → applied; ambiguous → review queue) → human resolves in Cowork → tags + `primary_topic` written → unclassified residual reachable via by-category + feeds `topics suggest`.

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

---

## Phase 0 results (2026-06-29)

Both validation spikes ran hands-on. **Verdict: gate PASS with two recorded caveats that become Phase 1 entry tasks.** Capture is feasible and Cowork drives the engine live; the gaps are a titleless-page fallback and a confirmatory clip pass of the remaining must-have sources.

### Spike A — Capture (Web Clipper)
Single catch-all "Default" template → `Knowledge/inbox/`, vault `Main`. 6 clips across **macOS Safari + iPhone Safari** (several articles + an X/tweet thread), then `inbox-check`.

- **In-browser capture obviates the fetch tier (the pivotal win).** Clips capture the already-rendered, authed DOM, so the source-type fetch failures the matrix worried about (tweet 402, `t.co` redirects, paywalled/JS, Reddit edge-block) **don't apply** — content quality is independent of source type. Articles + an X/tweet captured clean on both devices.
- **`why` path decided → review-time fill is primary.** Clip-time `why` is a manual text field that *works*, but was forgotten on 5/6 clips (it's a blank field, no modal prompt). So the **`/kb:review` triage backfill is the primary `why` path**; clip-time `why` is a bonus when remembered. The spec's "graceful degradation" is now the *default* mode. **Never** set `why` to the Interpreter prompt syntax — that makes the LLM guess, violating the core invariant.
- **Devices:** iPhone → Mac iCloud propagation lag ~minutes (not instant); both produce well-formed clips.
- **Dedup works:** a same-URL mobile double-clip was caught by `inbox-check` `dup_in_inbox` (normalized URL); the byte-identical copy was removed.
- **Final `inbox-check`:** 6 notes → `schema_ok=5`, `schema_bad=1`.

### Spike B — Cowork ↔ MCP
Probe registered in Claude Desktop (`mcpServers.kb-engine-probe`; absolute `uv` path; `--extra mcp --extra ml`; `KB_VAULT` env).

- **Connectivity confirmed.** Server handshakes in the real runtime; `kb_status` → `{notes: 585, chunks: 585, server_time}`; `kb_search "rust"` → 10 real semantic hits (the torch/`ml` embedding path runs inside the Cowork-spawned server).
- **Live-Artifact refresh CONFIRMED → live refresh chosen (no fallback).** A Live Artifact calling `kb_status` re-queries the local MCP on its refresh control; `server_time` advances each time. **Phase 2's project workbench can be a live, auto-refreshing Cowork artifact** — the scheduled-task fallback is *not* needed.
- **Architecture notes for Phase 1/2:** Cowork runs in a **VM**, but the MCP server runs on the **host** (it reached the real 585-note DB); tool calls are **permission-gated per Cowork session** (`kb_status` approved "always"). Probe cold-start ~3s (uv + Python); torch is lazy, so it costs only the first `kb_search`, not startup.

### Exit-criteria assessment
| Criterion | Status |
|-----------|--------|
| Capture matrix green for must-have sources, or degraded path recorded | ⚠️ **Mechanism-validated.** article + tweet confirmed on Mac+iPhone; the in-browser path covers github/youtube/paywalled/email by construction (fetch tier obviated) but they were **not individually clipped** → confirmatory pass recommended. |
| `inbox-check` `schema_bad == 0` on the test set | ⚠️ **schema_bad = 1** — a titleless page → `Untitled.md`, no `title`. Not a template defect (the clip schema is correct); remedy = **process-time title fallback** (Phase 1 ingestion). Clip is still ingestible. |
| `why` capture path decided | ✅ Review-time fill (primary) + clip-time field (bonus). |
| Cowork reaches MCP + calls a tool; refresh mechanism chosen | ✅ Connectivity + **live-artifact refresh** confirmed. |

### Feeds Phase 1 (entry tasks)
- **Title fallback at ingestion:** derive a title for titleless clips (from `<h1>` / URL slug) so `schema_bad → 0`; titleless ≠ lost.
- **`why` backfill in `/kb:review`:** make the ~5-second "why did you save this?" triage a first-class review step (the primary `why` path).
- **Tooling bug (found in spike):** `kb-engine --vault <path> inbox-check` did **not** honor `--vault` (reported 0 notes; the direct `check_inbox(vault)` call read the vault correctly). Fix how `vault_path` reaches the command before `/kb:review` relies on it.
- **Email capture channel** (`import-mail` over JMAP): designed + JMAP-spiked **green** (2026-06-30) — see *Capture front doors → Email*. Build alongside the Phase 1 capture-`why` ingestion as the second front door.

### Gate decision
Criteria 3–4 are fully met; 1–2 carry remedies that are Phase-1 ingestion work, not capture-feasibility failures. **Recommended: close Phase 0 and start Phase 1**, recording title-fallback + `why`-backfill + the `--vault` fix as Phase 1 entry tasks. Optional before closing: a 4-clip confirmatory pass (github / youtube / paywalled / email-link).
