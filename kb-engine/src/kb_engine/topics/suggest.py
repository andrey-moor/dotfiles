"""Surface latent mini-themes by clustering only the topicless residual.

``suggest_from_residual`` re-clusters the notes NOT already in any topic — with a
lower ``min_cluster_size`` so coherent two-note themes below the normal floor can
surface — and returns them as a ``DiscoverResult`` of proposals. It does not
persist; the caller decides whether to save.
"""
import numpy as np

from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.discover import DiscoverResult, build_topics


def suggest_from_residual(
    note_vectors: dict[str, np.ndarray],
    in_topic: set[str],
    clusterer: Clusterer,
    texts_by_path: dict[str, str],
) -> DiscoverResult:
    """Cluster only notes NOT already in a topic, to surface latent mini-themes.

    The caller supplies a clusterer built with ``min_cluster_size=2`` so coherent
    two-note themes below the normal floor become proposals. Returns a
    ``DiscoverResult`` (does not persist — the caller decides whether to save).
    """
    residual_paths = sorted(p for p in note_vectors if p not in in_topic)
    if not residual_paths:
        return DiscoverResult(
            topics=(), members_by_slug={}, unfiled=(), n_topics=0, n_unfiled=0
        )
    vectors = np.vstack([note_vectors[p] for p in residual_paths])
    labels = clusterer.cluster(vectors)
    topics, members_by_slug, unfiled = build_topics(
        residual_paths, vectors, texts_by_path, labels
    )
    return DiscoverResult(
        topics=tuple(topics),
        members_by_slug=members_by_slug,
        unfiled=tuple(unfiled),
        n_topics=len(topics),
        n_unfiled=len(unfiled),
    )
