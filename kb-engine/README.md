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
- **`KB_FAKE_EMBED=1`** — the CLI uses the deterministic `FakeEmbedder` instead
  of the real model. Used by the CLI tests to exercise `sync`/`search` without
  downloading a model.
- **`KB_RUN_INTEGRATION=1`** — opt in to the single real-model integration test
  (`tests/test_integration_real_model.py`), which loads jina-v3 and asserts
  semantic ranking on fixtures:

  ```bash
  uv sync --extra ml --extra dev
  KB_RUN_INTEGRATION=1 uv run pytest tests/test_integration_real_model.py -m integration -v
  ```
