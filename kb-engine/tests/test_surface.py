import numpy as np

from kb_engine.embeddings import FakeEmbedder
from kb_engine.store import Store
from kb_engine.surface import related_to_note, related_to_query


def _store_with(tmp_path, docs):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    e = FakeEmbedder(dim=32)
    for path, txt in docs.items():
        s.upsert_note(path=path, title=path.split("/")[-1], sha256="h", tags=[])
        s.replace_chunks(path, [(0, txt, e.embed_passages([txt])[0])])
    return s, e


def test_related_to_query_returns_relevant(tmp_path):
    s, e = _store_with(
        tmp_path,
        {
            "Knowledge/mem.md": "long term memory for agents",
            "Knowledge/rust.md": "rust macros and traits",
        },
    )
    hits = related_to_query(s, e, "memory for agents", limit=3)
    assert hits and all(h.note_path.startswith("Knowledge/") for h in hits)
    assert hits[0].note_path == "Knowledge/mem.md"
    assert hits[0].title == "mem.md"  # resolved from the note's title


def test_related_to_note_excludes_self(tmp_path):
    # a is identical to itself, b is the nearest other note, c is unrelated.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.replace_chunks("Knowledge/a.md", [(0, "x", np.array([1, 0, 0, 0], np.float32))])
    s.upsert_note(path="Knowledge/b.md", title="B", sha256="h", tags=[])
    s.replace_chunks("Knowledge/b.md", [(0, "y", np.array([0.9, 0.1, 0, 0], np.float32))])
    s.upsert_note(path="Knowledge/c.md", title="C", sha256="h", tags=[])
    s.replace_chunks("Knowledge/c.md", [(0, "z", np.array([0, 0, 1, 0], np.float32))])
    hits = related_to_note(s, "Knowledge/a.md", limit=3)
    paths = [h.note_path for h in hits]
    assert "Knowledge/a.md" not in paths  # don't surface the note itself
    assert paths[0] == "Knowledge/b.md"  # nearest neighbor first
    assert hits[0].title == "B"
