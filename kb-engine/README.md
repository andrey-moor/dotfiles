# kb-engine

Local embedding + hybrid search engine for an Obsidian knowledge base.

It reads an Obsidian vault's markdown **directly from the filesystem**
(files-as-truth), embeds notes with a local **jina-v3** model, stores float32
vectors in a SQLite cache alongside an FTS5 keyword index, and answers **hybrid**
(semantic + keyword) searches fused with Reciprocal Rank Fusion (RRF).

This is the retrieval substrate for the Obsidian KB. It is the foundation for
Phases 2–4 (per-topic centroids, clustering, areas, and proactive surfacing
build on top of the cache and search this engine provides).

## How it works

- **Ingest:** vault `.md` → notes (frontmatter, tags, inline `#tags`, `[[wikilinks]]`,
  sha256).
- **Embed:** each note → one jina-v3 vector over its `title + summary + why` gist
  (local; via the `[ml]` optional extra) → a float32 BLOB in SQLite, with
  `title + body` mirrored into an FTS5 index for keyword recall.
- **Search:** cosine similarity (the note-level gist vector) ∪ FTS5 BM25, fused via
  RRF, scoped to the `Knowledge/` tree (excluding `Knowledge/inbox/`).
- **Sync:** hash-based incremental — embed new/changed notes, drop deleted ones.
  The cache is always rebuildable from the vault, so the markdown files remain
  the single source of truth.

## Install

```bash
cd kb-engine
uv sync --extra ml            # base deps + the real jina-v3 model stack
uv sync --extra dev           # for the test suite (pytest, no torch)
uv sync --extra ml --extra dev  # both
```

The first run with `--extra ml` downloads the `jinaai/jina-embeddings-v3` model.
Importing `kb_engine` never requires torch — the real embedder imports it lazily,
so logic, tests, and `--help` work without the ML stack.

## Fresh machine bootstrap

Standing up kb-engine on a new machine (the `kb-engine` wrapper + the scheduled
launchd agents are all Nix-managed by `modules.dev.kb-engine`):

```bash
# 1. Clone the dotfiles repo, then build + apply the Nix configuration.
#    This puts `kb-engine` on PATH and installs the daily/weekly launchd agents.
just switch

# 2. Provision secrets. The pipeline runners source this file (0600) before every
#    run; enrichment + import-mail stay skipped until it holds real values.
mkdir -p ~/.config/kb-engine
$EDITOR ~/.config/kb-engine/secrets.env   # created empty by Nix; fill from 1Password
chmod 600 ~/.config/kb-engine/secrets.env
#   FASTMAIL_API_TOKEN — Fastmail → Settings → Privacy & Security → API tokens
#                        (read-only, Mail scope).
#   ANTHROPIC_API_KEY  — console.anthropic.com → API keys (dedicated KB key).

# 3. Build the embedding cache from the vault (first run downloads jina-v3).
kb-engine --vault "<vault>" rebuild

# 4. Confirm health — every check must be green (secrets is now a HARD check).
kb-engine --vault "<vault>" doctor

# 5. Confirm the scheduled agents are loaded.
launchctl list | grep kb
```

`<vault>` is the Obsidian vault path (`modules.dev.kb-engine.vaultPath`; defaults to
the iCloud "Main" vault). Once secrets hold real values, the next scheduled run picks
up enrichment + email import automatically — no re-switch needed.

## Usage

In this dotfiles repo, a `kb-engine` wrapper is put on `PATH` by the Nix module
`modules.dev.kb-engine` (enabled on behemoth). It runs this in-repo project via
`uv run --extra ml`, so the commands below work directly:

```bash
# Index the vault (hash-based incremental; safe to re-run)
kb-engine --vault "$HOME/Documents/Obsidian/MyVault" sync

# Hybrid (semantic + keyword) search; --json for machine-readable output
kb-engine --vault "$HOME/Documents/Obsidian/MyVault" search "graph memory for agents"
kb-engine --vault "$HOME/Documents/Obsidian/MyVault" search "graph memory" --json

# Cache stats: note/chunk counts, db path, last sync
kb-engine --vault "$HOME/Documents/Obsidian/MyVault" status

# Drop and re-embed everything from the vault
kb-engine --vault "$HOME/Documents/Obsidian/MyVault" rebuild
```

Without the wrapper (e.g. developing the engine directly), prefix with `uv run`:

```bash
uv run kb-engine --vault "<vault>" sync
uv run kb-engine --help
```

The SQLite cache lives under `~/.local/state/kb-engine/` by default; override the
path with `--db <path>`. Because it is derived purely from the vault, deleting it
and running `sync` (or `rebuild`) reconstructs it exactly.

## Topics

`topics discover` clusters the synced note vectors into topics. Each note's
gist vector is reduced with **UMAP** (`metric="cosine"`) and clustered with
**HDBSCAN**; unclustered notes are reported as an explicit
**unfiled** residual. Per topic the engine computes a unit-normalized centroid
and a keyword label (a simple c-TF-IDF over member note text). Topics
and their members persist in the SQLite cache; re-running `discover` replaces the
previously discovered topics.

```bash
uv sync --extra topics        # installs umap-learn + hdbscan + scikit-learn

# Discover topics over the current cache (sync first); --json for machine output
kb-engine --vault "<vault>" topics discover
kb-engine --vault "<vault>" topics discover --json
```

`--json` emits `{n_topics, n_unfiled, topics:[{slug, label, keywords, size}]}`.

### Areas

Areas are the **coarse tier** of one aboutness hierarchy — **areas → topics**. The
registry is **seeded, not clustered**: nine areas mirror the taxonomy's categories.
Each topic belongs to at most one area (`Topic.area`), so a note ends up with both
an `area/<slug>` and a `topic/<slug>` tag; four cross-cutting **facets** (Tutorials,
Reference, Inspiration, Tools) combine freely on top.

```bash
kb-engine --vault "<vault>" topics seed-areas               # seed the 9 areas (idempotent replace)
kb-engine --vault "<vault>" topics areas                    # list areas + member topics (or --json)
kb-engine --vault "<vault>" topics set-area rust-async dev  # assign a topic to an area
```

`topics areas --json` emits `{areas:[{slug, label, description, topics:[slug...]}]}`.
Area membership is **composed at read time** from each topic's `area` — `set-area`
records it and there is no separate membership table to keep in sync.

### Manual topics

`topics add` creates a **manual** topic (`kind="manual"`, `status="active"`)
anchored by an embedding of its `label + ". " + description`. Manual topics
coexist with discovered ones and **survive a subsequent `topics discover`** (only
discovered topics are replaced on re-discovery). `topics list` shows all topics —
manual first, then discovered — with their member counts.

```bash
kb-engine --vault "<vault>" topics add my-topic \
    --label "My Topic" --description "about rust filesystems"
kb-engine --vault "<vault>" topics list          # or --json
```

`topics add --json` emits `{slug, label, kind, status}`; adding a slug that
already exists fails. `topics list --json` emits
`{topics:[{slug, label, kind, status, size}]}`.

### Assignment

`topics assign` incrementally assigns notes to their nearest topic by cosine
similarity to the centroid: `score ≥ --high` → auto-member, `--low ≤ score <
--high` → reported as **borderline** for review, below `--low` → unassigned
(defaults: `--high 0.55`, `--low 0.4`). It considers `active` and `proposed`
topics. It is **dry-run by default** — it only reports; pass `--apply` to persist
high-confidence members (the engine never mutates membership silently).

```bash
# Preview assignments (no writes)
kb-engine --vault "<vault>" topics assign --json
# Persist high-confidence members
kb-engine --vault "<vault>" topics assign --apply
```

`--json` emits `{assigned:[{note, topic, score}], borderline:[...], unassigned:N,
applied:bool}`.

The engine stays **LLM-free**: labels here are deterministic keyword slugs.
Pretty, human-readable topic names are produced later by the `kb` skill layer —
this engine only provides the clustering, centroids, and keyword labels.

### Governance: the topic lifecycle

The engine does the deterministic compute and the vault file writes; **naming and
judgment live in the `kb` skill layer** (Claude), and **note mutation is gated** behind
an explicit `apply`. The full lifecycle:

1. **`sync`** — index the vault so topics reflect current notes.
2. **weekly topic pass** — either `pipeline --tier weekly`, or the pieces by hand:
   `topics reanchor` (recompute each manual topic's anchor from its members) →
   `topics thresholds` (derive per-topic assignment bars) → `topics assign --apply`
   (primary + up to two secondaries per note; the borderline band lands in the review
   queue). The **residual** is then clustered into fresh `proposed` topics. Active
   structure is preserved and manual topics (`topics add`) always survive. (The old
   `discover --sticky` single-mode is retired — `weekly` is the successor.)
3. **`topics diff-taxonomy`** — compare discovered topic membership against the tags
   declared in `_system/_taxonomy.md` using Jaccard set overlap over note paths. Emits
   `{mapping, new_topics, orphan_tags, covered_topics}`: `new_topics` is structure the
   data found that the taxonomy lacks; `orphan_tags` are declared tags no topic aligns
   with. A missing taxonomy file is treated as greenfield (all topics are new).

   ```bash
   kb-engine --vault "<vault>" topics diff-taxonomy --json
   ```

4. **(skill) name + review** — Claude turns the keyword slugs into human labels, proposes
   area names, and presents the restructure diff to the user for approval.
5. **`topics render`** — render-not-append, idempotent. Writes the MOCs and splices a
   proposals table into `_taxonomy.md` (see below). Safe to re-run.
6. **`topics apply`** — the routine note-mutating command in this loop; running it IS the
   gate for tag writes (no implicit apply elsewhere). Writes `area/<slug>` + `topic/<slug>`
   tags into member notes (see below).

Review + one-off governance verbs layer on top: **`topics confirm <slug> <note>`** (the
`/kb:review` verb — pin a borderline note as a topic's human-decided primary, then run
`apply`), and the taxonomy migration path **`topics propose-migration`** → edit the
generated `_system/migration-proposal.md` → **`topics migrate --proposal <path>`** (dry-run
by default; `--apply` executes the mass-retag cutover).

#### `_system/topics/` MOCs (render)

`topics render` writes Maps of Content into `<vault>/_system/topics/`:

- `_system/topics/index.md` — an **areas → topics** outline with
  `[[_system/topics/<slug>]]` wikilinks, member counts, and `kind/status`.
- `_system/topics/<slug>.md` — one MOC per topic: label, keywords, and a `## Notes` list
  of member `[[Knowledge/...]]` wikilinks sorted by score.

Both carry frontmatter `type: system, generated: true`. Bodies contain **no timestamps**
and members are deterministically ordered, so re-rendering is byte-identical (idempotent).
`_system/topics/` lives **outside `Knowledge/`**, so `sync` never embeds these MOCs — they
are pure derived views, rebuildable from the cache at any time.

`render` also updates `<vault>/_system/_taxonomy.md`: it splices a table of `proposed`
discovered topics (slug, keywords, size) **between stable markers**
`<!-- KB-PROPOSALS:START -->` … `<!-- KB-PROPOSALS:END -->`, creating the block if absent
and preserving the rest of the file (render-not-append).

```bash
kb-engine --vault "<vault>" topics render --json
```

`--json` emits `{n_topics, n_areas, index_path, taxonomy_path}`.

#### `area/<slug>` + `topic/<slug>` tag convention (apply)

`topics apply` writes membership back into notes as frontmatter tags: a `topic/<slug>`
per membership, the note's home `area/<slug>` (from its primary topic's area, falling
back to a best-scoring secondary's area), and `primary_topic` set to the home topic.
This namespace keeps machine-assigned tags distinct from the human taxonomy
(`Dev/Rust`, `AI/RAG`, …). It defaults to `--status active`, so `proposed` topics stay
proposed until promoted; only members of topics with the given status are tagged. Writes
go through the atomic house I/O, tags are de-duplicated, the body and other frontmatter
are preserved, and member files that are missing on disk (`skipped_missing`) or resolve
outside the vault (`skipped_outside_vault`) are skipped and reported. Re-running adds
nothing new.

```bash
kb-engine --vault "<vault>" topics apply --status active --json
```

`--json` emits `{status, n_changed, n_tags_added, skipped_missing, skipped_outside_vault}`.

## Importing from Things

`import-things` reads a local **Things 3** SQLite database, extracts URLs from
URL-bearing tasks, dedups them, and writes proper-schema **inbox stubs** into
`Knowledge/inbox/`. It is the unattended on-ramp that turns "read later" tasks
into reviewable KB notes.

Reading is **safe while Things is running**: the DB (plus any `-wal`/`-shm`
sidecars) is copied to a temp file and opened **read-only** — the engine never
touches the live database, and never writes back to Things. Only `type=0`
(tasks, not projects/headings), `trashed=0` tasks are considered; by default
only **open** tasks (`--status open`). A task contributes a stub per URL found
in its title or notes; tasks with no URL are ignored.

Dedup happens on the **normalized URL** (tracking params like `utm_*`/`fbclid`
and the fragment dropped, trailing slash stripped) both against existing vault
note URLs (scanning `Knowledge/**/*.md` frontmatter `url`) and within the batch,
so re-running never creates duplicates.

```bash
# Preview only — counts + a small sample, writes NOTHING
kb-engine --vault "<vault>" import-things --status open --dry-run --json

# Real import — writes Knowledge/inbox/<slug>.md stubs
kb-engine --vault "<vault>" import-things --status open
```

Flags:

- `--things-db PATH` — Things SQLite path. Default: the standard
  `~/Library/Group Containers/*ThingsMac*/**/main.sqlite` (first match); a clear
  error is raised if not found.
- `--status open|completed|all` — which task status to import (default `open`).
- `--area NAME` / `--project NAME` — restrict to an area/project by title
  (repeatable).
- `--date YYYY-MM-DD` — `date_added` stamped on stubs (default: today). The
  date is applied by the CLI, not the engine core, so the writer stays
  deterministic.
- `--dry-run` — report what would happen without writing.
- `--json` — machine-readable output.

`--dry-run --json` emits `{dry_run:true, things_db, status, n_tasks, n_urls,
would_write, would_skip_existing, sample:[{url, title}]}`. A real run emits
`{dry_run:false, written, skipped_existing, skipped_dup_in_batch}`. Each stub
carries frontmatter `{title, url, source, date_added, summary:"",
status:"inbox", context:"Imported from Things", tags:[]}` and a `## Notes`
body — ready to flow through the normal inbox-processing pipeline.

## Digest

`digest` writes a deterministic KB state report to `<vault>/_system/kb-digest.md`
— the weekly review entry point. Sections: **This week** (recent captures grouped
by area, one-liner each), **Review queue** (borderline notes awaiting a topic
decision), **Resurfacing** (notes related to recent work, plus aging/anniversary
nudges), **Health** (a one-line strip: recall@5 · areas · content% · inbox ·
unfiled · evicted), and **Synthesize** (topics big enough to be worth a wiki). A
**Status** header is prepended when the pipeline writes it. The body is keyed off
`today` with no finer timestamp, so re-running the same day rewrites a
byte-identical file (idempotent); `_system/` lives outside `Knowledge/`, so it is
never embedded.

```bash
kb-engine --vault "<vault>" digest          # writes the file + one-line summary
kb-engine --vault "<vault>" digest --json
```

`--json` emits `{inbox, proposals, topics, areas, unfiled, digest_path}`.

## Scheduled pipeline

`pipeline` is the **deterministic, LLM-free** maintenance command that runs
unattended, in two tiers:

- **`--tier daily`** — `import-mail` → `enrich` → `sync` → `digest`.
- **`--tier weekly`** (default) — the daily steps, plus **`topics apply --status
  active`** (write `area/<slug>` + `topic/<slug>` tags, **only for approved
  topics** — proposals stay `proposed`, so an unattended run never silently
  mis-tags), the **weekly topic pass** (re-anchor → growth-gated thresholds →
  assign → queue the borderline band → cluster the residual into `proposed`
  topics), and a retrieval **eval**.

Each step is isolated so one failure never aborts the run; the digest (with a
status header) is written even on failure and every run is recorded. Enrichment
only runs with `ANTHROPIC_API_KEY` set — otherwise it skips, keeping the run
LLM-free.

```bash
kb-engine --vault "<vault>" pipeline                  # weekly tier, one-line summary
kb-engine --vault "<vault>" pipeline --tier daily --json
```

`--json` emits `{tier, ok, outcomes:[{name, ok, detail}], counts:{inbox, proposals,
unfiled, queue}, digest_path}`. Everything it touches is either the rebuildable engine
cache or the regenerable `_system/` digest — except the gated `apply`, which only ever
writes tags for topics you have already approved. That safety property is what makes it
sound to run on a schedule.

### Weekly cadence

The intended operating loop is **unattended pipeline + a short human review**:

- **Unattended (weekly):** a macOS **launchd** agent — defined by the Nix module
  `modules.dev.kb-engine.schedule` (enabled on behemoth) — runs
  `kb-engine --vault "<Main>" pipeline` every Monday at 09:00, then fires a
  notification ("KB digest ready — N to review"). Logs land in
  `~/Library/Logs/kb-engine-pipeline.{log,err}`. Toggle with
  `modules.dev.kb-engine.schedule.enable`; the run cadence is
  `modules.dev.kb-engine.schedule.calendar` (a launchd `StartCalendarInterval`).
- **Review (~5 min, human):** prompted by the nudge, the `kb` skill's **Review**
  operation (`/kb:review`) reads the digest and drives the judgment the engine
  omits — process new inbox items (`/kb:process`), name/approve topic proposals
  (`/kb:topics`), and optionally promote-then-`apply` newly approved topics.

So the engine keeps the cache and digest current and proposes structure, while
note mutation stays gated behind an approved, human-confirmed `apply`. The digest
nags weekly, so the backlog can't silently rot.

`import-things`, `digest`, and `pipeline` are the engine commands behind the
Phase-3b cadence (read Things → import to inbox → weekly pipeline → review).

## Synthesis candidates

`synthesis-candidates` lists topics that have enough material to be worth a wiki
article but **don't have one yet** — so synthesis stops going idle. A topic is a
candidate when it has `>= --min` members (default `5`) and no article exists at
`<vault>/Knowledge/wiki/<slug>.md` (filename match on the topic slug). Results are
sorted by member count, biggest first. It is **read-only** (reads the stored topics
+ scans `Knowledge/wiki/`); the actual wiki *writing* stays in the `kb` skill
(`/kb:synthesize`).

```bash
kb-engine --vault "<vault>" synthesis-candidates           # >=5 members, no wiki
kb-engine --vault "<vault>" synthesis-candidates --min 3 --json
```

`--json` emits `{candidates:[{slug, label, size}]}`.

## Dedup report

`dedup-report` lists near-duplicate note pairs — gist-vector cosine `>= --threshold`
(default `0.95`) — so accidental re-captures surface for review. It is **read-only**:
merging is a human decision (the `/kb:review` merge flow), never automatic.

```bash
kb-engine --vault "<vault>" dedup-report                    # pairs >= 0.95
kb-engine --vault "<vault>" dedup-report --threshold 0.9 --json
```

`--json` emits `{threshold, pairs:[{a, b, cosine}]}`, highest cosine first.

## Proactive surfacing (related)

`related` answers "what's relevant to what I'm working on now". Pass **exactly one**
of `--query` (free-text context/project) or `--to` (a vault-relative note path):

- `--query` reuses **hybrid search** (semantic + keyword, scoped to `Knowledge/`,
  excluding `inbox/`), the same retrieval behind `search`.
- `--to` takes the note's mean-pooled vector and ranks all **other** notes by cosine,
  **excluding the note itself**. A note with no stored vector yields no results.

```bash
kb-engine --vault "<vault>" related --query "long-term memory for AI agents" --limit 5
kb-engine --vault "<vault>" related --to "Knowledge/graph-memory.md" --json
```

`--json` emits `{hits:[{note_path, title, score}]}`, ranked best-first. Like `search`,
it is **read-only** and never mutates the vault.

## Development & testing

The bulk of the suite is torch-free: a deterministic `FakeEmbedder` plus temp
SQLite and fixture markdown. Run it with:

```bash
uv run pytest                 # fast unit suite (integration tests excluded)
uv run pytest --cov           # with coverage (≥80% on core logic modules)
```

Environment toggles:

- **`[ml]` extra** — installs `sentence-transformers` + `torch` + the pinned
  `transformers<5.0` / `einops` needed by jina-v3. Required to actually embed;
  not needed for the unit suite or `--help`.
- **`[topics]` extra** — installs `umap-learn` + `hdbscan` + `scikit-learn` for
  the real clusterer (`topics discover`) and the agglomerative grouping behind
  `topics areas`. Both import lazily; the unit suite uses a deterministic
  `FakeClusterer` / `FakeEmbedder` and needs neither the ML stack nor a model.
- **`KB_FAKE_EMBED=1`** — the CLI uses the deterministic `FakeEmbedder` instead
  of the real model. Used by the CLI tests to exercise `sync`/`search` without
  downloading a model.
- **`KB_FAKE_CLUSTER=0,0,-1`** — `topics discover` uses a `FakeClusterer` with
  the given comma-separated labels (`-1` = noise) instead of UMAP→HDBSCAN. Used
  by the CLI tests to exercise discovery deterministically without the ML stack.
- **`KB_RUN_INTEGRATION=1`** — opt in to the real-model/clustering integration
  tests, excluded from the default run:

  ```bash
  # real jina-v3 semantic ranking
  uv sync --extra ml --extra dev
  KB_RUN_INTEGRATION=1 uv run pytest tests/test_integration_real_model.py -m integration -v

  # real UMAP→HDBSCAN clustering on separated fixtures
  uv sync --extra topics --extra dev
  KB_RUN_INTEGRATION=1 uv run pytest tests/test_integration_clustering.py -m integration -v
  ```
