"""The weekly topic pass: re-anchor → derive thresholds → assign → queue →
cluster the residual into proposals.

Replaces the retired sticky-single mode (topics/sticky.py). Assignment is the
real primary + up-to-2-secondaries semantics with per-topic thresholds; the
borderline band lands in the persisted review_queue for /kb:review.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.models import QueueEntry, TopicMember
from kb_engine.store import Store
from kb_engine.topics.assignment import (
    DEFAULT_ASSIGN_HIGH,
    DEFAULT_ASSIGN_LOW,
    DEFAULT_ASSIGN_SECONDARY,
    assign_notes,
)
from kb_engine.topics.anchoring import reanchor_topics
from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.discover import build_topics
from kb_engine.topics.thresholds import derive_thresholds, persist_thresholds


@dataclass(frozen=True)
class WeeklyTopicsResult:
    reanchored: int
    thresholds_set: int
    assigned: int
    queued: int
    new_topics: int
    unfiled: int


def weekly_topic_pass(
    store: Store,
    clusterer: Clusterer,
    high: float = DEFAULT_ASSIGN_HIGH,
    secondary: float = DEFAULT_ASSIGN_SECONDARY,
    low: float = DEFAULT_ASSIGN_LOW,
) -> WeeklyTopicsResult:
    """One unattended weekly maintenance pass over the topic layer.

    Human-pinned notes (a ``source='user'`` primary anywhere) are excluded
    from auto-assignment entirely. Every active topic's auto members are
    replaced wholesale each pass — one primary per note per pass, no
    cross-run staleness. The residual (unassigned, non-borderline) is
    clustered into fresh ``discovered`` proposals exactly as before.
    """
    note_vectors = dict(store.note_vectors())
    if not note_vectors:
        return WeeklyTopicsResult(0, 0, 0, 0, 0, 0)

    reanchor_result = reanchor_topics(store)
    stats = derive_thresholds(store)
    persist_thresholds(store, stats)

    pinned = store.user_primary_paths()
    assignable_vectors = {
        path: vec for path, vec in note_vectors.items() if path not in pinned
    }
    active = [t for t in store.load_topics() if t.status == "active"]
    assigned, borderline = assign_notes(
        assignable_vectors, active, high=high, secondary=secondary, low=low
    )

    members_by_slug: dict[str, list[TopicMember]] = {}
    for note_path, assignments in assigned.items():
        for a in assignments:
            members_by_slug.setdefault(a.slug, []).append(
                TopicMember(
                    note_path=note_path,
                    score=a.score,
                    source="auto",
                    is_primary=a.is_primary,
                )
            )
    for topic in active:
        store.replace_auto_members(topic.slug, members_by_slug.get(topic.slug, []))

    store.replace_review_queue(
        [QueueEntry(path, candidates, "borderline") for path, candidates in borderline]
    )

    queued_paths = {path for path, _ in borderline}
    residual_paths = sorted(
        set(assignable_vectors) - set(assigned) - queued_paths
    )
    n_new_topics = 0
    n_unfiled = len(residual_paths)
    if residual_paths:
        residual_matrix = np.vstack([note_vectors[p] for p in residual_paths])
        labels = clusterer.cluster(residual_matrix)
        texts_by_path = store.note_texts()
        topics, new_members, unfiled = build_topics(
            residual_paths, residual_matrix, texts_by_path, labels
        )
        store.save_topics(topics, new_members)
        n_new_topics = len(topics)
        n_unfiled = len(unfiled)

    return WeeklyTopicsResult(
        reanchored=len(reanchor_result.reanchored),
        thresholds_set=len(stats),
        assigned=len(assigned),
        queued=len(borderline),
        new_topics=n_new_topics,
        unfiled=n_unfiled,
    )
