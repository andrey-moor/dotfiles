import numpy as np

from kb_engine.embeddings import FakeEmbedder
from kb_engine.store import Store
from kb_engine.mcp.probe import status_payload, search_payload


def _seed(tmp_path):
    s = Store(tmp_path / "kb.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="Rust Macros", sha256="h", tags=[], summary="declarative macros")
    s.replace_chunks("Knowledge/a.md", [(0, "Rust Macros\n\ndeclarative macros", np.ones(64, np.float32))])
    return s


def test_status_payload_counts(tmp_path):
    s = _seed(tmp_path)
    assert status_payload(s) == {"notes": 1, "chunks": 1}
    s.close()


def test_search_payload_returns_hits(tmp_path):
    s = _seed(tmp_path)
    hits = search_payload(s, FakeEmbedder(dim=64), "macros", limit=5)
    assert hits and hits[0]["note_path"] == "Knowledge/a.md"
    assert set(hits[0]) == {"note_path", "title", "score"}
    s.close()
