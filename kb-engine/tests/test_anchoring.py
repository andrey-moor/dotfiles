import numpy as np

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics.anchoring import MIN_MEMBERS_FOR_REANCHOR, reanchor_topics


def _seed(store, slug, members, status="active"):
    store.add_manual_topic(slug, slug.upper(), "desc", np.ones(1024, np.float32))
    if status != "active":
        store._conn.execute("UPDATE topics SET status=? WHERE slug=?", (status, slug))
    rows = []
    for path, vec in members:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
        rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
    store.set_members(slug, rows)


def test_reanchor_uses_unit_mean_of_members(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:3]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed(store, "warm", members)
    result = reanchor_topics(store)
    assert result.reanchored == ("warm",)
    topic = store.load_topics()[0]
    mean = np.mean([v for _, v in members], axis=0)
    expected = mean / np.linalg.norm(mean)
    assert np.allclose(topic.centroid, expected, atol=1e-6)
    assert topic.anchor_source == "members"
    assert abs(float(np.linalg.norm(topic.centroid)) - 1.0) < 1e-5
    store.close()


def test_cold_start_keeps_label_anchor(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[: MIN_MEMBERS_FOR_REANCHOR - 1]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed(store, "cold", members)
    result = reanchor_topics(store)
    assert result.reanchored == ()
    assert result.kept_label == ("cold",)
    topic = store.load_topics()[0]
    assert topic.anchor_source == "label"
    assert np.allclose(topic.centroid, np.ones(1024, np.float32))
    store.close()


def test_reanchor_skips_non_manual_and_non_active(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:3]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed(store, "dormant", members, status="deprecated")
    result = reanchor_topics(store)
    assert result.reanchored == ()
    assert result.kept_label == ()
    store.close()


def test_reanchor_is_idempotent(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:3]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed(store, "warm", members)
    reanchor_topics(store)
    first = store.load_topics()[0].centroid.copy()
    reanchor_topics(store)
    assert np.allclose(store.load_topics()[0].centroid, first)
    store.close()
