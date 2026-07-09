import numpy as np


def test_fixture_shape_and_norms(real_vectors):
    n, dim = real_vectors.matrix.shape
    assert n >= 40
    assert dim == 1024
    assert real_vectors.matrix.dtype == np.float32
    norms = np.linalg.norm(real_vectors.matrix, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_fixture_groups_present(real_vectors):
    groups = {e["group"] for e in real_vectors.entries}
    assert sum(1 for g in groups if g.startswith("topic:")) >= 8
    assert {f"neardup:{i}" for i in range(5)} <= groups
    assert "unfiled" in groups


def test_neardup_pairs_are_actually_near(real_vectors):
    for i in range(5):
        pair = real_vectors.by_group(f"neardup:{i}")
        assert len(pair) == 2
        (_, a), (_, b) = pair
        assert float(a @ b) > 0.97


def test_topic_groups_are_geometrically_distinct(real_vectors):
    """Members sit closer to their own group's centroid than to a foreign one
    for at least most groups — the property threshold tests depend on."""
    groups: dict[str, list[np.ndarray]] = {}
    for e, row in zip(real_vectors.entries, real_vectors.matrix):
        if e["group"].startswith("topic:"):
            groups.setdefault(e["group"], []).append(row)
    cents = {g: np.mean(v, axis=0) / np.linalg.norm(np.mean(v, axis=0))
             for g, v in groups.items()}
    own_wins = 0
    total = 0
    for g, vecs in groups.items():
        for v in vecs:
            own = float(v @ cents[g])
            best_other = max(float(v @ c) for og, c in cents.items() if og != g)
            total += 1
            if own > best_other:
                own_wins += 1
    assert own_wins / total > 0.6
