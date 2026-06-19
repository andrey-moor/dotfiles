from dataclasses import dataclass
from typing import Mapping

import numpy as np

from kb_engine.models import Topic
from kb_engine.topics._math import cosine

_MAX_SECONDARIES = 2


@dataclass(frozen=True)
class Assignment:
    slug: str
    score: float
    is_primary: bool


# {path: [Assignment, ...]} — first element is the primary, rest are secondaries.
Assigned = dict[str, list[Assignment]]
# (path, (topic_slug, score)) pairs reported for human review.
Borderline = list[tuple[str, tuple[str, float]]]


def _ranked(vector: np.ndarray, topics: list[Topic]) -> list[tuple[str, float]]:
    """(slug, score) for every non-degenerate topic, best first (ties by slug)."""
    scored = [
        (topic.slug, cosine(vector, topic.centroid))
        for topic in topics
        if float(np.linalg.norm(topic.centroid)) != 0.0
    ]
    return sorted(scored, key=lambda sc: (-sc[1], sc[0]))


def assign_notes(
    note_vectors: Mapping[str, np.ndarray],
    topics: list[Topic],
    high: float,
    secondary: float,
    low: float,
) -> tuple[Assigned, Borderline]:
    """Assign each note a primary topic (nearest, score >= high) plus up to two
    secondary topics (other topics with score >= secondary).

    Notes whose nearest topic is in ``[low, high)`` are reported borderline;
    ``< low`` is unassigned. Deterministic (sorted paths; ranked ties by slug).
    """
    if secondary > high:
        raise ValueError(f"secondary ({secondary}) must be <= high ({high})")
    assigned: Assigned = {}
    borderline: Borderline = []
    for path in sorted(note_vectors):
        ranked = _ranked(note_vectors[path], topics)
        if not ranked:
            continue
        top_slug, top_score = ranked[0]
        if top_score < high:
            if top_score >= low:
                borderline.append((path, (top_slug, top_score)))
            continue
        members = [Assignment(top_slug, top_score, True)]
        for slug, score in ranked[1:]:
            if len(members) - 1 >= _MAX_SECONDARIES or score < secondary:
                break
            members.append(Assignment(slug, score, False))
        assigned[path] = members
    return assigned, borderline
