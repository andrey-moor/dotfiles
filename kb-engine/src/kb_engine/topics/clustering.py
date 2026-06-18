from typing import Protocol

import numpy as np


class Clusterer(Protocol):
    def cluster(self, vectors: np.ndarray) -> np.ndarray:
        """Return an int label per row; -1 = noise/unclustered."""


class FakeClusterer:
    """Deterministic clusterer that returns caller-supplied labels.

    Used in unit tests so topic building/storage can be exercised without
    UMAP/HDBSCAN.
    """

    def __init__(self, labels: list[int]) -> None:
        self._labels = labels

    def cluster(self, vectors: np.ndarray) -> np.ndarray:
        return np.asarray(self._labels, dtype=int)


# Minimum notes needed before clustering is meaningful; below this everything
# is treated as noise (no topics).
_MIN_NOTES = 3
# Adaptive min_cluster_size thresholds (proven pins, mirrors orrery-engine).
_SMALL_CORPUS = 100
_MEDIUM_CORPUS = 500
_MIN_CLUSTER_SMALL = 2
_MIN_CLUSTER_MEDIUM = 3
_MIN_CLUSTER_LARGE = 5
_MAX_UMAP_COMPONENTS = 5
_MAX_UMAP_NEIGHBORS = 15
_RANDOM_STATE = 42
# HDBSCAN cluster-selection: "leaf" yields finer, homogeneous topics; "eom"
# (excess of mass) yields fewer, broader clusters that can over-merge.
_CLUSTER_SELECTION_METHODS = frozenset({"eom", "leaf"})


class UmapHdbscanClusterer:
    """Real clusterer: UMAP dimensionality reduction → HDBSCAN density clustering.

    Mirrors orrery-engine's proven pipeline. UMAP/HDBSCAN are imported lazily
    inside ``cluster`` so the ``[topics]`` extra is only required when actually
    discovering topics (unit tests use ``FakeClusterer``).
    """

    def __init__(
        self,
        min_cluster_size: int | None = None,
        random_state: int = _RANDOM_STATE,
        cluster_selection_method: str = "leaf",
    ) -> None:
        # HDBSCAN requires min_cluster_size >= 2; validate at construction so a
        # bad value fails fast rather than deep inside fit_predict. None means
        # "use the adaptive ladder".
        if min_cluster_size is not None and min_cluster_size < 2:
            raise ValueError(
                f"min_cluster_size must be >= 2 (got {min_cluster_size})"
            )
        if cluster_selection_method not in _CLUSTER_SELECTION_METHODS:
            raise ValueError(
                "cluster_selection_method must be one of "
                f"{sorted(_CLUSTER_SELECTION_METHODS)} (got {cluster_selection_method!r})"
            )
        self.min_cluster_size = min_cluster_size
        self.random_state = random_state
        self.cluster_selection_method = cluster_selection_method

    def _adaptive(self, n: int) -> int:
        if self.min_cluster_size is not None:
            return self.min_cluster_size
        if n < _SMALL_CORPUS:
            return _MIN_CLUSTER_SMALL
        if n < _MEDIUM_CORPUS:
            return _MIN_CLUSTER_MEDIUM
        return _MIN_CLUSTER_LARGE

    def cluster(self, vectors: np.ndarray) -> np.ndarray:
        n = len(vectors)
        if n < _MIN_NOTES:
            return np.full(n, -1, dtype=int)

        import hdbscan
        import umap

        n_components = min(_MAX_UMAP_COMPONENTS, n - 1)
        n_neighbors = min(_MAX_UMAP_NEIGHBORS, max(2, n - 1))
        reduced = umap.UMAP(
            n_neighbors=n_neighbors,
            n_components=n_components,
            min_dist=0.0,
            metric="cosine",
            random_state=self.random_state,
        ).fit_transform(vectors)
        labels = hdbscan.HDBSCAN(
            min_cluster_size=self._adaptive(n),
            metric="euclidean",
            cluster_selection_method=self.cluster_selection_method,
        ).fit_predict(reduced)
        return labels.astype(int)
