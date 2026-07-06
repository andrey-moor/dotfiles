# Pass A — An Independent Design: A Personal Memory Prosthesis over Obsidian

*Designed from first principles without reading `kb-engine/**` or its specs. Evidence used:
the problem statement plus direct reads of the vault's own saved sources on PKM, retrieval,
and AI memory (bodies only; the existing system's `_system/`, `wiki/`, and `*-vs-ours` notes
were deliberately not read).*

---

## 0. Reading of the problem

Two failure modes killed v1, and they are coupled:

1. **Retrieval failure under context shift.** Months later, the words he'd use to search are
   not the words in the title or tags he wrote at save time. Keyword search over link-stubs
   (v1's `Clippings/` folder was raw dumps; his hand notes were one-line stubs) cannot bridge
   that gap.
2. **Dormancy.** The vault's own timestamps tell the story: 36 saves in Aug 2024, dead by
   November; a small revival Jan 2025, dead again for ~13 months. V1 demanded gardening
   (manual filing, emoji-tag ceremony, "Status:" fields) and gave little back. Systems that
   ask for discipline lose to systems that don't.

These compound: a system you don't trust to retrieve doesn't get used; a system not used
doesn't get fed; a system not fed retrieves even less. The design must break the loop
**structurally**, not motivationally.

**North stars** (in priority order):

- **N1 — Worst-case retrieval.** Optimize for the query made 8 months later, phrased in
  different vocabulary, on a bad day. Not for average browsing pleasure.
- **N2 — Structural aliveness.** The system must run, improve, and stay useful with zero
  required human ritual. Anything mandatory will eventually be skipped; anything skipped
  must cost nothing.
- **N3 — Zero-decision capture.** Every decision at save time (folder? tags? title?) is a
  tax on the habit. Capture is a reflex: URL + optional one-line "why," ≤5 seconds.
- **N4 — Truth in Markdown, everything else disposable.** The vault is home (hard
  constraint) and file-over-app is right anyway. All derived machinery must be regenerable
  from the files.

The framing that follows from these: this is a **memory prosthesis**, not a "second brain"
content garden. The dead version died because it asked him to garden. The new one is an
appliance: capture is reflex, organization is computed, retrieval is conversational, and
the only ritual is optionally reading one digest with coffee.

---

## 1. The design

### 1.1 Architecture — three planes

```
┌───────────────────────────────────────────────────────────────────┐
│ AGENT PLANE (interface)                                           │
│ Claude Code / Claude Desktop skills + a small CLI (`mem`)         │
│ verbs: add · ingest · search · similar · surface · digest ·       │
│        probe · eval · doctor                                      │
├───────────────────────────────────────────────────────────────────┤
│ INDEX PLANE (derived, disposable)                                 │
│ one SQLite file OUTSIDE the vault:                                │
│   FTS5 (BM25) over title/why/summary/content                      │
│   vectors (chunk + gist) via local embedding model                │
│   metadata table (facets, hashes, telemetry, probes)              │
│ rebuildable from the vault at any time; incremental by hash       │
├───────────────────────────────────────────────────────────────────┤
│ SUBSTRATE PLANE (truth)                                           │
│ Markdown notes in the Obsidian vault, one file per saved item,    │
│ full extracted content inside the note. Syncs to iPhone free.     │
└───────────────────────────────────────────────────────────────────┘
```

- The **substrate** is the only thing that matters long-term. If every other component is
  deleted, the notes remain readable, greppable, Obsidian-searchable — already better than
  v1, because the *content* is in the files.
- The **index** lives outside the vault (e.g. `~/.local/state/mem/index.db`) so iCloud never
  syncs or corrupts it and Obsidian never sees it. It is a cache, never a source.
- The **agent plane** is the UI. No bespoke GUI ever. Obsidian is the read surface; Claude
  is the ask surface; the CLI is the plumbing both use.

### 1.2 Data model

Vault layout (flat truth, computed views):

```
KB/
  items/2026/some-slug.md      # one note per saved item, year-partitioned
  topics/retrieval.md          # GENERATED topic hubs (MOCs)
  digests/2026-W28.md          # GENERATED weekly digests
  inbox.md                     # append-only phone capture target
```

Item note — frontmatter is machine-owned except `why`; body is structured for progressive
disclosure (a reader — human or agent — can stop at any heading):

```markdown
---
id: 01J9XK...            # stable ULID; survives renames
url: https://…           # as captured
canon: https://…         # canonicalized (tracker-stripped, redirects resolved) — dedup key
title: …                 # extracted, fixed up by LLM when the source title is garbage
source: web | tweet | newsletter | task | pdf | video
author: …
saved: 2026-07-06
why: "for the lan-mouse debugging approach"   # HIS words, verbatim, optional
summary: …               # 2–3 sentences, machine
topics: [ai-agents, retrieval]                # 1–3 from controlled vocabulary
status: raw | enriched
hash: sha256:…           # content hash for idempotent re-processing
---
## Why            ← his one line, if given (also in frontmatter; duplicated for reading flow)
## Summary        ← machine, 2–3 sentences
## Highlights     ← his, optional, added any time from phone or Mac
## Content        ← readable extraction, capped ~3–5k words, link to original for the rest
## Related        ← 3–5 machine-written wikilinks, each with a one-line "because…"
```

Index-side model: `items` (facets + gist vector of title+why+summary), `chunks` (~400-token
content chunks, each embedded), `fts` (BM25 over weighted fields), `events` (captures,
searches, opens — local telemetry), `probes` (eval set).

**Chunk + gist duality matters:** the gist vector catches "what is this about" queries; the
chunk vectors catch "it mentioned a specific trick" queries. Both are searched, results
fused at the note level (max over chunks).

### 1.3 Capture

Rule: **no decisions, never blocks, nothing mandatory beyond the URL.**

| Source | Path | Notes |
|---|---|---|
| Mac / in Claude | `mem add <url> -m "why"`, or say "save this" in any Claude session | agent extracts the why from conversation context if present |
| iPhone | Share sheet → Shortcut → appends one line `- <url> | <why>` to `KB/inbox.md` | append-only line format makes iCloud conflicts trivially mergeable; phone writes only here, pipeline consumes only from here (single-writer per file) |
| Newsletters | Mail rule files them to a `KB` mailbox; pipeline polls IMAP and ingests per-issue | zero-touch; the issue becomes one item; links inside are NOT exploded unless he saves one explicitly |
| Tweets | Share sheet, same as iPhone path | extractor tries syndication endpoints/nitter-style fallbacks; on failure keeps URL + why + whatever text came through as `status: raw` — a capture is never dropped |
| Saved tasks (Things) | periodic export treated as another inbox | evidence shows links pool there and arrive in bulk; ingestion is batch-friendly and idempotent, so a 459-item backlog month is fine |

**Dedup at ingest** (his corpus is full of `-2`, `-3`, `-4` duplicate saves): canonical-URL
match first, then near-dup by gist-vector cosine (>0.95) → merge: bump `saved`, append the
new why. The capture surface *answers back*: "already saved 2026-03-31 — your note said
'…'." Re-saving becomes a feature (a resurfacing signal), not litter.

### 1.4 Enrichment pipeline

`mem ingest` — one idempotent command, run by launchd hourly and on demand:

1. sweep inboxes (inbox.md, mailbox, Things export) → create raw items
2. fetch + extract readable main text (readability-style; PDFs and YouTube transcripts
   included); cache by URL hash
3. write/update the item note (never touching `why`/`Highlights`)
4. LLM pass, batched: 2–3 sentence summary; title repair (tweet titles are garbage);
   topic assignment from the controlled vocabulary
5. embed gist + chunks (local model); upsert index
6. write `## Related` links (top-k neighbors over threshold, with one-line reasons)
7. regenerate affected topic hubs and the "Recent" hub

Every step keyed by content hash → re-running is free; failures degrade (a fetch failure
still yields an indexed item findable by title/why/url and retried next sweep). **Catch-up
after any dormancy is exactly one run.** LLM cost scales with new items (~15/week), not
corpus size; embeddings are local and free.

### 1.5 Organization — computed views over flat truth

- **No filing folders.** Year partition only (file-count hygiene). Folders-as-taxonomy is
  the v1 mistake: every folder decision is capture friction plus future wrongness.
- **Controlled topic vocabulary, machine-assigned.** ~30 topics spanning his whole life
  (ai-agents, retrieval, obsidian-pkm, rust, home-projects, camping-gear, recipes,
  photography, …) — the corpus is life-wide (bathroom fans and boots next to ColBERT), so
  the taxonomy must be too. The LLM assigns 1–3 per item. Quarterly, embedding clusters
  propose splits/merges/new topics; he approves from the digest with one word. Tags are
  **views, not truth**: a full re-tag is one cheap command, so taxonomy debt can't
  accumulate guilt.
- **Facets** (source, author, saved) in frontmatter power Obsidian Bases/Dataview browsing
  for free.
- **Related-links written into notes** make Obsidian's graph and backlinks actually useful
  and give phone-browsing serendipity without any plugin.

### 1.6 Retrieval — the heart

Layered, because context shift is a vocabulary problem *and* a ranking problem:

1. **Hybrid index search.** BM25 (FTS5) ∪ vector cosine (gist + chunks), fused with
   reciprocal-rank fusion — no score calibration to maintain. Field boosts: `why` > title >
   summary > content. Mild recency tiebreak. Structured filters compose: `topic:retrieval
   source:tweet saved:2025`.
2. **Agent loop on top.** In Claude: "what do I have about agents remembering things across
   sessions?" → the agent reformulates the query 2–3 ways, runs hybrid search, reads
   **progressively** (ids+titles+snippets → summaries → full content only for finalists),
   and answers with citations as `[[wikilinks]]`. The agent bridges vocabulary the index
   can't; the index keeps the agent from reading 1,200 notes. This layering is exactly the
   progressive-disclosure / just-in-time-retrieval pattern his own saved sources converge on.
3. **Zero-query retrieval (`mem surface`).** Given current working context (the repo he's
   in, a draft, a meeting note), embed it and surface the top related saved items — at
   Claude session start as one quiet line. Saved items must *come back on their own*;
   that's what "saving" is for.
4. **Floor guarantee.** Because full text lives in the notes, plain Obsidian search and
   `grep` work with the engine off. The system's worst case equals a good clipper's best
   case.

### 1.7 Browsing & compiled surfaces

All generated, all regenerable, clearly marked `> [!generated]` with a preserved
`## Notes (yours)` block for hand edits:

- **Topic hubs** (`KB/topics/*.md`): canonical picks pinned by the LLM, then recent items,
  each with its one-liner. The Obsidian entry points on Mac and iPhone.
- **Home** (`KB/index.md`): topics with counts, recent saves, recent digests.
- **Weekly digest** (see §1.8).

No plugin dependencies required for reading; everything is plain Markdown + wikilinks.

### 1.8 The aliveness loop

Dormancy resistance is designed in, not hoped for:

- **Automation runs regardless.** launchd: hourly ingest sweep; Monday 7am digest. His
  absence stops nothing; his return costs nothing (idempotent catch-up).
- **One optional ritual: the weekly digest** (~5 min, in the vault, optionally echoed at
  Claude session start): last week's saves grouped by topic with one-liners; **three
  resurfacings** (one related to current work, one aging never-opened gem, one anniversary);
  pending taxonomy proposals as one-word approvals; a health line (raw-item count, ingest
  failures, index freshness, searches this week and hit rate, probe recall).
- **No review queue, ever.** Nothing waits for him; there is no "process your inbox" debt.
  V1-style guilt piles are the documented killer.
- **Graceful dormancy mode.** No interactions for 30 days → digest degrades to a monthly
  "12 saved, 3 worth a look" note. Re-entry ramp, not reproach.
- **Trust loop.** Every real search that fails becomes an eval probe (`mem probe add`).
  The system provably improves at exactly the queries he actually makes — and trust is what
  keeps him coming back.

### 1.9 Interfaces

- **Claude (primary):** skills for save / find / surface / digest-review. Conversational
  retrieval is the killer app; answers cite `[[notes]]`.
- **CLI (`mem`)** for plumbing, scripting, cron — and as the API the skills call.
- **Obsidian (read surface):** hubs, digests, graph, Bases-over-facets. iPhone reading free
  via existing sync.
- **Explicitly no bespoke GUI.** Maintenance surface must stay near zero.

### 1.10 Evaluation

- **Probe suite:** 25–40 real memory-phrased queries with expected notes ("that thread about
  token-level embeddings for reranking" → ColBERT note), seeded from remembered past
  failures, grown from live ones. `mem eval` reports recall@5 and MRR; runs on any pipeline
  or model change and monthly by cron; result line in the digest.
- **Aliveness metrics** (local `events` table): captures/week, searches/week and hit rate,
  digest reads. The 6-month success criteria: (a) months-later self-queries succeed
  (recall@5 ≥ ~85% on probes), (b) no capture gap > 3 weeks, (c) he can name recent
  "found it in seconds" moments.
- **Failure-driven development:** the eval set is the backlog; tuning targets probes, not
  vibes.

### 1.11 Scaling (1.2k → 5k → 50k)

| Scale | What changes |
|---|---|
| ~1.2k now | FTS5 + brute-force cosine over blobs — milliseconds, zero infra |
| 5k (~5 yrs) | nothing; vectors ≈ 60–100 MB; brute force still fine |
| 50k | ANN (sqlite-vec/HNSW) + doc-level pre-filter; year partitions keep folders sane for Obsidian/iCloud; hubs show canonical+recent only (search is the entry point anyway); optionally archive cold items out of hubs — never out of the index |

Enrichment cost is flat forever (only new items). Architecture never changes shape.

### 1.12 Failure modes & mitigations

- **iCloud sync conflict:** single-writer-per-file discipline; inbox is append-only lines;
  pipeline runs on the Mac only.
- **Extraction failure / hostile sources (X):** never drop a capture; keep raw + retry;
  worst case the URL + why + repaired title are still indexed and findable.
- **Link rot:** full text was captured on day one — rot mostly stops mattering; `mem doctor`
  can re-check and snapshot on demand.
- **Embedding model change:** vectors are cache; re-embed everything in one run; probes
  verify no regression.
- **LLM tag drift / bad summaries:** tags are views (mass re-tag is cheap); summaries are
  regenerable; `why`/`Highlights` are never machine-touched.
- **The engine itself dies:** notes remain complete and readable — the substrate never
  needed the engine to be valuable (N4).

### 1.13 Radical alternative (clearly labeled — not the main design)

**SQLite-as-truth episodic memory.** Store items, chunks, events, and *every interaction*
(searches, opens, sessions) in one database as an event log; treat memory like a cognitive
system (decay, reinforcement on re-encounter, spaced resurfacing driven by access patterns);
export Markdown views into Obsidian as a read-only projection. It would beat the main design
at resurfacing quality and query power (real joins over episodes: "what was I reading around
the time we did the LUKS VM work?"). Rejected as primary because it inverts N4: truth
becomes opaque, trust and inspectability drop, iPhone becomes a projection surface, and his
own most-endorsed sources (file-over-app, explicit inspectable memory, BYOAI) argue the
opposite. The main design steals its best organ anyway: the local `events` table as
telemetry — episodic signal without episodic truth.

**Build-vs-buy honesty:** Readwise Reader / Karakeep / Recall solve capture + read-later +
decent search as products. Rejected: not local-first, ongoing cost, closed retrieval loop,
and — decisively — his leverage is the Claude/agent integration, which a closed product
can't give him. But their capture ergonomics (share sheet in two taps, answer-back on
duplicate) are the bar to meet.

---

## 2. Key decisions (load-bearing, with the rejected alternative)

1. **Markdown notes are truth; SQLite is a disposable cache.** Rejected DB-as-truth:
   violates his home + file-over-app; kills inspectability/trust. (N4)
2. **Full extracted content lives in the note.** Rejected link-only stubs (v1) and
   sidecar content stores: stubs are unsearchable and rot; sidecars break the
   "grep still works" floor and file-over-app portability.
3. **Capture = URL + optional why; zero decisions.** Rejected file-on-capture: decision
   tax is what kills the habit — v1's corpse proves it.
4. **`why` captured verbatim, never machine-edited, boosted in ranking.** Rejected
   discarding or paraphrasing it: months later the query resembles the intent, not the
   document. (Corpus evidence: the field existed and stayed empty — so it must be
   effortless and optional, but rewarded when present.)
5. **Hybrid retrieval (BM25 ∪ local embeddings, RRF), chunk + gist.** Rejected
   keyword-only: the documented v1 failure. Rejected embeddings-only: loses exact
   names/acronyms/code. Rejected rerankers/ColBERT at this scale: complexity before the
   probe suite demands it.
6. **Agent loop over the index as the primary retrieval UX, with progressive
   disclosure.** Rejected raw ranked lists as the main UX: the agent bridges vocabulary
   (N1) — but only the index makes agent retrieval tractable and cheap (context rot).
7. **Local embedding model.** Rejected API embeddings: per-use cost, offline failure,
   privacy; at this scale local is free and good enough — probes will verify.
8. **Machine-assigned controlled vocabulary (~30 life-wide topics); tags are views.**
   Rejected manual tagging (tag debt → guilt → dormancy) and folksonomy-by-LLM
   (unbounded tag sprawl); rejected folders-as-taxonomy outright.
9. **Emergent taxonomy maintenance** (clusters propose, he approves from the digest).
   Rejected hand-designed-once taxonomy: it's wrong in a year; rejected fully-auto
   evolution: taxonomy is the one place a human veto is cheap and valuable.
10. **Related-links + generated topic hubs as the browse layer.** Rejected hand-curated
    MOCs (rot, ceremony) and graph databases (his own saved analysis: faithfulness gains
    don't justify infra at this scale).
11. **Dedup at ingest with answer-back.** Rejected ignoring dupes: his corpus is
    literally littered with `-2/-3/-4` copies; a re-save should strengthen memory, not
    fragment it.
12. **Newsletters auto-ingested from a mailbox; issue = item.** Rejected manual
    forwarding (friction) and per-link explosion (noise dilutes the corpus and the
    curation signal his sources prize).
13. **Weekly push digest is the only ritual, optional, with resurfacing.** Rejected
    review queues / spaced-repetition obligations: mandatory rituals are how it died.
    Push, don't pull.
14. **Probe-based eval + local usage telemetry.** Rejected vibes: trust must be
    measurable, and failed searches must turn into test cases or tuning is aimless.
15. **Index outside the vault; pipeline runs only on the Mac; phone writes only to an
    append-only inbox.** Rejected index-in-vault and multi-writer: iCloud conflicts are
    the quiet data-corruption path.

---

## 3. What his own notes argued (and how it shaped the design)

His curated corpus converges on five claims with striking consistency:

1. **File-over-app, explicit inspectable memory, BYOAI** (Karpathy's LLM-wiki gist +
   Farzapedia thread, saved three separate times — the strongest signal in the corpus):
   memory should be plain local files any AI can be pointed at; the artifact is navigable
   and yours. → The substrate plane, N4, and the rejection of the SQLite-as-truth
   alternative.
2. **The LLM is the librarian; the human rarely writes the organization** (Karpathy:
   "you rarely ever write or edit the wiki manually, it's the domain of the LLM"; linting;
   outputs filed back; custom search CLI for the LLM). → Machine-owned frontmatter,
   generated hubs, `mem doctor`, agent-first interface, write-back digests.
3. **Vault + Claude Code compounds; automation must be zero-touch** (internetvin, CyrilXBT,
   Nyk's 3-layer memory stack, sourfraser's "AI employee": transcripts auto-land, agent
   processes, "perfect is the enemy of done"; always-search-vault-first instructions).
   → Capture-to-vault automation, session-start `surface`, the always-running pipeline.
4. **Retrieval should be hybrid, token-frugal, and infrastructure-light** (claude-mem:
   SQLite + hybrid semantic/keyword + 3-layer progressive disclosure, ~10× token savings;
   ColBERT saved explicitly as a *reranker* option; GraphRAG-vs-vector analysis concluding
   graph infra rarely pays; fast-graphrag's cheap PageRank as the counterpoint; Anthropic's
   context-rot post: just-in-time retrieval, structured notes). → RRF hybrid on SQLite,
   progressive disclosure in the agent loop, no graph database, no reranker until probes
   demand one.
5. **Curation is the value; a dump is not a commonplace book** (jameesy: Claude's output
   quality mirrors the intentionality of what you keep). → The `why` line, canonical picks
   in hubs, restraint in auto-write-back (Q&A outputs are filed only on explicit "capture
   this").

Where I **depart** from his sources: Karpathy says at ~100-article scale "no fancy RAG
needed — the agent plus index files suffice." At 1,200 life-wide items with garbage tweet
titles — heading to 5k — I judge that wrong for *this* corpus: the hybrid index is cheap
insurance for N1, and his own claude-mem save (hybrid SQLite + vectors) is the pattern that
actually fits. I keep Karpathy's "agent over files" as the UX while rejecting his "no index"
as the mechanism.

The corpus is also **meta-evidence** — what his behavior (not his sources) argued:
duplicate saves everywhere → dedup with answer-back; `context:` fields present but almost
always empty → intent capture must be one optional keystroke, and ranking must survive its
absence; tweet-slug titles (`t-ztr8dc4an.md`) → title repair and content extraction are
load-bearing; Things-export and Web-Clipper-backlog imports → batch, idempotent ingestion
is a first-class path, not an edge case; the save-date histogram (burst → death → burst)
→ aliveness must be structural. And the scope surprise: boots, bathroom fans, and recipes
live beside ColBERT — the system is a prosthesis for a *life*, not a research library, so
ceremony-per-item must be near zero and the taxonomy must span all of it.

---

## 4. Open questions (his call, not mine)

1. **Digest delivery surface:** vault note only, or also email / Claude session-start echo?
   (Where does he reliably *look* on Monday?)
2. **Newsletter scope:** which senders, and is issue-as-item right, or do a few
   high-density newsletters deserve per-link explosion?
3. **Enrichment LLM:** Claude API (quality, uses existing subscription) vs local model
   (pure local-first, weaker summaries)? My default: Claude for the weekly batch, local
   fallback — but it's a privacy/values fork.
4. **Write-back appetite:** should good Claude answers auto-file into the KB, or only on
   explicit "capture this"? (I default to explicit — curation over dump — but Karpathy's
   compounding loop argues the other way.)
5. **Reading workflow:** does he want read-later *reading* to move into Obsidian (content
   is now in the notes), or keep reading in the browser and treat notes purely as memory?
   Affects how much extraction fidelity matters (images, formatting).
6. **Index scope:** whole vault (Orrery people/meeting notes too) with per-folder
   privacy excludes, or `KB/` only? Whole-vault maximizes "find it later"; excludes need
   his judgment.
7. **Things:** keep as a capture funnel indefinitely, or retire it for links once the
   share-sheet path is trusted?
8. **Retention policy:** dead products/404s/expired deals — archive view, or keep
   everything forever? (Index keeps everything either way; this is about hub noise.)
