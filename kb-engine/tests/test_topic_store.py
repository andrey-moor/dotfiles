import numpy as np

from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store


def test_note_vectors_mean_pools_chunks(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.replace_chunks(
        "Knowledge/a.md",
        [
            (0, "x", np.array([1, 0, 0, 0], np.float32)),
            (1, "y", np.array([0, 1, 0, 0], np.float32)),
        ],
    )
    nv = dict((p, v) for p, v in s.note_vectors())
    assert nv["Knowledge/a.md"].shape == (4,)
    assert np.allclose(nv["Knowledge/a.md"], [0.5, 0.5, 0, 0])


def test_note_texts_joins_title_and_first_chunk(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="Rust", sha256="h", tags=[])
    s.replace_chunks(
        "Knowledge/a.md",
        [
            (0, "borrow checker", np.zeros(4, np.float32)),
            (1, "lifetimes", np.zeros(4, np.float32)),
        ],
    )
    # Note with no chunks contributes its title only.
    s.upsert_note(path="Knowledge/b.md", title="Empty", sha256="h", tags=[])
    texts = s.note_texts()
    assert texts["Knowledge/a.md"] == "Rust borrow checker"  # title + first chunk only
    assert texts["Knowledge/b.md"] == "Empty"


def test_save_and_load_topics(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    t = Topic(
        slug="ai-agents",
        label="AI Agents",
        keywords=("agent", "tool"),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics(
        [t],
        {"ai-agents": [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]},
    )
    loaded = s.load_topics()
    assert loaded[0].slug == "ai-agents" and loaded[0].centroid.shape == (4,)
    mem = s.topic_members("ai-agents")
    assert mem[0].note_path == "Knowledge/a.md" and abs(mem[0].score - 0.9) < 1e-6


def test_save_topics_replaces_previous_discovered(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    t1 = Topic(
        slug="old",
        label="Old",
        keywords=(),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics([t1], {"old": []})
    t2 = Topic(
        slug="new",
        label="New",
        keywords=(),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics([t2], {"new": []})  # discover re-run
    slugs = {t.slug for t in s.load_topics()}
    assert slugs == {"new"}  # stale discovered topics cleared
