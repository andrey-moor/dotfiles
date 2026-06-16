# KB Phase 1 — kb-engine Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task with TDD. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build `kb-engine` — a local, in-repo Python CLI that embeds the Obsidian KB, stores vectors in SQLite, and answers hybrid (semantic + keyword) searches — delivering the spec's #1 retrieval fix and the substrate for Phases 2–4.

**Architecture:** A uv project at `kb-engine/` (package `kb_engine`). The engine reads the Obsidian vault's markdown **directly from the filesystem** (files-as-truth). Notes → chunks → jina-v3 embeddings (local, via an `[ml]` optional extra) → float32 BLOBs in a SQLite cache with an FTS5 keyword index. Search fuses cosine similarity and FTS5 BM25 via Reciprocal Rank Fusion. Sync is hash-based incremental (embed new/changed, drop deleted); the cache is always rebuildable from the vault. A `click` CLI exposes `sync`/`search`/`status`/`rebuild` with `--json`.

**Tech Stack:** Python ≥3.11, uv, `click`, `python-frontmatter`, `pyyaml`, `numpy`, `semantic-text-splitter`, stdlib `sqlite3` (FTS5). ML extra (`[ml]`): `sentence-transformers`, `torch>=2.2`, `transformers>=4.40,<5.0`, `huggingface-hub`, `tokenizers`, `einops` (proven pins reused from orrery-engine — the `<5.0` transformers bound and `einops` are required for `jinaai/jina-embeddings-v3`). Tests: `pytest`, `pytest-cov`.

---

## Testing strategy (read first)

- **Unit tests** use a `FakeEmbedder` (deterministic vectors derived from text — no torch, no model download) + temp SQLite + fixture markdown in `tmp_path`. These are the bulk; they run in seconds via plain `uv run pytest`.
- **One integration test** (`tests/test_integration_real_model.py`, marked `@pytest.mark.integration`) loads the real jina-v3 model and asserts semantic ranking on fixtures. Skipped unless `KB_RUN_INTEGRATION=1` and the `[ml]` extra is installed — so CI/default runs stay fast.
- Coverage target **≥80%** on logic modules (`vault`, `chunking`, `store`, `sync`, `search`), enforced via `pytest --cov`.
- The real embedder (`LocalJinaEmbedder`) imports torch lazily **inside the method**, so importing `kb_engine` never requires torch.

## File structure

```
kb-engine/
├── pyproject.toml              # uv project, pinned deps, [ml] extra, pytest/cov config
├── README.md                   # what it is, install, CLI usage
├── src/kb_engine/
│   ├── __init__.py
│   ├── config.py               # Config dataclass: vault_path, db_path, model_name, chunk tokens
│   ├── models.py               # plain dataclasses: Note, Chunk, SearchHit
│   ├── vault.py                # read vault .md → Note (frontmatter, body, tags, wikilinks, sha256)
│   ├── chunking.py             # Note → list[Chunk] (section-aware, token-budgeted)
│   ├── embeddings.py           # Embedder protocol; FakeEmbedder; LocalJinaEmbedder (lazy torch)
│   ├── store.py                # SQLite schema + CRUD; float32 BLOB vectors; FTS5 keyword index
│   ├── sync.py                 # files-as-truth incremental sync + rebuild
│   ├── search.py               # cosine + FTS5 + RRF fusion; path scoping
│   └── cli.py                  # click CLI: sync/search/status/rebuild, --json
└── tests/
    ├── conftest.py             # fixtures: tmp vault, FakeEmbedder, in-memory store
    ├── fixtures/notes/*.md     # sample Obsidian notes
    ├── test_vault.py
    ├── test_chunking.py
    ├── test_embeddings.py
    ├── test_store.py
    ├── test_sync.py
    ├── test_search.py
    ├── test_cli.py
    └── test_integration_real_model.py
```

The package also gets wired onto `PATH` for the `kb` skill in the final task.

---

### Task 1: Project scaffold

**Files:**
- Create: `kb-engine/pyproject.toml`, `kb-engine/src/kb_engine/__init__.py`, `kb-engine/README.md`, `kb-engine/tests/conftest.py`, `kb-engine/.gitignore`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling>=1.27.0"]
build-backend = "hatchling.build"

[project]
name = "kb-engine"
version = "0.1.0"
description = "Local embedding + hybrid search engine for an Obsidian knowledge base."
requires-python = ">=3.11"
dependencies = [
    "click>=8.1.7",
    "pyyaml>=6.0.1",
    "python-frontmatter>=1.1.0",
    "numpy>=1.26.0",
    "semantic-text-splitter>=0.13.0",
]

[project.optional-dependencies]
ml = [
    "sentence-transformers>=3.0.0",
    "torch>=2.2.0",
    "transformers>=4.40.0,<5.0",
    "huggingface-hub>=0.24.0",
    "tokenizers>=0.20.0",
    "einops>=0.7.0",
]
dev = ["pytest>=8.0.0", "pytest-cov>=5.0.0"]

[project.scripts]
kb-engine = "kb_engine.cli:main"

[tool.pytest.ini_options]
markers = ["integration: requires the real jina model (set KB_RUN_INTEGRATION=1)"]
addopts = "-m 'not integration'"

[tool.coverage.run]
source = ["kb_engine"]
```

- [ ] **Step 2: Create the package + a stub CLI so the entry point resolves**

`src/kb_engine/__init__.py`:
```python
__version__ = "0.1.0"
```

Create a minimal `src/kb_engine/cli.py` placeholder so `kb-engine --help` works:
```python
import click

@click.group()
def main() -> None:
    """kb-engine — local embedding + hybrid search for an Obsidian KB."""

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: `.gitignore`** — ignore `.venv/`, `__pycache__/`, `*.db`, `.pytest_cache/`, `.coverage`.

- [ ] **Step 4: Install + verify the toolchain**

Run:
```bash
cd kb-engine && uv sync --extra dev
uv run kb-engine --help
uv run pytest -q
```
Expected: help text prints; pytest reports "no tests ran" (exit 5 ok) — environment works without the `[ml]`/torch install.

- [ ] **Step 5: Commit**
```bash
cd /Users/andreym/Documents/dotfiles
git add kb-engine/pyproject.toml kb-engine/src kb-engine/README.md kb-engine/tests/conftest.py kb-engine/.gitignore kb-engine/uv.lock
git commit -m "feat(kb-engine): scaffold uv project with pinned jina deps"
```

---

### Task 2: Config + models

**Files:** Create `src/kb_engine/config.py`, `src/kb_engine/models.py`, `tests/test_config.py`

- [ ] **Step 1: Write failing test** (`tests/test_config.py`)
```python
from pathlib import Path
from kb_engine.config import Config

def test_default_db_path_is_under_state_dir(tmp_path):
    cfg = Config(vault_path=tmp_path)
    assert cfg.vault_path == tmp_path
    assert cfg.db_path.name == "kb-engine.db"
    assert cfg.model_name == "jinaai/jina-embeddings-v3"
    assert cfg.embed_dim == 1024

def test_knowledge_dir_scopes_to_knowledge_subfolder(tmp_path):
    cfg = Config(vault_path=tmp_path)
    assert cfg.knowledge_dir == tmp_path / "Knowledge"
```

- [ ] **Step 2: Run → fail.** `uv run pytest tests/test_config.py` → ImportError.

- [ ] **Step 3: Implement `config.py`**
```python
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MODEL = "jinaai/jina-embeddings-v3"
DEFAULT_EMBED_DIM = 1024
DEFAULT_CHUNK_TOKENS = 512

def _default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / "kb-engine"

@dataclass(frozen=True)
class Config:
    vault_path: Path
    db_path: Path = field(default=None)  # type: ignore[assignment]
    model_name: str = DEFAULT_MODEL
    embed_dim: int = DEFAULT_EMBED_DIM
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS

    def __post_init__(self) -> None:
        if self.db_path is None:
            object.__setattr__(self, "db_path", _default_state_dir() / "kb-engine.db")

    @property
    def knowledge_dir(self) -> Path:
        return self.vault_path / "Knowledge"
```

- [ ] **Step 4: Define `models.py`** (used by later tasks)
```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Note:
    path: str           # vault-relative path, e.g. "Knowledge/foo.md"
    title: str
    body: str
    tags: tuple[str, ...]
    wikilinks: tuple[str, ...]
    frontmatter: dict
    sha256: str

@dataclass(frozen=True)
class Chunk:
    note_path: str
    ordinal: int
    text: str

@dataclass(frozen=True)
class SearchHit:
    note_path: str
    title: str
    score: float
    snippet: str
```

- [ ] **Step 5: Run → pass; commit** `feat(kb-engine): add config and core dataclasses`

---

### Task 3: Vault reader

**Files:** Create `src/kb_engine/vault.py`, `tests/test_vault.py`, `tests/fixtures/notes/*.md`

- [ ] **Step 1: Add fixture notes** under `tests/fixtures/notes/` — at minimum:
  - `rag.md`: frontmatter `title, tags: [AI/RAG], url`; body with a `## Notes` section, an inline `#extra` tag, and a `[[colbert]]` wikilink.
  - `empty-tags.md`: valid frontmatter, `tags: []`.

- [ ] **Step 2: Write failing tests** (`tests/test_vault.py`)
```python
from pathlib import Path
from kb_engine.vault import read_note, iter_notes

FIX = Path(__file__).parent / "fixtures" / "notes"

def test_read_note_parses_frontmatter_tags_and_wikilinks():
    note = read_note(FIX / "rag.md", base=FIX)
    assert note.title  # from frontmatter title
    assert "AI/RAG" in note.tags          # frontmatter tag
    assert "extra" in note.tags           # inline #extra tag, deduped, no '#'
    assert "colbert" in note.wikilinks    # [[colbert]] → "colbert"
    assert len(note.sha256) == 64

def test_iter_notes_skips_non_md_and_returns_relative_paths(tmp_path):
    (tmp_path / "a.md").write_text("---\ntitle: A\n---\nbody")
    (tmp_path / "ignore.txt").write_text("nope")
    notes = list(iter_notes(tmp_path))
    assert [n.path for n in notes] == ["a.md"]
```

- [ ] **Step 3: Run → fail.**

- [ ] **Step 4: Implement `vault.py`** — use `frontmatter.load`; extract tags from frontmatter `tags` (list) **plus** inline `#tag` regex (strip leading `#`, dedupe, preserve `Category/Sub`); extract `[[wikilink]]` via regex (take target before any `|`); compute `sha256` over the raw file bytes; `path` is `file.relative_to(base)` as posix. `iter_notes(root)` walks `*.md` recursively, sorted, skips non-`.md`.

- [ ] **Step 5: Run → pass; commit** `feat(kb-engine): vault reader (frontmatter, tags, wikilinks, hash)`

---

### Task 4: Chunking

**Files:** Create `src/kb_engine/chunking.py`, `tests/test_chunking.py`

- [ ] **Step 1: Write failing tests** (`tests/test_chunking.py`)
```python
from kb_engine.chunking import chunk_note
from kb_engine.models import Note

def _note(body: str) -> Note:
    return Note(path="Knowledge/x.md", title="X", body=body, tags=(), wikilinks=(), frontmatter={}, sha256="0"*64)

def test_short_note_is_single_chunk_prefixed_with_title():
    chunks = chunk_note(_note("hello world"), max_tokens=512)
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0
    assert "X" in chunks[0].text  # title prepended for context

def test_long_note_splits_into_multiple_ordered_chunks():
    body = "\n\n".join(f"## Section {i}\n" + ("word " * 300) for i in range(4))
    chunks = chunk_note(_note(body), max_tokens=256)
    assert len(chunks) > 1
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `chunking.py`** — prepend the title to the first chunk for retrieval context; use `semantic_text_splitter.TextSplitter.from_tiktoken_model` is unavailable offline, so use `semantic_text_splitter.TextSplitter(capacity=max_tokens)` (character/token capacity splitter) over `title + "\n\n" + body`; return `Chunk(note_path, ordinal, text)` list. Empty/whitespace body → one chunk of just the title.

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): section-aware note chunking`

---

### Task 5: Embeddings (protocol + fake + real)

**Files:** Create `src/kb_engine/embeddings.py`, `tests/test_embeddings.py`

- [ ] **Step 1: Write failing tests** (unit — fake only)
```python
import numpy as np
from kb_engine.embeddings import FakeEmbedder

def test_fake_embedder_is_deterministic_and_unit_dim():
    e = FakeEmbedder(dim=8)
    a1 = e.embed_passages(["hello"])[0]
    a2 = e.embed_passages(["hello"])[0]
    assert a1.shape == (8,)
    assert np.allclose(a1, a2)              # deterministic
    assert not np.allclose(a1, e.embed_passages(["world"])[0])

def test_fake_query_matches_same_text_passage_closely():
    e = FakeEmbedder(dim=16)
    p = e.embed_passages(["graph memory"])[0]
    q = e.embed_query("graph memory")
    assert float(p @ q) > 0.99             # same text → near-identical vector
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `embeddings.py`**
```python
from typing import Protocol
import hashlib
import numpy as np

class Embedder(Protocol):
    dim: int
    def embed_passages(self, texts: list[str]) -> list[np.ndarray]: ...
    def embed_query(self, text: str) -> np.ndarray: ...

class FakeEmbedder:
    """Deterministic, torch-free embedder for tests: seeded by text hash."""
    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim
    def _vec(self, text: str) -> np.ndarray:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(self.dim).astype(np.float32)
        return v / (np.linalg.norm(v) + 1e-9)
    def embed_passages(self, texts: list[str]) -> list[np.ndarray]:
        return [self._vec(t) for t in texts]
    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)

class LocalJinaEmbedder:
    """Real jina-v3 embedder. torch/sentence-transformers imported lazily."""
    def __init__(self, model_name: str = "jinaai/jina-embeddings-v3", dim: int = 1024) -> None:
        self.model_name = model_name
        self.dim = dim
        self._model = None
    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy
            self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
        return self._model
    def embed_passages(self, texts: list[str]) -> list[np.ndarray]:
        m = self._load()
        arr = m.encode(texts, task="retrieval.passage", normalize_embeddings=True)
        return [a.astype(np.float32) for a in arr]
    def embed_query(self, text: str) -> np.ndarray:
        m = self._load()
        return m.encode([text], task="retrieval.query", normalize_embeddings=True)[0].astype(np.float32)
```

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): embedder protocol, fake + jina-v3 impl`

---

### Task 6: SQLite store

**Files:** Create `src/kb_engine/store.py`, `tests/test_store.py`

- [ ] **Step 1: Write failing tests**
```python
import numpy as np
from kb_engine.store import Store

def test_upsert_and_fetch_note_and_vectors(tmp_path):
    s = Store(tmp_path / "t.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h1", tags=["AI/RAG"])
    s.replace_chunks("Knowledge/a.md", [(0, "A body", np.ones(4, np.float32))])
    assert s.note_sha("Knowledge/a.md") == "h1"
    rows = list(s.iter_vectors())
    assert rows[0][0] == "Knowledge/a.md" and rows[0][2].shape == (4,)

def test_delete_note_cascades_chunks_and_fts(tmp_path):
    s = Store(tmp_path / "t.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.replace_chunks("Knowledge/a.md", [(0, "alpha beta", np.ones(4, np.float32))])
    s.delete_note("Knowledge/a.md")
    assert s.note_sha("Knowledge/a.md") is None
    assert list(s.iter_vectors()) == []
    assert s.keyword_search("alpha", limit=5) == []

def test_keyword_search_uses_fts(tmp_path):
    s = Store(tmp_path / "t.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="Memory", sha256="h", tags=[])
    s.replace_chunks("Knowledge/a.md", [(0, "long term memory for agents", np.ones(4, np.float32))])
    hits = s.keyword_search("memory", limit=5)
    assert hits and hits[0][0] == "Knowledge/a.md"
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `store.py`** — schema:
```sql
CREATE TABLE IF NOT EXISTS notes (
  path TEXT PRIMARY KEY, title TEXT, sha256 TEXT NOT NULL, tags TEXT  -- tags = JSON array
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY, note_path TEXT NOT NULL, ordinal INTEGER NOT NULL,
  text TEXT NOT NULL, vector BLOB NOT NULL,
  FOREIGN KEY(note_path) REFERENCES notes(path) ON DELETE CASCADE
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, note_path UNINDEXED);
```
Vectors stored via `np.asarray(v, np.float32).tobytes()`; read back with `np.frombuffer(blob, np.float32)`. Enable `PRAGMA foreign_keys=ON`. `replace_chunks` deletes existing chunks+fts rows for the note then inserts (keeps FTS in sync manually since it's not a content-table). `keyword_search(query, limit)` runs `SELECT note_path, bm25(chunks_fts) ... ORDER BY rank LIMIT ?` returning `(note_path, score)`; sanitize the query for FTS (quote terms). `iter_vectors()` yields `(note_path, ordinal, np.ndarray)`.

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): sqlite store with float32 vectors + fts5`

---

### Task 7: Sync (files-as-truth)

**Files:** Create `src/kb_engine/sync.py`, `tests/test_sync.py`

- [ ] **Step 1: Write failing tests** (use FakeEmbedder)
```python
from kb_engine.sync import sync, SyncStats
from kb_engine.store import Store
from kb_engine.embeddings import FakeEmbedder
from kb_engine.config import Config

def _vault(tmp_path):
    k = tmp_path / "Knowledge"; k.mkdir()
    (k / "a.md").write_text("---\ntitle: A\ntags: [AI/RAG]\n---\nalpha content")
    return tmp_path

def test_initial_sync_embeds_all(tmp_path):
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path/"t.db")
    st = sync(cfg, Store(cfg.db_path), FakeEmbedder(dim=16))
    assert st.added == 1 and st.changed == 0 and st.deleted == 0

def test_second_sync_is_noop_when_unchanged(tmp_path):
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path/"t.db")
    store = Store(cfg.db_path)
    sync(cfg, store, FakeEmbedder(dim=16))
    st2 = sync(cfg, store, FakeEmbedder(dim=16))
    assert st2.added == 0 and st2.changed == 0

def test_edit_triggers_reembed_and_delete_removes(tmp_path):
    v = _vault(tmp_path); cfg = Config(vault_path=v, db_path=tmp_path/"t.db")
    store = Store(cfg.db_path); sync(cfg, store, FakeEmbedder(dim=16))
    (v/"Knowledge"/"a.md").write_text("---\ntitle: A\n---\nDIFFERENT body now")
    assert sync(cfg, store, FakeEmbedder(dim=16)).changed == 1
    (v/"Knowledge"/"a.md").unlink()
    assert sync(cfg, store, FakeEmbedder(dim=16)).deleted == 1
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `sync.py`** — `sync(cfg, store, embedder) -> SyncStats`:
  1. `store.init_schema()`.
  2. Read disk notes via `vault.iter_notes(cfg.knowledge_dir)`; build `{path: Note}`. Skip the `inbox/` and `wiki/` subdirs? **No** — embed all of `Knowledge/` incl. `wiki/`; exclude `inbox/` (unprocessed). (Path filter: skip paths starting with `inbox/`.)
  3. DB state via `store.all_note_shas() -> {path: sha}`.
  4. Diff: `added` = on disk not in DB; `changed` = sha differs; `deleted` = in DB not on disk.
  5. For added+changed: `chunk_note` → `embed_passages` → `store.upsert_note` + `store.replace_chunks`.
  6. For deleted: `store.delete_note`.
  7. Return `SyncStats(added, changed, deleted)` (a frozen dataclass).
  `rebuild(cfg, store, embedder)` drops all tables then calls `sync`.

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): hash-based incremental sync + rebuild`

---

### Task 8: Hybrid search (cosine + FTS5 + RRF)

**Files:** Create `src/kb_engine/search.py`, `tests/test_search.py`

- [ ] **Step 1: Write failing tests**
```python
import numpy as np
from kb_engine.search import semantic_search, hybrid_search, rrf_fuse

def test_rrf_fuse_rewards_agreement():
    sem = [("a", 0.9), ("b", 0.5)]
    kw  = [("b", 10.0), ("a", 1.0)]
    fused = rrf_fuse([sem, kw], k=60)
    assert {p for p, _ in fused} == {"a", "b"}
    # both ranked high in one list each → close scores, both present
    assert len(fused) == 2

def test_semantic_search_ranks_nearest(tmp_path):
    from kb_engine.store import Store
    from kb_engine.embeddings import FakeEmbedder
    s = Store(tmp_path/"t.db"); s.init_schema(); e = FakeEmbedder(dim=32)
    for p, txt in [("Knowledge/mem.md","long term memory"),("Knowledge/rust.md","rust macros")]:
        s.upsert_note(path=p, title=p, sha256="h", tags=[])
        s.replace_chunks(p, [(0, txt, e.embed_passages([txt])[0])])
    hits = semantic_search(s, e, "memory for an assistant", limit=2)
    assert hits[0][0] == "Knowledge/mem.md"   # nearer than rust
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `search.py`**
```python
import numpy as np

def semantic_search(store, embedder, query, limit=20):
    q = embedder.embed_query(query)
    scored: dict[str, float] = {}
    for note_path, _ordinal, vec in store.iter_vectors():
        s = float(q @ vec)                       # both unit-normalized → cosine
        if s > scored.get(note_path, -1.0):
            scored[note_path] = s                # best chunk per note
    return sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:limit]

def rrf_fuse(ranked_lists, k=60, limit=20):
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, (path, _score) in enumerate(lst):
            scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]

def hybrid_search(store, embedder, query, limit=20, scope_prefix="Knowledge/"):
    sem = semantic_search(store, embedder, query, limit=limit*2)
    kw  = store.keyword_search(query, limit=limit*2)   # [(path, bm25)]
    fused = rrf_fuse([sem, kw], limit=limit*2)
    fused = [(p, s) for p, s in fused if p.startswith(scope_prefix)
             and not p.startswith(scope_prefix + "inbox/")]
    return fused[:limit]
```

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): hybrid search with RRF fusion + path scoping`

---

### Task 9: CLI

**Files:** Replace `src/kb_engine/cli.py`; create `tests/test_cli.py`

- [ ] **Step 1: Write failing tests** (click's `CliRunner`, FakeEmbedder via `KB_FAKE_EMBED=1`)
```python
import json, os
from click.testing import CliRunner
from kb_engine.cli import main

def _vault(tmp_path):
    k = tmp_path/"Knowledge"; k.mkdir()
    (k/"mem.md").write_text("---\ntitle: Memory\ntags: [AI]\n---\nlong term memory for agents")
    return tmp_path

def test_sync_then_search_json(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    v = _vault(tmp_path); db = tmp_path/"t.db"
    r = CliRunner().invoke(main, ["--vault", str(v), "--db", str(db), "sync", "--json"])
    assert r.exit_code == 0 and json.loads(r.output)["added"] == 1
    r2 = CliRunner().invoke(main, ["--vault", str(v), "--db", str(db), "search", "memory", "--json"])
    assert r2.exit_code == 0
    hits = json.loads(r2.output)["hits"]
    assert hits and hits[0]["note_path"] == "Knowledge/mem.md"
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `cli.py`** — a `click.group` with `--vault` and `--db` options stored on `ctx.obj` (Config). An embedder factory: if `KB_FAKE_EMBED=1` → `FakeEmbedder(dim=cfg.embed_dim)` else `LocalJinaEmbedder(cfg.model_name, cfg.embed_dim)`. Commands:
  - `sync [--json]` → run `sync()`, print stats (human or JSON `{added, changed, deleted}`).
  - `search QUERY [--limit] [--json]` → `hybrid_search`, resolve titles from store, print hits (JSON `{hits: [{note_path, title, score}]}`).
  - `status [--json]` → counts: notes, chunks, db path, last sync (mtime of db).
  - `rebuild [--json]` → `rebuild()`.
  `main` is the group; `[project.scripts]` already points to `kb_engine.cli:main`.

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): click CLI (sync/search/status/rebuild, --json)`

---

### Task 10: Real-model integration test

**Files:** Create `tests/test_integration_real_model.py`

- [ ] **Step 1: Write the integration test** (skipped unless opted in)
```python
import os, numpy as np, pytest
pytestmark = pytest.mark.integration

@pytest.mark.skipif(os.getenv("KB_RUN_INTEGRATION") != "1", reason="set KB_RUN_INTEGRATION=1")
def test_real_jina_ranks_semantically(tmp_path):
    from kb_engine.embeddings import LocalJinaEmbedder
    from kb_engine.store import Store
    from kb_engine.search import semantic_search
    e = LocalJinaEmbedder()
    s = Store(tmp_path/"t.db"); s.init_schema()
    docs = {"Knowledge/mem.md": "giving an AI assistant long-term memory",
            "Knowledge/fan.md": "replacing a bathroom exhaust fan"}
    for p, t in docs.items():
        s.upsert_note(path=p, title=p, sha256="h", tags=[])
        s.replace_chunks(p, [(0, t, e.embed_passages([t])[0])])
    hits = semantic_search(s, e, "how do I give my AI agent persistent memory", limit=2)
    assert hits[0][0] == "Knowledge/mem.md"   # the review's failing keyword query now works
```

- [ ] **Step 2: Run it for real once**
```bash
cd kb-engine && uv sync --extra ml --extra dev
KB_RUN_INTEGRATION=1 uv run pytest tests/test_integration_real_model.py -m integration -v
```
Expected: PASS (downloads jina-v3 on first run — may take minutes). If the model download or torch install fails in this environment, report it: the unit suite still fully validates logic; the integration gate documents the real-model contract.

- [ ] **Step 3: Commit** `test(kb-engine): real jina-v3 semantic ranking integration test`

---

### Task 11: Coverage gate + full suite

- [ ] **Step 1:** Run `cd kb-engine && uv run pytest --cov --cov-report=term-missing`.
- [ ] **Step 2:** Ensure ≥80% on `vault`, `chunking`, `store`, `sync`, `search`. Add targeted unit tests for any uncovered branch (e.g. empty-body chunk, FTS query sanitization, deleted-note scope filter).
- [ ] **Step 3: Commit** `test(kb-engine): raise coverage to >=80% on core modules`

---

### Task 12: Wire into the dotfiles environment + README

**Files:** Create `modules/home/dev/kb-engine.nix`; update `kb-engine/README.md`

- [ ] **Step 1:** Write `modules/home/dev/kb-engine.nix` following the repo's module pattern (`options.modules.dev.kb-engine.enable = mkEnableOption`). On enable, install a wrapper script on `PATH` named `kb-engine` that runs the project via uv:
```nix
{ lib, config, pkgs, ... }:
with lib;
let cfg = config.modules.dev.kb-engine;
    kbEngine = pkgs.writeShellScriptBin "kb-engine" ''
      exec ${pkgs.uv}/bin/uv run --project ${config.modules.dotfilesDir}/kb-engine \
        --extra ml kb-engine "$@"
    '';
in {
  options.modules.dev.kb-engine.enable = mkEnableOption "kb-engine local KB search";
  config = mkIf cfg.enable { home.packages = [ kbEngine pkgs.uv ]; };
}
```
(Verify `config.modules.dotfilesDir` exists per CLAUDE.md; if the option name differs, match the repo's actual option.)

- [ ] **Step 2:** Enable it in the behemoth host config (`modules.dev.kb-engine.enable = true;`).

- [ ] **Step 3:** Validate the module evaluates: `just build` (or `nix flake check`). Do NOT run `just switch` (that mutates the live system) unless the user asks — report that the module builds and is ready to activate.

- [ ] **Step 4:** Flesh out `kb-engine/README.md` — what it is, `uv sync --extra ml`, CLI examples (`kb-engine --vault <path> sync`, `search`), the files-as-truth/rebuild note, and that it's the foundation for Phases 2–4.

- [ ] **Step 5: Commit** `feat(kb-engine): nix module + wrapper, enable on behemoth, README`

---

## Self-review

- **Spec coverage (§3 architecture, §6 retrieval):** local jina embeddings ✓ (T5), SQLite float32 cache ✓ (T6), correct Obsidian ingest incl. frontmatter/tags/wikilinks ✓ (T3), files-as-truth hash sync + rebuild ✓ (T7), hybrid semantic∪keyword search w/ path scoping ✓ (T8), CLI `--json` ✓ (T9), in-repo + Nix-wired ✓ (T12). Per-topic centroids, clustering, areas, proactive surfacing = **Phase 2+** (out of scope here).
- **No placeholders:** schema, embedder protocol, cosine/RRF, sync diff, and representative tests are concrete code. Boilerplate (CLI glue, README) is specified by interface + tests.
- **Type consistency:** `Store` methods (`init_schema`, `upsert_note`, `replace_chunks`, `note_sha`, `all_note_shas`, `delete_note`, `iter_vectors`, `keyword_search`) are used identically across T6–T9. `Embedder` protocol (`embed_passages`/`embed_query`/`dim`) consistent T5/T7/T8. `SyncStats(added, changed, deleted)` consistent T7/T9.
- **Risk:** the only environment-dependent step is T10 (real torch+model). It's isolated and opt-in; all logic is validated torch-free, so a heavy-dep hiccup never blocks the build.
```
