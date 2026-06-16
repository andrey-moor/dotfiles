from dataclasses import dataclass

from kb_engine.embeddings import Embedder
from kb_engine.search import DEFAULT_LIMIT, hybrid_search
from kb_engine.store import Store
from kb_engine.topics._math import cosine


@dataclass(frozen=True)
class SurfaceHit:
    note_path: str
    title: str
    score: float


def _resolve(store: Store, ranked: list[tuple[str, float]]) -> list[SurfaceHit]:
    return [
        SurfaceHit(
            note_path=path,
            title=store.note_title(path) or path,
            score=float(score),
        )
        for path, score in ranked
    ]


def related_to_query(
    store: Store, embedder: Embedder, query: str, limit: int = DEFAULT_LIMIT
) -> list[SurfaceHit]:
    """Surface the KB notes most relevant to a free-text query (hybrid search)."""
    ranked = hybrid_search(store, embedder, query, limit=limit)
    return _resolve(store, ranked)


def related_to_note(
    store: Store, note_path: str, limit: int = DEFAULT_LIMIT
) -> list[SurfaceHit]:
    """Surface notes nearest to ``note_path`` by mean-vector cosine, excluding itself.

    Returns an empty list if the note has no stored vector (never synced / no
    chunks).
    """
    vectors = dict(store.note_vectors())
    target = vectors.get(note_path)
    if target is None:
        return []
    ranked = sorted(
        (
            (path, cosine(target, vec))
            for path, vec in vectors.items()
            if path != note_path
        ),
        key=lambda kv: kv[1],
        reverse=True,
    )[:limit]
    return _resolve(store, ranked)
