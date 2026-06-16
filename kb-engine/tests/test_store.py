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


def test_keyword_search_punctuation_only_query_returns_empty(tmp_path):
    s = Store(tmp_path / "t.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.replace_chunks("Knowledge/a.md", [(0, "alpha beta", np.ones(4, np.float32))])
    # A query with no FTS terms (only punctuation/quotes) must not raise on the
    # MATCH grammar and must return no hits.
    assert s.keyword_search('"?!.* ', limit=5) == []
    assert s.keyword_search("   ", limit=5) == []
