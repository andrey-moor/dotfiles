import os

import numpy as np
import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("KB_RUN_INTEGRATION") != "1", reason="set KB_RUN_INTEGRATION=1"
)
def test_umap_hdbscan_recovers_separated_groups():
    from kb_engine.topics.clustering import UmapHdbscanClusterer

    rng = np.random.default_rng(0)
    groups = [rng.normal(c, 0.02, (12, 16)).astype(np.float32) for c in (-5, 0, 5)]
    vecs = np.vstack(groups)
    labels = UmapHdbscanClusterer(min_cluster_size=5).cluster(vecs)
    n_clusters = len({label for label in labels if label != -1})
    assert n_clusters >= 2  # recovers the separation
