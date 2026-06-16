from kb_engine.embeddings import Embedder
from kb_engine.store import Store

DEFAULT_LIMIT = 20
RRF_K = 60
SCOPE_PREFIX = "Knowledge/"
INBOX_PREFIX = SCOPE_PREFIX + "inbox/"

Ranked = list[tuple[str, float]]


def semantic_search(
    store: Store, embedder: Embedder, query: str, limit: int = DEFAULT_LIMIT
) -> Ranked:
    """Cosine ranking over unit vectors, collapsing to the best chunk per note."""
    q = embedder.embed_query(query)
    scored: dict[str, float] = {}
    for note_path, _ordinal, vec in store.iter_vectors():
        s = float(q @ vec)  # both unit-normalized → cosine similarity
        if s > scored.get(note_path, -1.0):
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


def hybrid_search(
    store: Store,
    embedder: Embedder,
    query: str,
    limit: int = DEFAULT_LIMIT,
    scope_prefix: str = SCOPE_PREFIX,
) -> Ranked:
    """Fuse semantic + keyword results, then scope to Knowledge/ (no inbox)."""
    sem = semantic_search(store, embedder, query, limit=limit * 2)
    kw = store.keyword_search(query, limit=limit * 2)  # [(path, bm25)]
    fused = rrf_fuse([sem, kw], limit=limit * 2)
    inbox_prefix = scope_prefix + "inbox/"
    fused = [
        (p, s)
        for p, s in fused
        if p.startswith(scope_prefix) and not p.startswith(inbox_prefix)
    ]
    return fused[:limit]
