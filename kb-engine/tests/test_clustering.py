import numpy as np
import pytest

from kb_engine.topics.clustering import FakeClusterer, UmapHdbscanClusterer


def test_fake_clusterer_returns_supplied_labels():
    c = FakeClusterer(labels=[0, 0, -1, 1])  # -1 = noise
    out = c.cluster(np.zeros((4, 8), np.float32))
    assert list(out) == [0, 0, -1, 1]


def test_umap_hdbscan_returns_all_noise_below_minimum():
    # Fewer than 3 notes is too small to cluster — everything is noise.
    # This path returns before importing umap/hdbscan, so no ML deps needed.
    c = UmapHdbscanClusterer()
    out = c.cluster(np.zeros((2, 8), np.float32))
    assert list(out) == [-1, -1]


def test_umap_hdbscan_empty_input_is_noise():
    c = UmapHdbscanClusterer()
    out = c.cluster(np.zeros((0, 8), np.float32))
    assert list(out) == []


def test_adaptive_min_cluster_size_honors_explicit_override():
    c = UmapHdbscanClusterer(min_cluster_size=7)
    assert c._adaptive(1000) == 7  # explicit value wins regardless of corpus size


@pytest.mark.parametrize(
    "n, expected",
    [(50, 2), (99, 2), (100, 3), (499, 3), (500, 5), (5000, 5)],
)
def test_adaptive_min_cluster_size_scales_with_corpus(n, expected):
    c = UmapHdbscanClusterer()  # no explicit override
    assert c._adaptive(n) == expected
