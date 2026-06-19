# KB Topic Layer v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sharpen and broaden the KB topic layer via summary-anchored embeddings, primary+secondary multi-topic membership, and a two-tier (taxonomy/topic) navigation model.

**Architecture:** Incremental changes to the in-repo `kb-engine` (UMAP→HDBSCAN leaf clustering, sqlite vector+FTS cache, hybrid search). Three independently-shippable phases. Spec: `docs/superpowers/specs/2026-06-19-kb-topic-layer-v2-design.md`.

**Tech Stack:** Python `kb_engine`; sqlite3 (vectors + FTS5); local jina-v3 embeddings; UMAP/HDBSCAN; `python-frontmatter`; click CLI; pytest (FakeEmbedder/FakeClusterer keep unit tests torch-free).

**Working dir for all commands:** `/Users/andreym/Documents/dotfiles/kb-engine` (run `uv run pytest -q` there). Branch: `feat/kb-topic-layer-v2`.

---

## File Structure

| File | Phase | Responsibility / change |
|------|-------|-------------------------|
| `src/kb_engine/chunking.py` | 1 | add `embedding_text(note)` (title+summary, fallback to body) + `fts_text(note)` |
| `src/kb_engine/store.py` | 1,2,3 | `notes.summary` column; `topic_members.is_primary` column; `note_texts` from summary; `upsert_note` summary; `set_members`/`save_topics` write is_primary; `topic_members` reads it; `notes_without_topic()` |
| `src/kb_engine/sync.py` | 1 | `_index_note`: one summary vector + full-body FTS chunk + store summary |
| `src/kb_engine/models.py` | 2 | `TopicMember.is_primary: bool = True` |
| `src/kb_engine/topics/assignment.py` | 2 | `assign_notes` → primary + ≤2 secondaries |
| `src/kb_engine/topics/apply.py` | 2 | write `primary_topic` frontmatter field + all topic tags |
| `src/kb_engine/topics/render.py` | 2,3 | MOC primary/secondary split; `_unfiled-by-category.md` index |
| `src/kb_engine/topics/suggest.py` (new) | 3 | cluster the unfiled residual at `min_cluster_size=2` → proposals |
| `src/kb_engine/cli.py` | 1,2,3 | `--secondary` on assign; `topics suggest`; wire renders |
| `tests/test_*.py` | all | mirror each change (see tasks) |

**Schema migrations:** `init_schema()` runs `CREATE TABLE IF NOT EXISTS`, which does **not** add columns to an existing table. Each new column needs an idempotent `ALTER TABLE` guarded by a `PRAGMA table_info` check (Task 1.1, 2.1). The cache is rebuildable, so a `rebuild` is the fallback.

---

## PHASE 1 — Summary-anchored embeddings

### Task 1.1: `notes.summary` column + migration + `upsert_note`

**Files:**
- Modify: `src/kb_engine/store.py` (`_SCHEMA`, `init_schema`, `upsert_note`, add `note_summary`)
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
def test_upsert_note_stores_summary(tmp_path):
    from kb_engine.store import Store
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.upsert_note(path="Knowledge/a.md", title="A", summary="A short gist.",
                      sha256="x", tags=["AI/Agents"])
    assert store.note_summary("Knowledge/a.md") == "A short gist."
    store.close()


def test_init_schema_adds_summary_to_legacy_notes_table(tmp_path):
    # A DB created before the summary column must gain it on init_schema (idempotent).
    import sqlite3
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE notes (path TEXT PRIMARY KEY, title TEXT, sha256 TEXT NOT NULL, tags TEXT)")
    conn.commit(); conn.close()
    from kb_engine.store import Store
    store = Store(db)
    store.init_schema()  # must not raise
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(notes)")}
    assert "summary" in cols
    store.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_store.py -k "summary" -v`
Expected: FAIL — `upsert_note() got an unexpected keyword argument 'summary'` / `no attribute note_summary`.

- [ ] **Step 3: Implement**

In `_SCHEMA`, change the notes table to:
```sql
CREATE TABLE IF NOT EXISTS notes (
  path TEXT PRIMARY KEY, title TEXT, sha256 TEXT NOT NULL, tags TEXT, summary TEXT
);
```

Add a migration to `init_schema` (after `executescript`):
```python
    def init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._ensure_column("notes", "summary", "TEXT")
        self._conn.commit()

    def _ensure_column(self, table: str, column: str, decl: str) -> None:
        cols = {row[1] for row in self._conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
```

Update `upsert_note` to accept and store `summary`:
```python
    def upsert_note(
        self, path: str, title: str, summary: str, sha256: str, tags: list[str]
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO notes(path, title, summary, sha256, tags) VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET title=excluded.title,
                summary=excluded.summary, sha256=excluded.sha256, tags=excluded.tags
            """,
            (path, title, summary, sha256, json.dumps(list(tags))),
        )
        self._conn.commit()

    def note_summary(self, note_path: str) -> str | None:
        row = self._conn.execute(
            "SELECT summary FROM notes WHERE path=?", (note_path,)
        ).fetchone()
        return row[0] if row else None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_store.py -k "summary" -v` → PASS. (Other tests calling `upsert_note` positionally will break — fixed in Task 1.4's sync update and any test updates; run the full suite at the end of Step 4 and update callers in tests to pass `summary=""`.)

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/store.py tests/test_store.py
git commit -m "feat(kb-engine): add notes.summary column + migration"
```

### Task 1.2: `embedding_text()` / `fts_text()` helpers

**Files:**
- Modify: `src/kb_engine/chunking.py`
- Test: `tests/test_chunking.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_chunking.py
import types
from kb_engine.models import Note
from kb_engine.chunking import embedding_text, fts_text


def _note(title, body, summary):
    fm = types.MappingProxyType({"summary": summary} if summary is not None else {})
    return Note(path="Knowledge/a.md", title=title, body=body, tags=(),
                wikilinks=(), frontmatter=fm, sha256="x")


def test_embedding_text_uses_title_and_summary():
    n = _note("Rust Macros", "long body " * 100, "A guide to Rust macros.")
    assert embedding_text(n) == "Rust Macros\n\nA guide to Rust macros."


def test_embedding_text_falls_back_to_body_when_no_summary():
    n = _note("T", "B" * 500, "")
    out = embedding_text(n)
    assert out.startswith("T\n\n") and len(out) <= 3 + 280 + len("T")


def test_embedding_text_title_only_when_empty_body_and_summary():
    assert embedding_text(_note("Only Title", "", "")) == "Only Title"


def test_fts_text_is_title_plus_full_body():
    n = _note("T", "the whole body here", "short gist")
    assert fts_text(n) == "T\n\nthe whole body here"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_chunking.py -k "embedding_text or fts_text" -v`
Expected: FAIL — `cannot import name 'embedding_text'`.

- [ ] **Step 3: Implement**

Add to `src/kb_engine/chunking.py`:
```python
_BODY_FALLBACK_CHARS = 280


def _summary_of(note: Note) -> str:
    value = note.frontmatter.get("summary") if note.frontmatter else None
    return str(value).strip() if value else ""


def embedding_text(note: Note) -> str:
    """Text embedded into the note's semantic vector: title + summary.

    Falls back to the first ``_BODY_FALLBACK_CHARS`` of the body when there is no
    summary, and to the title alone when both are empty.
    """
    summary = _summary_of(note)
    if not summary:
        summary = note.body.strip()[:_BODY_FALLBACK_CHARS]
    title = note.title.strip()
    return f"{title}\n\n{summary}" if summary else title


def fts_text(note: Note) -> str:
    """Full text indexed for keyword (FTS) recall: title + full body."""
    body = note.body.strip()
    title = note.title.strip()
    return f"{title}\n\n{body}" if body else title
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_chunking.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/chunking.py tests/test_chunking.py
git commit -m "feat(kb-engine): embedding_text/fts_text (summary-anchored vectors)"
```

### Task 1.3: `note_texts()` uses summary for labels

**Files:**
- Modify: `src/kb_engine/store.py` (`note_texts`)
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
def test_note_texts_uses_title_and_summary_not_body(tmp_path):
    import numpy as np
    from kb_engine.store import Store
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.upsert_note("Knowledge/a.md", "Rust Macros", "Guide to declarative macros.",
                      "x", ["Dev/Rust"])
    # FTS chunk text is the full body — must NOT leak into label text.
    store.replace_chunks("Knowledge/a.md", [(0, "Rust Macros\n\nnoisy body text @handle", np.ones(8, np.float32))])
    assert store.note_texts()["Knowledge/a.md"] == "Rust Macros Guide to declarative macros."
    store.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_store.py -k note_texts -v`
Expected: FAIL — current `note_texts` returns title + first-chunk text (the noisy body).

- [ ] **Step 3: Implement**

Replace `note_texts` body in `store.py`:
```python
    def note_texts(self) -> dict[str, str]:
        """Return ``{note_path: "title summary"}`` for keyword (c-TF-IDF) labeling.

        Uses the stored summary (not chunk/body text) so labels stay topical and
        free of body noise (handles, URLs, IDs).
        """
        rows = self._conn.execute("SELECT path, title, summary FROM notes").fetchall()
        texts: dict[str, str] = {}
        for path, title, summary in rows:
            parts = [part for part in (title, summary) if part]
            texts[path] = " ".join(parts)
        return texts
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_store.py -k note_texts -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/store.py tests/test_store.py
git commit -m "feat(kb-engine): note_texts labels from summary, not body"
```

### Task 1.4: `_index_note` — one summary vector + full-body FTS

**Files:**
- Modify: `src/kb_engine/sync.py` (`_index_note`)
- Test: `tests/test_sync.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync.py  (uses FakeEmbedder — deterministic, torch-free)
def test_index_note_embeds_summary_and_ftss_full_body(tmp_path, monkeypatch):
    import types, numpy as np
    from kb_engine.store import Store
    from kb_engine.embeddings import FakeEmbedder
    from kb_engine.models import Note
    from kb_engine.sync import _index_note
    from kb_engine.chunking import embedding_text

    store = Store(tmp_path / "kb.db"); store.init_schema()
    emb = FakeEmbedder(dim=64)
    note = Note(path="Knowledge/a.md", title="Rust Macros",
                body="A very long body. " * 200, tags=("Dev/Rust",), wikilinks=(),
                frontmatter=types.MappingProxyType({"summary": "Declarative macros guide."}),
                sha256="x")
    _index_note(store, note, emb, max_tokens=512)

    # exactly ONE vector per note (no mean-pool dilution), equal to embed(embedding_text)
    vecs = list(store.note_vectors())
    assert len(vecs) == 1
    expected = emb.embed_passages([embedding_text(note)])[0]
    assert np.allclose(vecs[0][1], expected)
    # keyword search still finds a body-only term
    assert store.keyword_search("body")  # body word is in FTS
    store.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_sync.py -k embeds_summary -v`
Expected: FAIL — current `_index_note` chunks title+body and embeds each chunk (multiple vectors, body-derived).

- [ ] **Step 3: Implement**

Replace `_index_note` in `sync.py`:
```python
from kb_engine.chunking import embedding_text, fts_text  # replace `chunk_note` import


def _index_note(store: Store, note: Note, embedder: Embedder, max_tokens: int) -> None:
    # Semantic vector = title + summary (one clean vector). FTS = full body.
    vector = embedder.embed_passages([embedding_text(note)])[0]
    summary = note.frontmatter.get("summary") if note.frontmatter else None
    store.upsert_note(
        path=note.path, title=note.title, summary=str(summary or "").strip(),
        sha256=note.sha256, tags=list(note.tags),
    )
    store.replace_chunks(note.path, [(0, fts_text(note), vector)])
```
`max_tokens` is now unused by `_index_note` (kept in signature for call-site compatibility; or drop it and update `sync`/`rebuild` call sites that pass `cfg.chunk_tokens`). Prefer dropping it: change the two calls in `sync()`/`rebuild` flow to `_index_note(store, note, embedder)` and remove the param.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_sync.py -v` → PASS. Then full suite: `uv run pytest -q` and fix any `upsert_note` positional callers in other tests (pass `summary=""`).

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/sync.py tests/test_sync.py
git commit -m "feat(kb-engine): index one summary vector + full-body FTS per note"
```

### Task 1.5: Rebuild + re-discover (operational verification)

**Files:** none (engine run against the real vault).

- [ ] **Step 1: Rebuild the cache** (embedding input changed → re-embed all)

```bash
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
kb-engine --vault "$VAULT" rebuild --json
```
Expected: `{"added": <~583>, "changed": 0, "deleted": 0}`.

- [ ] **Step 2: Re-discover and eyeball cluster quality**

```bash
kb-engine --vault "$VAULT" topics discover --json    # non-sticky: pure clustering signal
```
Expected: clusters form; labels should look cleaner than the body-diluted baseline. Record `n_new_topics` / `n_unfiled` for comparison. (No assertion — this is a human quality check before Phase 2.)

- [ ] **Step 3: Commit** — nothing to commit (no code). Note observations in the PR description.

---

## PHASE 2 — Primary + secondary assignment

### Task 2.1: `TopicMember.is_primary` + `topic_members.is_primary` column

**Files:**
- Modify: `src/kb_engine/models.py` (`TopicMember`)
- Modify: `src/kb_engine/store.py` (schema, migration, `save_topics`, `set_members`, `topic_members`)
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
def test_topic_member_is_primary_roundtrip(tmp_path):
    import numpy as np
    from kb_engine.store import Store
    from kb_engine.models import TopicMember
    store = Store(tmp_path / "kb.db"); store.init_schema()
    store.add_manual_topic("rust", "Rust", "rust lang", np.ones(8, np.float32))
    store.set_members("rust", [
        TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto", is_primary=True),
        TopicMember(note_path="Knowledge/b.md", score=0.6, source="auto", is_primary=False),
    ])
    members = {m.note_path: m for m in store.topic_members("rust")}
    assert members["Knowledge/a.md"].is_primary is True
    assert members["Knowledge/b.md"].is_primary is False
    store.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_store.py -k is_primary -v`
Expected: FAIL — `TopicMember.__init__() got an unexpected keyword argument 'is_primary'`.

- [ ] **Step 3: Implement**

`models.py`:
```python
@dataclass(frozen=True)
class TopicMember:
    note_path: str
    score: float  # cosine to centroid
    source: str  # "auto" | "seed" | "user"
    is_primary: bool = True  # primary (home) vs secondary (cross-link) membership
```

`store.py` schema — `topic_members`:
```sql
CREATE TABLE IF NOT EXISTS topic_members (
  topic_slug TEXT NOT NULL, note_path TEXT NOT NULL, score REAL, source TEXT,
  is_primary INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (topic_slug, note_path),
  FOREIGN KEY (topic_slug) REFERENCES topics(slug) ON DELETE CASCADE
);
```
Add to `init_schema`: `self._ensure_column("topic_members", "is_primary", "INTEGER NOT NULL DEFAULT 1")`.

`set_members` — write is_primary:
```python
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO topic_members(
                        topic_slug, note_path, score, source, is_primary
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (slug, member.note_path, member.score, member.source,
                     int(member.is_primary)),
                )
```
`save_topics` — same extra column + `int(member.is_primary)` in its INSERT.
`topic_members` — read it:
```python
    def topic_members(self, slug: str) -> list[TopicMember]:
        rows = self._conn.execute(
            """
            SELECT note_path, score, source, is_primary FROM topic_members
            WHERE topic_slug=? ORDER BY is_primary DESC, score DESC, note_path
            """,
            (slug,),
        ).fetchall()
        return [
            TopicMember(note_path=p, score=s, source=src, is_primary=bool(ip))
            for p, s, src, ip in rows
        ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_store.py -k is_primary -v` → PASS, then `uv run pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/models.py src/kb_engine/store.py tests/test_store.py
git commit -m "feat(kb-engine): TopicMember.is_primary + schema column"
```

### Task 2.2: `assign_notes` → primary + ≤2 secondaries

**Files:**
- Modify: `src/kb_engine/topics/assignment.py`
- Test: `tests/test_assignment.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assignment.py
import numpy as np
from kb_engine.models import Topic
from kb_engine.topics.assignment import assign_notes

def _topic(slug, vec):
    v = np.asarray(vec, np.float32)
    return Topic(slug=slug, label=slug, keywords=(), centroid=v / np.linalg.norm(v),
                 kind="manual", status="active")

def test_assign_returns_primary_plus_capped_secondaries():
    topics = [_topic("a", [1, 0, 0]), _topic("b", [0.95, 0.31, 0]),
              _topic("c", [0.9, 0.0, 0.44]), _topic("d", [0.88, 0.2, 0.43])]
    # note vector closest to a, also close to b/c/d
    vecs = {"Knowledge/n.md": np.asarray([1, 0.1, 0.1], np.float32)}
    assigned, borderline = assign_notes(vecs, topics, high=0.8, secondary=0.6, low=0.4)
    members = assigned["Knowledge/n.md"]
    primaries = [m for m in members if m.is_primary]
    secondaries = [m for m in members if not m.is_primary]
    assert len(primaries) == 1 and primaries[0].slug == "a"
    assert len(secondaries) <= 2  # capped
    assert all(m.score >= 0.6 for m in secondaries)

def test_assign_no_primary_when_below_high_is_borderline():
    topics = [_topic("a", [1, 0, 0])]
    vecs = {"Knowledge/n.md": np.asarray([0.5, 0.5, 0.7], np.float32)}  # cosine < high
    assigned, borderline = assign_notes(vecs, topics, high=0.9, secondary=0.6, low=0.4)
    assert "Knowledge/n.md" not in assigned
```

Note: the assigned value is now a `list[Assignment]` where `Assignment` carries `slug`, `score`, `is_primary`. Define a small frozen dataclass `Assignment` in `assignment.py`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_assignment.py -v`
Expected: FAIL — current `assign_notes` returns `dict[path, (slug, score)]`, no primary/secondary.

- [ ] **Step 3: Implement**

Rewrite `assignment.py`:
```python
from dataclasses import dataclass
from typing import Mapping

import numpy as np

from kb_engine.models import Topic
from kb_engine.topics._math import cosine

_MAX_SECONDARIES = 2


@dataclass(frozen=True)
class Assignment:
    slug: str
    score: float
    is_primary: bool


Assigned = dict[str, list[Assignment]]
Borderline = list[tuple[str, tuple[str, float]]]


def _ranked(vector: np.ndarray, topics: list[Topic]) -> list[tuple[str, float]]:
    """(slug, score) for every non-degenerate topic, best first (ties by slug)."""
    scored = [
        (topic.slug, cosine(vector, topic.centroid))
        for topic in topics
        if float(np.linalg.norm(topic.centroid)) != 0.0
    ]
    return sorted(scored, key=lambda sc: (-sc[1], sc[0]))


def assign_notes(
    note_vectors: Mapping[str, np.ndarray],
    topics: list[Topic],
    high: float,
    secondary: float,
    low: float,
) -> tuple[Assigned, Borderline]:
    """Assign each note a primary topic (nearest, score >= high) plus up to two
    secondary topics (other topics with score >= secondary).

    Notes whose nearest topic is in ``[low, high)`` are reported borderline;
    ``< low`` is unassigned. Deterministic (sorted paths; ranked ties by slug).
    """
    assigned: Assigned = {}
    borderline: Borderline = []
    for path in sorted(note_vectors):
        ranked = _ranked(note_vectors[path], topics)
        if not ranked:
            continue
        top_slug, top_score = ranked[0]
        if top_score < high:
            if top_score >= low:
                borderline.append((path, (top_slug, top_score)))
            continue
        members = [Assignment(top_slug, top_score, True)]
        for slug, score in ranked[1:]:
            if len(members) - 1 >= _MAX_SECONDARIES or score < secondary:
                break
            members.append(Assignment(slug, score, False))
        assigned[path] = members
    return assigned, borderline
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_assignment.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/topics/assignment.py tests/test_assignment.py
git commit -m "feat(kb-engine): primary + capped-secondary topic assignment"
```

### Task 2.3: CLI `assign` persists primary/secondary (+ `--secondary`)

**Files:**
- Modify: `src/kb_engine/cli.py` (`topics_assign`, `DEFAULT_ASSIGN_SECONDARY`)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py  (pattern: invoke via CliRunner with KB_FAKE_EMBED=1 / seeded store)
def test_assign_apply_persists_primary_and_secondary(tmp_path, monkeypatch):
    # Seed two active topics + a note vector near both; run `topics assign --apply`.
    # Assert topic_members has one is_primary=1 row and one is_primary=0 row for the note.
    ...  # mirror existing test_cli seeding helpers; assert via Store.topic_members
```
(Reuse the existing `test_cli.py` seeding helper that builds a store with `KB_FAKE_EMBED`. Assert the persisted `is_primary` split.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli.py -k assign -v` → FAIL (no `--secondary`; members lack is_primary split).

- [ ] **Step 3: Implement**

Add near the other defaults in `cli.py`:
```python
DEFAULT_ASSIGN_SECONDARY = 0.45  # re-tune empirically after Phase 1
```
Add option + thread it through `topics_assign`:
```python
@click.option("--secondary", default=DEFAULT_ASSIGN_SECONDARY, show_default=True, type=float,
              help="Min cosine for a SECONDARY (cross-link) topic.")
...
def topics_assign(cfg, high, low, secondary, apply_changes, as_json):
    ...
        assigned, borderline = assign_notes(note_vectors, assignable, high, secondary, low)
        if apply_changes:
            members_by_slug: dict[str, list[TopicMember]] = {}
            for note_path, members in assigned.items():
                for a in members:
                    members_by_slug.setdefault(a.slug, []).append(
                        TopicMember(note_path=note_path, score=a.score,
                                    source="auto", is_primary=a.is_primary)
                    )
            for slug, members in members_by_slug.items():
                store.set_members(slug, members)
```
Update the JSON rows to flatten the new `assigned` shape (one row per (note, topic) with an `is_primary` field).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli.py -k assign -v` → PASS, then `uv run pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/cli.py tests/test_cli.py
git commit -m "feat(kb-engine): topics assign --secondary persists primary/secondary"
```

### Task 2.4: `apply` writes `primary_topic` field + all tags

**Files:**
- Modify: `src/kb_engine/topics/apply.py`
- Test: `tests/test_apply.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_apply.py
def test_apply_writes_all_topic_tags_and_primary_topic_field(tmp_path):
    import numpy as np, frontmatter
    from kb_engine.store import Store
    from kb_engine.models import TopicMember
    vault = tmp_path; (vault / "Knowledge").mkdir()
    note = vault / "Knowledge" / "n.md"
    note.write_text("---\ntitle: N\ntags: [Dev/Rust]\n---\nbody\n")
    store = Store(vault / "kb.db"); store.init_schema()
    store.add_manual_topic("rust", "Rust", "rust", np.ones(8, np.float32))
    store.add_manual_topic("ai", "AI", "ai", np.ones(8, np.float32))
    store.set_members("rust", [TopicMember("Knowledge/n.md", 0.9, "auto", is_primary=True)])
    store.set_members("ai", [TopicMember("Knowledge/n.md", 0.6, "auto", is_primary=False)])
    from kb_engine.topics.apply import apply_topic_tags
    apply_topic_tags(store, vault, only_status=("active",))
    post = frontmatter.load(note)
    assert set(post["tags"]) >= {"Dev/Rust", "topic/rust", "topic/ai"}
    assert post["primary_topic"] == "rust"
    store.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_apply.py -k primary_topic -v` → FAIL (no `primary_topic` written).

- [ ] **Step 3: Implement**

In `apply.py`, add a primary-slug collector and write the field. Extend `_slugs_to_add_by_note` to also return primary per note, or add a sibling:
```python
def _primary_by_note(store: Store, only_status: tuple[str, ...]) -> dict[str, str]:
    """{note_path: primary_topic_slug} for active topics where the note is primary."""
    wanted = set(only_status)
    primary: dict[str, str] = {}
    for topic in store.load_topics():
        if topic.status not in wanted:
            continue
        for m in store.topic_members(topic.slug):
            if m.is_primary:
                primary[m.note_path] = topic.slug
    return primary
```
Update `_apply_to_note` to accept an optional `primary_slug` and set `post["primary_topic"] = primary_slug` (only when present; count the note as changed if the field is newly set even if all tags already exist). Thread `_primary_by_note(...)` through `apply_topic_tags` and pass per note.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_apply.py -v` → PASS, then `uv run pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/topics/apply.py tests/test_apply.py
git commit -m "feat(kb-engine): apply writes primary_topic field + all topic tags"
```

### Task 2.5: MOC render splits primary vs secondary

**Files:**
- Modify: `src/kb_engine/topics/render.py` (`_render_topic_moc`)
- Test: `tests/test_render.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_render.py
def test_topic_moc_splits_primary_and_secondary():
    import numpy as np
    from kb_engine.models import Topic, TopicMember
    from kb_engine.topics.render import _render_topic_moc
    topic = Topic(slug="rust", label="Rust", keywords=("rust",),
                  centroid=np.ones(8, np.float32), kind="manual", status="active")
    members = [
        TopicMember("Knowledge/p.md", 0.9, "auto", is_primary=True),
        TopicMember("Knowledge/s.md", 0.6, "auto", is_primary=False),
    ]
    out = _render_topic_moc(topic, members)
    assert "## Notes" in out and "## Also relevant" in out
    notes_block, also_block = out.split("## Also relevant", 1)
    assert "[[Knowledge/p.md]]" in notes_block and "[[Knowledge/p.md]]" not in also_block
    assert "[[Knowledge/s.md]]" in also_block
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_render.py -k splits_primary -v` → FAIL (single `## Notes` list).

- [ ] **Step 3: Implement**

Rewrite `_render_topic_moc` to partition by `is_primary`:
```python
def _render_topic_moc(topic: Topic, members: list[TopicMember]) -> str:
    keywords = ", ".join(topic.keywords)
    lines = [f"# {topic.label}", "",
             f"- slug: `{topic.slug}`",
             f"- kind/status: {topic.kind}/{topic.status}",
             f"- keywords: {keywords}", ""]

    def block(header: str, items: list[TopicMember]) -> None:
        lines.extend([header, ""])
        ordered = sorted(items, key=lambda m: (-m.score, m.note_path))
        if ordered:
            lines.extend(f"- [[{m.note_path}]] ({m.score:.2f})" for m in ordered)
        else:
            lines.append("_None._")
        lines.append("")

    block("## Notes", [m for m in members if m.is_primary])
    secondary = [m for m in members if not m.is_primary]
    if secondary:
        block("## Also relevant", secondary)

    body = "\n".join(lines).rstrip() + "\n"
    post = frontmatter.Post(body, type="system", generated=True)
    return frontmatter.dumps(post) + "\n"
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_render.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/topics/render.py tests/test_render.py
git commit -m "feat(kb-engine): MOC primary/secondary (Notes vs Also relevant)"
```

---

## PHASE 3 — Two-tier navigation + latent topics

### Task 3.1: `notes_without_topic()` + by-category index

**Files:**
- Modify: `src/kb_engine/store.py` (`notes_without_topic`)
- Modify: `src/kb_engine/topics/render.py` (`_render_unfiled_by_category`, wire into `render_topics`)
- Test: `tests/test_store.py`, `tests/test_render.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_store.py
def test_notes_without_topic_returns_tags(tmp_path):
    import numpy as np
    from kb_engine.store import Store
    from kb_engine.models import TopicMember
    store = Store(tmp_path / "kb.db"); store.init_schema()
    store.upsert_note("Knowledge/a.md", "A", "", "x", ["Dev/Rust", "Reference"])
    store.upsert_note("Knowledge/b.md", "B", "", "x", ["AI/Agents"])
    store.add_manual_topic("rust", "Rust", "rust", np.ones(8, np.float32))
    store.set_members("rust", [TopicMember("Knowledge/a.md", 0.9, "auto", True)])
    # a is in a topic; b is not
    assert store.notes_without_topic() == {"Knowledge/b.md": ["AI/Agents"]}
    store.close()
```
```python
# tests/test_render.py
def test_unfiled_by_category_groups_by_taxonomy_tag():
    from kb_engine.topics.render import _render_unfiled_by_category
    out = _render_unfiled_by_category({
        "Knowledge/b.md": ["AI/Agents"],
        "Knowledge/c.md": ["AI/Agents", "Dev/Tools"],
    })
    assert "## AI/Agents" in out
    assert "[[Knowledge/b.md]]" in out and "[[Knowledge/c.md]]" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_store.py tests/test_render.py -k "without_topic or unfiled_by_category" -v` → FAIL (functions absent).

- [ ] **Step 3: Implement**

`store.py`:
```python
    def notes_without_topic(self) -> dict[str, list[str]]:
        """{note_path: [taxonomy tags]} for notes that are in NO topic_members row.

        Topic tags (the 'topic/...' frontmatter) live in notes.tags too, but
        membership is the source of truth here; we return the note's non-topic tags.
        """
        in_topic = {
            p for (p,) in self._conn.execute("SELECT DISTINCT note_path FROM topic_members")
        }
        out: dict[str, list[str]] = {}
        for path, tags_json in self._conn.execute("SELECT path, tags FROM notes"):
            if path in in_topic:
                continue
            tags = [t for t in (json.loads(tags_json) if tags_json else [])
                    if not t.startswith("topic/")]
            out[path] = tags
        return out
```
`render.py` — new function + write in `render_topics`:
```python
def _render_unfiled_by_category(by_note: dict[str, list[str]]) -> str:
    """Group topicless notes under each taxonomy tag (a note may appear under several)."""
    by_tag: dict[str, list[str]] = {}
    for note_path, tags in by_note.items():
        for tag in (tags or ["(untagged)"]):
            by_tag.setdefault(tag, []).append(note_path)
    lines = ["# Unfiled by Category", "",
             "_Notes in no topic, grouped by taxonomy tag._", ""]
    for tag in sorted(by_tag):
        lines.append(f"## {tag}")
        for p in sorted(by_tag[tag]):
            lines.append(f"- [[{p}]]")
        lines.append("")
    body = "\n".join(lines).rstrip() + "\n"
    return frontmatter.dumps(frontmatter.Post(body, type="system", generated=True)) + "\n"
```
In `render_topics`, after writing topic MOCs:
```python
    (topics_dir / "_unfiled-by-category.md").write_text(
        _render_unfiled_by_category(store.notes_without_topic())
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_store.py tests/test_render.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/store.py src/kb_engine/topics/render.py tests/test_store.py tests/test_render.py
git commit -m "feat(kb-engine): by-category index for topicless notes (2-tier fallback)"
```

### Task 3.2: Latent-topic surfacing (`topics suggest`)

**Files:**
- Create: `src/kb_engine/topics/suggest.py`
- Modify: `src/kb_engine/cli.py` (add `topics suggest`)
- Test: `tests/test_suggest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_suggest.py  (FakeClusterer — torch-free)
def test_suggest_clusters_only_topicless_notes():
    import numpy as np
    from kb_engine.models import Topic, TopicMember
    from kb_engine.topics.clustering import FakeClusterer
    from kb_engine.topics.suggest import suggest_from_residual

    note_vectors = {"Knowledge/a.md": np.ones(8, np.float32),
                    "Knowledge/b.md": np.ones(8, np.float32),
                    "Knowledge/c.md": np.zeros(8, np.float32)}
    in_topic = {"Knowledge/a.md"}  # a already has a topic → excluded from residual
    # FakeClusterer returns labels for the residual (b, c) in sorted-path order
    result = suggest_from_residual(note_vectors, in_topic,
                                   clusterer=FakeClusterer(labels=[0, 0]),
                                   texts_by_path={"Knowledge/b.md": "rust macros",
                                                  "Knowledge/c.md": "rust async"})
    slugs = {t.slug for t in result.topics}
    member_paths = {m.note_path for ms in result.members_by_slug.values() for m in ms}
    assert "Knowledge/a.md" not in member_paths  # filed note excluded
    assert member_paths == {"Knowledge/b.md", "Knowledge/c.md"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_suggest.py -v` → FAIL (`suggest.py` absent).

- [ ] **Step 3: Implement**

`src/kb_engine/topics/suggest.py` — reuse `build_topics` from `discover.py`:
```python
import numpy as np

from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.discover import DiscoverResult, build_topics


def suggest_from_residual(
    note_vectors: dict[str, np.ndarray],
    in_topic: set[str],
    clusterer: Clusterer,
    texts_by_path: dict[str, str],
) -> DiscoverResult:
    """Cluster only notes NOT already in a topic, to surface latent mini-themes.

    Uses the supplied clusterer (caller passes one built with min_cluster_size=2)
    so coherent 2-note themes below the normal floor become proposals.
    """
    residual_paths = sorted(p for p in note_vectors if p not in in_topic)
    if not residual_paths:
        return DiscoverResult(topics=[], members_by_slug={}, n_unfiled=0)
    vectors = np.array([note_vectors[p] for p in residual_paths], dtype=np.float32)
    labels = clusterer.cluster(vectors)
    topics, members_by_slug, unfiled = build_topics(
        residual_paths, vectors, texts_by_path, labels
    )
    return DiscoverResult(topics=topics, members_by_slug=members_by_slug,
                          n_unfiled=len(unfiled))
```
(Confirm `DiscoverResult` shape/fields in `discover.py`; adapt the constructor call if it differs — it returns topics/members/unfiled.)

`cli.py` — `topics suggest` command: build `note_vectors` from `store.note_vectors()`; `in_topic` from a new `store` helper or `{m.note_path for t in load_topics() if t.status=='active' for m in topic_members(t.slug)}`; `texts_by_path = store.note_texts()`; `clusterer = _build_clusterer()` but with `min_cluster_size=2` (pass `UmapHdbscanClusterer(min_cluster_size=2)` directly, honoring `KB_FAKE_CLUSTER`); print proposed slugs + sizes. Persist via `store.save_topics(result.topics, result.members_by_slug)` only when a `--apply` flag is given (default dry-run, mirroring `assign`).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_suggest.py -v` → PASS, then `uv run pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/topics/suggest.py src/kb_engine/cli.py tests/test_suggest.py
git commit -m "feat(kb-engine): topics suggest — latent topics from the unfiled residual"
```

### Task 3.3: Operational re-tune + re-apply (real vault)

**Files:** none.

- [ ] **Step 1: Dry-run the assignment distribution to re-tune thresholds**

```bash
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
kb-engine --vault "$VAULT" topics assign --json   # dry-run; inspect score spread
```
Pick `--high`/`--secondary` from the score distribution (Phase 1 shifted the scale).

- [ ] **Step 2: Apply + render + suggest**

```bash
kb-engine --vault "$VAULT" topics assign --high <H> --secondary <S> --apply --json
kb-engine --vault "$VAULT" topics apply --status active --json
kb-engine --vault "$VAULT" topics render --json          # MOCs + by-category index
kb-engine --vault "$VAULT" topics suggest --json         # review latent themes
```

- [ ] **Step 3:** No code commit. Capture before/after unfiled counts in the PR.

---

## Notes for the implementer

- **TDD per task:** failing test → run (RED) → implement → run (GREEN) → commit. Run the **full** suite (`uv run pytest -q`) before each commit; Phase 1 changes ripple into `upsert_note` callers in other tests — update them to pass `summary=""`.
- **No vault writes in unit tests** — use `tmp_path` and `FakeEmbedder`/`FakeClusterer` (torch-free). Real-vault verification is the explicit operational tasks (1.5, 3.3).
- **Determinism:** keep sorted-path / sorted-slug ordering everywhere (existing tests rely on it).
- **Backward compat:** `TopicMember.is_primary` defaults `True`; `_ensure_column` migrations are idempotent so existing caches upgrade in place.
