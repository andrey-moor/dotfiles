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
