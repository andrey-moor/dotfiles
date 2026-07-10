"""Assign notes to manual topics by cosine similarity to their centroids.

Each note gets one primary topic — the highest-scoring topic whose high bar it
clears — plus up to two secondary cross-links; a note that clears nothing but
ranks inside a topic's ``[low, high)`` band lands in the borderline review queue
for a human decision. Per-topic thresholds (``Topic.threshold_high`` /
``threshold_secondary``) override the global fallbacks when set, degrading
exactly to the old global behavior when they are absent.
"""
from dataclasses import dataclass
from typing import Mapping

import numpy as np

from kb_engine.models import Topic
from kb_engine.topics._math import cosine

DEFAULT_ASSIGN_HIGH = 0.55
DEFAULT_ASSIGN_SECONDARY = 0.45  # min cosine for a secondary (cross-link) topic
DEFAULT_ASSIGN_LOW = 0.4  # borderline floor: [low, high) lands in the review queue

_MAX_SECONDARIES = 2
_MAX_BORDERLINE_CANDIDATES = 3


@dataclass(frozen=True)
class Assignment:
    slug: str
    score: float
    is_primary: bool


# {path: [Assignment, ...]} — first element is the primary, rest are secondaries.
Assigned = dict[str, list[Assignment]]
# (path, top candidates (slug, score) best-first) pairs for the review queue.
Borderline = list[tuple[str, tuple[tuple[str, float], ...]]]


def _ranked(vector: np.ndarray, topics: list[Topic]) -> list[tuple[Topic, float]]:
    """(topic, score) for every non-degenerate topic, best first (ties by slug)."""
    scored = [
        (topic, cosine(vector, topic.centroid))
        for topic in topics
        if float(np.linalg.norm(topic.centroid)) != 0.0
    ]
    return sorted(scored, key=lambda ts: (-ts[1], ts[0].slug))


def _high(topic: Topic, fallback: float) -> float:
    return topic.threshold_high if topic.threshold_high is not None else fallback


def _secondary(topic: Topic, fallback: float) -> float:
    return (
        topic.threshold_secondary
        if topic.threshold_secondary is not None
        else fallback
    )


def assign_notes(
    note_vectors: Mapping[str, np.ndarray],
    topics: list[Topic],
    high: float,
    secondary: float,
    low: float,
) -> tuple[Assigned, Borderline]:
    """Assign each note a primary topic plus up to two secondaries.

    Per-topic thresholds (``Topic.threshold_high`` / ``threshold_secondary``)
    override the global ``high`` / ``secondary`` / ``low`` fallbacks:

    - primary: the highest-scoring topic whose own high bar the note clears
    - secondaries: up to 2 other topics clearing their own secondary bar
    - borderline: nothing cleared, but the top-ranked topic's score is inside
      ``[low_t, high_t)`` (``low_t`` = the topic's derived secondary, else
      ``low``) — reported with its top candidates for the review queue
    - else unassigned

    With no per-topic thresholds set this reduces exactly to the old global
    behavior. Deterministic (sorted paths; ranked ties by slug).
    """
    if secondary > high:
        raise ValueError(f"secondary ({secondary}) must be <= high ({high})")
    assigned: Assigned = {}
    borderline: Borderline = []
    for path in sorted(note_vectors):
        ranked = _ranked(note_vectors[path], topics)
        if not ranked:
            continue
        clearing = [(t, s) for t, s in ranked if s >= _high(t, high)]
        if not clearing:
            top_topic, top_score = ranked[0]
            low_t = (
                top_topic.threshold_secondary
                if top_topic.threshold_secondary is not None
                else low
            )
            if low_t <= top_score < _high(top_topic, high):
                candidates = tuple(
                    (t.slug, s) for t, s in ranked[:_MAX_BORDERLINE_CANDIDATES]
                )
                borderline.append((path, candidates))
            continue
        primary_topic, primary_score = clearing[0]
        members = [Assignment(primary_topic.slug, primary_score, True)]
        for topic, score in ranked:
            if topic.slug == primary_topic.slug:
                continue
            if len(members) - 1 >= _MAX_SECONDARIES:
                break
            if score >= _secondary(topic, secondary):
                members.append(Assignment(topic.slug, score, False))
        assigned[path] = members
    return assigned, borderline
