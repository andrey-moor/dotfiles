import numpy as np

from kb_engine.dedup import DupPair, near_duplicates
from kb_engine.store import Store


def _store_with(tmp_path, pairs):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    for path, vec in pairs:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, np.asarray(vec, np.float32))])
    return store


def test_near_duplicates_finds_fixture_twins(tmp_path, real_vectors):
    twins = real_vectors.by_group("neardup:0")
    far = real_vectors.by_group("unfiled")[:1]
    store = _store_with(tmp_path, twins + far)
    pairs = near_duplicates(store, threshold=0.95)
    assert len(pairs) == 1
    assert pairs[0].cosine > 0.97
    assert {pairs[0].a, pairs[0].b} == {p for p, _ in twins}
    store.close()


def test_near_duplicates_sorted_and_threshold_respected(tmp_path, real_vectors):
    d0 = real_vectors.by_group("neardup:0")
    d1 = real_vectors.by_group("neardup:1")
    store = _store_with(tmp_path, d0 + d1)
    pairs = near_duplicates(store, threshold=0.95)
    same_pair = [p for p in pairs if p.cosine > 0.97]
    assert len(same_pair) >= 2  # both fixture twin-pairs found
    assert pairs == sorted(pairs, key=lambda p: (-p.cosine, p.a, p.b))
    store.close()


def test_near_duplicates_empty_store(tmp_path):
    store = _store_with(tmp_path, [])
    assert near_duplicates(store) == []
    store.close()
