import numpy as np
from kb_engine.store import Store, _sanitize_fts_query


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


def test_keyword_search_preserves_internal_hyphens(tmp_path):
    # A hyphenated term like "jina-v3" must match a chunk containing "jina-v3";
    # the tokenizer must not split it into "jina" + "v3".
    s = Store(tmp_path / "t.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="Models", sha256="h", tags=[])
    s.replace_chunks(
        "Knowledge/a.md",
        [(0, "we evaluated jina-v3 embeddings", np.ones(4, np.float32))],
    )
    hits = s.keyword_search("jina-v3", limit=5)
    assert hits and hits[0][0] == "Knowledge/a.md"


def test_sanitize_fts_query_keeps_hyphens_and_unicode():
    # Internal hyphens are preserved as one term; non-ASCII word chars survive.
    assert _sanitize_fts_query("jina-v3") == '"jina-v3"'
    assert _sanitize_fts_query("GPT-4") == '"GPT-4"'
    assert _sanitize_fts_query("café") == '"café"'
    # Leading/trailing punctuation is still stripped; multi-term still splits.
    assert _sanitize_fts_query("-leading-") == '"leading"'
    assert _sanitize_fts_query("co-op test") == '"co-op" "test"'
    # Empty / punctuation-only stays empty (unchanged).
    assert _sanitize_fts_query('"?!.* ') == ""
    assert _sanitize_fts_query("   ") == ""


def test_keyword_search_punctuation_only_query_returns_empty(tmp_path):
    s = Store(tmp_path / "t.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.replace_chunks("Knowledge/a.md", [(0, "alpha beta", np.ones(4, np.float32))])
    # A query with no FTS terms (only punctuation/quotes) must not raise on the
    # MATCH grammar and must return no hits.
    assert s.keyword_search('"?!.* ', limit=5) == []
    assert s.keyword_search("   ", limit=5) == []


def test_notes_by_tag_groups_paths_by_tag(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=["Dev/Rust", "Tools"])
    s.upsert_note(path="Knowledge/b.md", title="B", sha256="h", tags=["Dev/Rust"])
    s.upsert_note(path="Knowledge/c.md", title="C", sha256="h", tags=[])
    by_tag = s.notes_by_tag()
    assert by_tag["Dev/Rust"] == {"Knowledge/a.md", "Knowledge/b.md"}
    assert by_tag["Tools"] == {"Knowledge/a.md"}
    # untagged notes contribute no entries
    assert all("Knowledge/c.md" not in paths for paths in by_tag.values())


def test_notes_by_tag_empty_store(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    assert s.notes_by_tag() == {}


def test_upsert_note_stores_summary(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.upsert_note(path="Knowledge/a.md", title="A", summary="A short gist.",
                      sha256="x", tags=["AI/Agents"])
    assert store.note_summary("Knowledge/a.md") == "A short gist."
    store.close()


def test_upsert_note_updates_summary_on_conflict(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.upsert_note(path="Knowledge/a.md", title="A", sha256="x", tags=[], summary="old")
    store.upsert_note(path="Knowledge/a.md", title="A", sha256="x", tags=[], summary="new")
    assert store.note_summary("Knowledge/a.md") == "new"
    store.close()


def test_init_schema_adds_summary_to_legacy_notes_table(tmp_path):
    import sqlite3
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE notes (path TEXT PRIMARY KEY, title TEXT, sha256 TEXT NOT NULL, tags TEXT)")
    conn.commit(); conn.close()
    store = Store(db)
    store.init_schema()  # must not raise
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(notes)")}
    assert "summary" in cols
    store.close()
