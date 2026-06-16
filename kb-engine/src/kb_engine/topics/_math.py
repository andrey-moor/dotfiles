import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two vectors; 0.0 if either has zero norm."""
    denom = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def frozen_centroid(vector: np.ndarray) -> np.ndarray:
    """Return a read-only contiguous float32 copy of ``vector``.

    ``Topic`` is ``frozen=True`` but that doesn't protect ndarray contents;
    making the centroid non-writeable prevents callers from mutating shared
    state through ``topic.centroid``.
    """
    centroid = np.ascontiguousarray(vector, np.float32)
    centroid.flags.writeable = False
    return centroid
