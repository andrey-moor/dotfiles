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
