import numpy as np

from kb_engine.embeddings import Embedder
from kb_engine.store import Store

DEFAULT_LIMIT = 20
RRF_K = 60
SCOPE_PREFIX = "Knowledge/"
SUPPRESS_THRESHOLD = 0.97

Ranked = list[tuple[str, float]]


def semantic_search(
    store: Store, embedder: Embedder, query: str, limit: int = DEFAULT_LIMIT
) -> Ranked:
    """Cosine ranking over unit vectors, collapsing to the best chunk per note."""
    q = embedder.embed_query(query)
    scored: dict[str, float] = {}
    for note_path, _ordinal, vec in store.iter_vectors():
        s = float(q @ vec)  # both unit-normalized → cosine similarity
        # -inf sentinel so a first chunk with cosine exactly -1.0 still registers.
        if s > scored.get(note_path, float("-inf")):
            scored[note_path] = s  # keep the best chunk per note
    return sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:limit]


def rrf_fuse(
    ranked_lists: list[Ranked], k: int = RRF_K, limit: int = DEFAULT_LIMIT
) -> Ranked:
    """Reciprocal Rank Fusion: reward items ranked highly across input lists."""
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, (path, _score) in enumerate(lst):
            scores[path] = scores.get(path, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:limit]


def _suppress_near_dups(
    store: Store, ranked: Ranked, threshold: float = SUPPRESS_THRESHOLD
) -> Ranked:
    """Drop results whose note vector is a >threshold cosine twin of a
    higher-ranked kept result (the best-ranked twin survives). Results without
    a stored vector are kept — fail open."""
    vectors = store.note_vectors_for([path for path, _ in ranked])
    kept: Ranked = []
    kept_units: list[np.ndarray] = []
    for path, score in ranked:
        vector = vectors.get(path)
        if vector is None:
            kept.append((path, score))
            continue
        norm = float(np.linalg.norm(vector))
        unit = vector / norm if norm else vector
        if any(float(unit @ ku) > threshold for ku in kept_units):
            continue
        kept.append((path, score))
        kept_units.append(unit)
    return kept


def hybrid_search(
    store: Store,
    embedder: Embedder,
    query: str,
    limit: int = DEFAULT_LIMIT,
    scope_prefix: str = SCOPE_PREFIX,
) -> Ranked:
    """Fuse semantic + keyword results, then scope to Knowledge/ (inbox included)."""
    sem = semantic_search(store, embedder, query, limit=limit * 2)
    kw = store.keyword_search(query, limit=limit * 2)  # [(path, bm25)]
    fused = rrf_fuse([sem, kw], limit=limit * 2)
    fused = [(p, s) for p, s in fused if p.startswith(scope_prefix)]
    fused = _suppress_near_dups(store, fused)
    return fused[:limit]
