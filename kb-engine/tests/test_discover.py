import numpy as np

from kb_engine.store import Store
from kb_engine.topics.clustering import FakeClusterer
from kb_engine.topics.discover import build_topics, discover_topics


def _seed(store: Store, rows: list[tuple[str, str]]) -> None:
    for i, (path, text) in enumerate(rows):
        store.upsert_note(path=path, title=path, sha256="h", tags=[])
        vector = np.eye(4, dtype=np.float32)[i % 4]
        store.replace_chunks(path, [(0, text, vector)])


def test_build_topics_centroids_labels_and_noise():
    paths = ["Knowledge/a.md", "Knowledge/b.md", "Knowledge/c.md"]
    vecs = np.array([[1, 0], [0.9, 0.1], [0, 1]], np.float32)
    texts = {
        "Knowledge/a.md": "rust macros",
        "Knowledge/b.md": "rust borrow",
        "Knowledge/c.md": "llm prompt",
    }
    labels = np.array([0, 0, -1])  # c is noise
    topics, members, unfiled = build_topics(paths, vecs, texts, labels)
    assert len(topics) == 1  # one real cluster (label 0)
    t = topics[0]
    assert t.centroid.shape == (2,) and np.linalg.norm(t.centroid) > 0
    assert "rust" in t.keywords
    assert {m.note_path for m in members[t.slug]} == {"Knowledge/a.md", "Knowledge/b.md"}
    assert unfiled == ["Knowledge/c.md"]  # noise -> unfiled
    # member score = cosine of note vec to centroid
    assert all(0.0 <= m.score <= 1.0001 for m in members[t.slug])


def test_build_topics_suffixes_duplicate_slugs():
    # Two distinct clusters whose keyword labels slugify identically must get
    # disambiguated slugs (the second gets a "-2" suffix).
    paths = ["Knowledge/a.md", "Knowledge/b.md", "Knowledge/c.md", "Knowledge/d.md"]
    vecs = np.array([[1, 0], [0.9, 0.1], [0, 1], [0.1, 0.9]], np.float32)
    texts = {
        "Knowledge/a.md": "rust borrow",
        "Knowledge/b.md": "rust borrow",
        "Knowledge/c.md": "rust borrow",
        "Knowledge/d.md": "rust borrow",
    }
    labels = np.array([0, 0, 1, 1])  # two equal-size clusters, same keywords
    topics, _members, unfiled = build_topics(paths, vecs, texts, labels)
    slugs = [t.slug for t in topics]
    assert len(topics) == 2
    assert len(set(slugs)) == 2  # slugs disambiguated, not collided
    assert any(s.endswith("-2") for s in slugs)
    assert unfiled == []


def test_discover_topics_stores_and_reports(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    _seed(
        s,
        [
            ("Knowledge/a.md", "rust macros"),
            ("Knowledge/b.md", "rust borrow"),
            ("Knowledge/c.md", "llm prompt"),
        ],
    )
    result = discover_topics(s, FakeClusterer(labels=[0, 0, -1]))
    assert result.n_topics == 1 and result.n_unfiled == 1
    assert {t.slug for t in s.load_topics()} == {result.topics[0].slug}
    assert result.unfiled == ["Knowledge/c.md"]


def test_discover_topics_all_noise_yields_no_topics(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    _seed(
        s,
        [
            ("Knowledge/a.md", "rust macros"),
            ("Knowledge/b.md", "llm prompt"),
        ],
    )
    result = discover_topics(s, FakeClusterer(labels=[-1, -1]))
    assert result.n_topics == 0
    assert result.n_unfiled == 2
    assert s.load_topics() == []


def test_discover_topics_empty_corpus(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    result = discover_topics(s, FakeClusterer(labels=[]))
    assert result.n_topics == 0 and result.n_unfiled == 0
    assert result.topics == [] and result.unfiled == []
