import numpy as np

from kb_engine.topics.clustering import FakeClusterer


def test_fake_clusterer_returns_supplied_labels():
    c = FakeClusterer(labels=[0, 0, -1, 1])  # -1 = noise
    out = c.cluster(np.zeros((4, 8), np.float32))
    assert list(out) == [0, 0, -1, 1]
