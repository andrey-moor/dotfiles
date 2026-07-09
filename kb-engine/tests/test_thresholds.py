import numpy as np
import pytest

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics.thresholds import (
    SECONDARY_OFFSET,
    THRESHOLD_FLOOR,
    derive_thresholds,
    persist_thresholds,
)


def _seed_topic(store, slug, members):
    store.add_manual_topic(slug, slug.upper(), "d", np.ones(1024, np.float32))
    rows = []
    for path, vec in members:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
        rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
    store.set_members(slug, rows)


def test_derive_matches_numpy_percentiles(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:4]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed_topic(store, "t1", members)
    centroid = store.load_topics()[0].centroid
    c_unit = centroid / np.linalg.norm(centroid)
    sims = np.array([
        float((v / np.linalg.norm(v)) @ c_unit) for _, v in members
    ])
    stats = derive_thresholds(store)
    assert len(stats) == 1
    s = stats[0]
    assert s.slug == "t1"
    assert s.n_members == 4
    assert s.p25 == pytest.approx(float(np.percentile(sims, 25)), abs=1e-6)
    assert s.high == pytest.approx(max(THRESHOLD_FLOOR, s.p25))
    assert s.secondary == pytest.approx(s.high - SECONDARY_OFFSET)
    store.close()


def test_floor_binds_for_loose_topics(tmp_path, real_vectors):
    """Members from DIFFERENT topics make a loose cluster — p25 vs the label
    anchor lands low, so the 0.45 floor must bind."""
    mixed = [real_vectors.by_group("topic:")[0], real_vectors.by_group("unfiled")[0],
             real_vectors.by_group("neardup:0")[0]]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed_topic(store, "loose", mixed)
    stats = derive_thresholds(store)
    assert stats[0].high >= THRESHOLD_FLOOR
    store.close()


def test_persist_writes_columns(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:3]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed_topic(store, "t1", members)
    stats = derive_thresholds(store)
    n = persist_thresholds(store, stats)
    assert n == 1
    loaded = store.load_topics()[0]
    assert loaded.threshold_high == pytest.approx(stats[0].high)
    assert loaded.threshold_secondary == pytest.approx(stats[0].secondary)
    store.close()


def test_topics_without_member_vectors_skipped(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.add_manual_topic("empty", "E", "d", np.ones(4, np.float32))
    assert derive_thresholds(store) == []
    store.close()
