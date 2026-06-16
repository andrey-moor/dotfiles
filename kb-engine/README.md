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
  sha256) → section-aware, token-budgeted chunks.
- **Embed:** chunks → jina-v3 embeddings (local; via the `[ml]` optional extra)
  → float32 BLOBs in SQLite, with the chunk text mirrored into an FTS5 index.
- **Search:** cosine similarity (best chunk per note) ∪ FTS5 BM25, fused via RRF,
  scoped to the `Knowledge/` tree (excluding `Knowledge/inbox/`).
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
chunk vectors are mean-pooled, reduced with **UMAP** (`metric="cosine"`), and
clustered with **HDBSCAN**; unclustered notes are reported as an explicit
**unfiled** residual. Per topic the engine computes a unit-normalized centroid
and a keyword label (a simple c-TF-IDF over note titles + first chunks). Topics
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

`topics areas` groups discovered topics into broader **areas** by agglomerative
clustering (`scikit-learn`, `metric="cosine"`, `linkage="average"`) over the
topic centroids. The cut is tunable with `--threshold` (default `0.3`); a higher
threshold yields fewer, broader areas. Each run replaces the stored areas.

```bash
# Group the current topics into areas (run `topics discover` first)
kb-engine --vault "<vault>" topics areas
kb-engine --vault "<vault>" topics areas --threshold 0.4 --json
```

`--json` emits `{n_areas, areas:[{slug, label, topics:[slug...]}]}`.

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
2. **`topics discover --sticky`** — sticky re-discovery: notes scoring `>= --high`
   (default `0.55`) against an existing **active** topic stay fixed as its members; only
   the **residual** is clustered into new `discovered`/`proposed` topics. This preserves
   approved structure across re-runs (plain `discover` replaces all discovered topics).
   Manual topics (`topics add`) always survive.
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
6. **`topics apply`** — the **only note-mutating command**; running it IS the gate (there
   is no implicit apply elsewhere). Writes `topic/<slug>` tags into member notes (see
   below).

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

#### `topic/<slug>` tag convention (apply)

`topics apply` writes membership back into notes as frontmatter tags namespaced under
`topic/` — e.g. a note in topic `rust-async-tokio` gains the tag `topic/rust-async-tokio`.
This namespace keeps machine-assigned topic tags distinct from the human taxonomy
(`Dev/Rust`, `AI/RAG`, …). It defaults to `--status active`, so `proposed` topics stay
proposed until promoted; only members of topics with the given status are tagged. Tags are
de-duplicated, the note body and other frontmatter are preserved, and member files missing
on disk are skipped and reported (`skipped_missing`). Re-running adds nothing new.

```bash
kb-engine --vault "<vault>" topics apply --status active --json
```

`--json` emits `{status, n_changed, n_tags_added, skipped_missing}`.

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
— a single glance at what needs attention: inbox backlog, topic proposals
awaiting naming/approval, topic/area counts, and unfiled notes (with a "needs
review" checklist). The body contains **no timestamps**, so re-running rewrites a
byte-identical file (idempotent); `_system/` lives outside `Knowledge/`, so it is
never embedded.

```bash
kb-engine --vault "<vault>" digest          # writes the file + one-line summary
kb-engine --vault "<vault>" digest --json
```

`--json` emits `{inbox, proposals, topics, areas, unfiled, digest_path}`.

`import-things` and `digest` are the two engine commands the Phase-3b scheduled
pipeline drives (read Things → import to inbox → process → refresh digest).

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
