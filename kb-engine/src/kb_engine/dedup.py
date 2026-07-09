"""Near-duplicate detection over note gist vectors.

A one-shot report for the human merge flow (/kb:review): pairs of notes whose
note-vector cosine exceeds a threshold. Merging is a decision — this module
never mutates anything.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.store import Store

DEFAULT_DEDUP_THRESHOLD = 0.95


@dataclass(frozen=True)
class DupPair:
    a: str
    b: str
    cosine: float


def near_duplicates(
    store: Store, threshold: float = DEFAULT_DEDUP_THRESHOLD
) -> list[DupPair]:
    """All note pairs with cosine >= ``threshold``, best first (ties by paths)."""
    items = list(store.note_vectors())
    if len(items) < 2:
        return []
    paths = [p for p, _ in items]
    matrix = np.vstack([v for _, v in items])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    unit = matrix / norms
    sim = unit @ unit.T
    upper_i, upper_j = np.triu_indices(len(paths), k=1)
    hits = np.nonzero(sim[upper_i, upper_j] >= threshold)[0]
    pairs = [
        DupPair(a=paths[upper_i[h]], b=paths[upper_j[h]],
                cosine=float(sim[upper_i[h], upper_j[h]]))
        for h in hits
    ]
    return sorted(pairs, key=lambda p: (-p.cosine, p.a, p.b))
