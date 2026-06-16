# kb-engine

Local embedding + hybrid search engine for an Obsidian knowledge base.

The engine reads an Obsidian vault's markdown directly from the filesystem
(files-as-truth), embeds notes with a local jina-v3 model, stores float32
vectors in a SQLite cache with an FTS5 keyword index, and answers hybrid
(semantic + keyword) searches fused with Reciprocal Rank Fusion.

## Install

```bash
cd kb-engine
uv sync --extra dev           # base deps + pytest (no torch)
uv sync --extra ml --extra dev  # add the real jina-v3 model stack
```

## Usage

```bash
uv run kb-engine --help
```

The SQLite cache is always rebuildable from the vault.
