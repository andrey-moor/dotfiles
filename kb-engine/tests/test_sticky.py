import numpy as np

from kb_engine.store import Store
from kb_engine.topics.clustering import FakeClusterer
from kb_engine.topics.sticky import StickyResult, sticky_discover


def _seed_note(store: Store, path: str, vector: list[float]) -> None:
    store.upsert_note(path=path, title=path, sha256="h", tags=[])
    store.replace_chunks(path, [(0, path, np.array(vector, np.float32))])


def _seed_existing(store: Store) -> None:
    # an approved manual topic anchored near [1,0,0]
    store.add_manual_topic("rust", "Rust", "rust", np.array([1, 0, 0], np.float32))


def test_sticky_keeps_existing_and_proposes_from_residual(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    _seed_existing(s)
    # 3 notes: 2 near rust (assigned to existing), 1 elsewhere (residual -> new cluster)
    vecs = {
        "Knowledge/a.md": [0.99, 0.01, 0],
        "Knowledge/b.md": [0.98, 0, 0.02],
        "Knowledge/c.md": [0, 0, 1],
    }
    for path, vector in vecs.items():
        _seed_note(s, path, vector)
    # clusterer only ever sees the residual (1 note) -> return single cluster label
    res = sticky_discover(s, FakeClusterer(labels=[0]), high=0.9)
    assert isinstance(res, StickyResult)
    # existing manual topic preserved
    assert "rust" in {t.slug for t in s.load_topics()}
    # a, b assigned to the existing rust topic
    assert res.n_assigned_existing == 2
    rust_members = {m.note_path for m in s.topic_members("rust")}
    assert rust_members == {"Knowledge/a.md", "Knowledge/b.md"}
    # c formed a new discovered proposal from the residual
    assert res.n_new_topics == 1
    discovered = [t for t in s.load_topics() if t.kind == "discovered"]
    assert len(discovered) == 1
    new_members = {m.note_path for m in s.topic_members(discovered[0].slug)}
    assert new_members == {"Knowledge/c.md"}


def test_sticky_clusterer_only_sees_residual(tmp_path):
    # The clusterer must be invoked with ONLY the residual matrix (the notes not
    # assigned to an existing topic), not the whole corpus.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    _seed_existing(s)
    _seed_note(s, "Knowledge/a.md", [1.0, 0, 0])  # -> rust
    _seed_note(s, "Knowledge/b.md", [0, 1.0, 0])  # residual
    _seed_note(s, "Knowledge/c.md", [0, 0, 1.0])  # residual

    seen: dict[str, int] = {}

    class SpyClusterer:
        def cluster(self, vectors):
            seen["rows"] = len(vectors)
            return np.array([0, 0], dtype=int)

    sticky_discover(s, SpyClusterer(), high=0.9)
    assert seen["rows"] == 2  # only b, c reached the clusterer


def test_sticky_preserves_existing_when_all_notes_assigned(tmp_path):
    # When every note is absorbed by an existing topic the residual is empty;
    # the clusterer is never called and no discovered topics are produced.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    _seed_existing(s)
    _seed_note(s, "Knowledge/a.md", [1.0, 0, 0])
    _seed_note(s, "Knowledge/b.md", [0.99, 0.01, 0])

    class ExplodingClusterer:
        def cluster(self, vectors):
            raise AssertionError("clusterer should not run on an empty residual")

    res = sticky_discover(s, ExplodingClusterer(), high=0.9)
    assert res.n_assigned_existing == 2
    assert res.n_new_topics == 0
    assert res.n_unfiled == 0
    assert {t.slug for t in s.load_topics()} == {"rust"}


def test_sticky_residual_noise_is_unfiled(tmp_path):
    # Residual notes the clusterer marks as noise (-1) are reported as unfiled,
    # not turned into topics.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    _seed_existing(s)
    _seed_note(s, "Knowledge/a.md", [1.0, 0, 0])  # -> rust
    _seed_note(s, "Knowledge/b.md", [0, 1.0, 0])  # residual, noise

    res = sticky_discover(s, FakeClusterer(labels=[-1]), high=0.9)
    assert res.n_assigned_existing == 1
    assert res.n_new_topics == 0
    assert res.n_unfiled == 1
