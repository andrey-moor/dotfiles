import sqlite3

import numpy as np
import pytest
from kb_engine.models import TopicMember
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


def test_note_texts_uses_title_and_summary_not_body(tmp_path):
    import numpy as np
    from kb_engine.store import Store
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.upsert_note("Knowledge/a.md", "Rust Macros", "x", ["Dev/Rust"],
                      summary="Guide to declarative macros.")
    # FTS chunk text is the full body — must NOT leak into label text.
    store.replace_chunks(
        "Knowledge/a.md",
        [(0, "Rust Macros\n\nnoisy body text @handle", np.ones(8, np.float32))],
    )
    assert store.note_texts()["Knowledge/a.md"] == "Rust Macros Guide to declarative macros."
    store.close()


def test_topic_member_is_primary_roundtrip(tmp_path):
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


def test_init_schema_adds_is_primary_to_legacy_topic_members(tmp_path):
    import sqlite3
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE topic_members (topic_slug TEXT NOT NULL, note_path TEXT NOT NULL, "
        "score REAL, source TEXT, PRIMARY KEY (topic_slug, note_path))"
    )
    conn.commit(); conn.close()
    store = Store(db)
    store.init_schema()  # must not raise
    cols = {r[1] for r in store._conn.execute("PRAGMA table_info(topic_members)")}
    assert "is_primary" in cols
    store.close()


def test_topic_members_orders_primaries_before_higher_scoring_secondaries(tmp_path):
    # The reader must return PRIMARY members first regardless of score, so a
    # high-scoring secondary still sorts below a lower-scoring primary.
    store = Store(tmp_path / "kb.db"); store.init_schema()
    store.add_manual_topic("rust", "Rust", "rust lang", np.ones(8, np.float32))
    store.set_members("rust", [
        TopicMember(note_path="Knowledge/secondary.md", score=0.99, source="auto", is_primary=False),
        TopicMember(note_path="Knowledge/primary.md", score=0.50, source="auto", is_primary=True),
    ])
    ordered = [m.note_path for m in store.topic_members("rust")]
    assert ordered == ["Knowledge/primary.md", "Knowledge/secondary.md"]
    store.close()


def test_notes_without_topic_returns_tags(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.upsert_note(path="Knowledge/a.md", title="A", sha256="x", tags=["Dev/Rust", "Reference"])
    store.upsert_note(path="Knowledge/b.md", title="B", sha256="x", tags=["AI/Agents"])
    store.add_manual_topic("rust", "Rust", "rust", np.ones(8, np.float32))
    store.set_members("rust", [TopicMember("Knowledge/a.md", 0.9, "auto", True)])
    # a is in a topic; b is not
    assert store.notes_without_topic() == {"Knowledge/b.md": ["AI/Agents"]}
    store.close()


def test_notes_without_topic_excludes_secondary_members(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.upsert_note(path="Knowledge/sec.md", title="S", sha256="x", tags=["Dev/Rust"])
    store.upsert_note(path="Knowledge/unfiled.md", title="U", sha256="x", tags=["AI"])
    store.add_manual_topic("rust", "Rust", "rust", np.ones(8, np.float32))
    store.set_members("rust", [TopicMember("Knowledge/sec.md", 0.6, "auto", is_primary=False)])
    result = store.notes_without_topic()
    assert "Knowledge/sec.md" not in result  # secondary membership still counts as filed
    assert "Knowledge/unfiled.md" in result
    store.close()


def test_note_vectors_for_returns_only_requested(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.upsert_note("a.md", "A", "sha-a", [])
    store.upsert_note("b.md", "B", "sha-b", [])
    va = np.array([1.0, 0.0, 0.0], np.float32)
    vb = np.array([0.0, 1.0, 0.0], np.float32)
    store.replace_chunks("a.md", [(0, "a text", va)])
    store.replace_chunks("b.md", [(0, "b text", vb)])
    got = store.note_vectors_for(["a.md", "missing.md"])
    assert set(got) == {"a.md"}
    assert np.allclose(got["a.md"], va)
    store.close()


def test_topic_anchor_source_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    c = np.array([1.0, 0.0], np.float32)
    store.add_manual_topic("t1", "T1", "desc", c)
    loaded = store.load_topics()[0]
    assert loaded.anchor_source == "label"
    new = np.array([0.0, 1.0], np.float32)
    store.update_topic_anchor("t1", new, "members")
    loaded = store.load_topics()[0]
    assert loaded.anchor_source == "members"
    assert np.allclose(loaded.centroid, new)
    store.close()


def test_existing_db_gains_anchor_source_column(tmp_path):
    """init_schema on a pre-Phase-4 DB backfills the column with 'label'."""
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE topics (slug TEXT PRIMARY KEY, label TEXT, keywords TEXT,"
        " centroid BLOB NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL);"
    )
    conn.execute(
        "INSERT INTO topics VALUES ('old', 'Old', '[]', ?, 'manual', 'active')",
        (np.ones(2, np.float32).tobytes(),),
    )
    conn.commit()
    conn.close()
    store = Store(db)
    store.init_schema()
    assert store.load_topics()[0].anchor_source == "label"
    store.close()


def test_topic_thresholds_roundtrip_and_default_none(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(2, np.float32))
    assert store.load_topics()[0].threshold_high is None
    assert store.load_topics()[0].threshold_secondary is None
    store.set_topic_thresholds("t1", 0.61, 0.53)
    loaded = store.load_topics()[0]
    assert loaded.threshold_high == pytest.approx(0.61)
    assert loaded.threshold_secondary == pytest.approx(0.53)
    store.close()
