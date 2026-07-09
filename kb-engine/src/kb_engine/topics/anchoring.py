"""Member-centroid re-anchoring for manual topics.

A manual topic starts life anchored by an embedding of its label+description
(cold start). Once it has enough confirmed members, the members themselves are
the better definition of the topic — the anchor becomes the unit-normalized
mean of member vectors, and ``anchor_source`` records the provenance.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.store import Store

MIN_MEMBERS_FOR_REANCHOR = 3


@dataclass(frozen=True)
class ReanchorResult:
    reanchored: tuple[str, ...]  # slugs whose anchor was recomputed from members
    kept_label: tuple[str, ...]  # manual/active slugs still on their label anchor


def reanchor_topics(store: Store) -> ReanchorResult:
    """Recompute anchors for manual/active topics with enough member vectors.

    Idempotent: the mean of an unchanged member set is unchanged. Members
    without a stored vector (e.g. evicted, never synced) don't count toward
    the minimum.
    """
    reanchored: list[str] = []
    kept: list[str] = []
    for topic in store.load_topics():
        if topic.kind != "manual" or topic.status != "active":
            continue
        member_paths = [m.note_path for m in store.topic_members(topic.slug)]
        vectors = store.note_vectors_for(member_paths)
        if len(vectors) < MIN_MEMBERS_FOR_REANCHOR:
            kept.append(topic.slug)
            continue
        mean = np.mean(list(vectors.values()), axis=0)
        norm = float(np.linalg.norm(mean))
        if norm == 0.0:
            kept.append(topic.slug)
            continue
        store.update_topic_anchor(
            topic.slug, (mean / norm).astype(np.float32), "members"
        )
        reanchored.append(topic.slug)
    return ReanchorResult(reanchored=tuple(reanchored), kept_label=tuple(kept))
