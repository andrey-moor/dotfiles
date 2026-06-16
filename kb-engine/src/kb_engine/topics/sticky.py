from dataclasses import dataclass

import numpy as np

from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store
from kb_engine.topics.assignment import assign_notes
from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.discover import build_topics

DEFAULT_STICKY_HIGH = 0.55


@dataclass(frozen=True)
class StickyResult:
    n_assigned_existing: int
    n_new_topics: int
    n_unfiled: int


def _existing_sticky_topics(store: Store) -> list[Topic]:
    """Approved topics that hold their members fixed during re-discovery.

    For now: manual topics that are active (the practical stickiness anchor).
    A future semi-supervised re-fit could widen this (deferred, YAGNI).
    """
    return [
        topic
        for topic in store.load_topics()
        if topic.kind == "manual" and topic.status == "active"
    ]


def sticky_discover(
    store: Store, clusterer: Clusterer, high: float = DEFAULT_STICKY_HIGH
) -> StickyResult:
    """Assign notes to existing approved topics, then cluster only the residual.

    Notes scoring ``>= high`` against an existing manual/active topic are written
    as members of that topic (kept fixed). The remaining notes (the residual) are
    clustered into new ``discovered`` proposals via ``save_topics``, which leaves
    the existing manual topics untouched. An empty corpus yields an empty result.
    """
    note_vectors = dict(store.note_vectors())
    if not note_vectors:
        return StickyResult(n_assigned_existing=0, n_new_topics=0, n_unfiled=0)

    existing = _existing_sticky_topics(store)
    assigned, _borderline = assign_notes(note_vectors, existing, high=high, low=high)

    members_by_existing: dict[str, list[TopicMember]] = {}
    for note_path, (slug, score) in assigned.items():
        members_by_existing.setdefault(slug, []).append(
            TopicMember(note_path=note_path, score=score, source="auto")
        )
    for slug, members in members_by_existing.items():
        store.set_members(slug, members)

    residual_paths = sorted(set(note_vectors) - set(assigned))
    if not residual_paths:
        return StickyResult(
            n_assigned_existing=len(assigned), n_new_topics=0, n_unfiled=0
        )

    residual_matrix = np.vstack([note_vectors[path] for path in residual_paths])
    labels = clusterer.cluster(residual_matrix)

    texts_by_path = store.note_texts()
    topics, new_members_by_slug, unfiled = build_topics(
        residual_paths, residual_matrix, texts_by_path, labels
    )
    store.save_topics(topics, new_members_by_slug)

    return StickyResult(
        n_assigned_existing=len(assigned),
        n_new_topics=len(topics),
        n_unfiled=len(unfiled),
    )
