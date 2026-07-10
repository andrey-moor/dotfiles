"""Shape a clustering of note vectors into proposed topics.

``build_topics`` maps cluster labels to ``Topic`` objects — each with a
unit-normalized centroid and a keyword-derived label/slug — alongside their
members, and collects the noise cluster (label ``-1``) as the unfiled residual.
Output is ordered by cluster size then slug for determinism. The clustering
itself lives in ``clustering.py``; this module only turns its result into the
topic model.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.models import Topic, TopicMember
from kb_engine.topics._math import cosine, frozen_centroid
from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.labeling import slugify, top_keywords
from kb_engine.store import Store

_KEYWORDS_PER_TOPIC = 5
_LABEL_KEYWORDS = 3
_NOISE_LABEL = -1


def _unit_normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector.astype(np.float32)
    return (vector / norm).astype(np.float32)


def build_topics(
    paths: list[str],
    vectors: np.ndarray,
    texts_by_path: dict[str, str],
    labels: np.ndarray,
) -> tuple[list[Topic], dict[str, list[TopicMember]], list[str]]:
    """Turn cluster labels into topics, members, and the unfiled residual.

    Returns ``(topics, members_by_slug, unfiled)`` where ``unfiled`` is the list
    of note paths that landed in the noise cluster (label ``-1``). Topics are
    ordered by cluster size (desc) then slug for deterministic output.
    """
    labels = np.asarray(labels, dtype=int)

    indices_by_label: dict[int, list[int]] = {}
    unfiled: list[str] = []
    for idx, label in enumerate(labels):
        label = int(label)
        if label == _NOISE_LABEL:
            unfiled.append(paths[idx])
            continue
        indices_by_label.setdefault(label, []).append(idx)

    docs_by_cluster = {
        label: [texts_by_path.get(paths[i], "") for i in members]
        for label, members in indices_by_label.items()
    }
    keywords_by_cluster = top_keywords(docs_by_cluster, n=_KEYWORDS_PER_TOPIC)

    # Order clusters deterministically: largest first, then by base slug.
    ordered_labels = sorted(
        indices_by_label,
        key=lambda label: (
            -len(indices_by_label[label]),
            slugify(" ".join(keywords_by_cluster[label])),
        ),
    )

    topics: list[Topic] = []
    members_by_slug: dict[str, list[TopicMember]] = {}
    used_slugs: set[str] = set()

    for label in ordered_labels:
        member_indices = indices_by_label[label]
        keywords = keywords_by_cluster[label]

        centroid = frozen_centroid(_unit_normalize(np.mean(vectors[member_indices], axis=0)))
        slug = _unique_slug(slugify(" ".join(keywords)), used_slugs)
        used_slugs.add(slug)
        topic_label = " ".join(keywords[:_LABEL_KEYWORDS]).title()

        topics.append(
            Topic(
                slug=slug,
                label=topic_label,
                keywords=keywords,
                centroid=centroid,
                kind="discovered",
                status="proposed",
            )
        )
        members_by_slug[slug] = [
            TopicMember(
                note_path=paths[i],
                score=cosine(vectors[i], centroid),
                source="auto",
            )
            for i in member_indices
        ]

    return topics, members_by_slug, unfiled


def _unique_slug(base: str, used: set[str]) -> str:
    """Disambiguate a slug against ``used`` with a numeric suffix."""
    base = base or "topic"
    if base not in used:
        return base
    suffix = 2
    while f"{base}-{suffix}" in used:
        suffix += 1
    return f"{base}-{suffix}"


@dataclass(frozen=True)
class DiscoverResult:
    topics: tuple[Topic, ...]
    members_by_slug: dict[str, list[TopicMember]]
    unfiled: tuple[str, ...]
    n_topics: int
    n_unfiled: int


def discover_topics(store: Store, clusterer: Clusterer) -> DiscoverResult:
    """Cluster the store's note vectors into topics and persist them.

    Reads mean-pooled note vectors (sorted by path), clusters them, builds
    topics with keyword labels, saves them to the store, and returns a summary.
    An empty corpus yields an empty result without invoking the clusterer.
    """
    note_vectors = list(store.note_vectors())
    if not note_vectors:
        return DiscoverResult(
            topics=(), members_by_slug={}, unfiled=(), n_topics=0, n_unfiled=0
        )

    paths = [path for path, _ in note_vectors]
    matrix = np.vstack([vector for _, vector in note_vectors])
    labels = clusterer.cluster(matrix)

    texts_by_path = store.note_texts()
    topics, members_by_slug, unfiled = build_topics(
        paths, matrix, texts_by_path, labels
    )
    store.save_topics(topics, members_by_slug)

    return DiscoverResult(
        topics=tuple(topics),
        members_by_slug=members_by_slug,
        unfiled=tuple(unfiled),
        n_topics=len(topics),
        n_unfiled=len(unfiled),
    )
