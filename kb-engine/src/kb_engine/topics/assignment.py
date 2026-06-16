from typing import Mapping

import numpy as np

from kb_engine.models import Topic

# (path, (topic_slug, score)) pairs reported for human review.
Borderline = list[tuple[str, tuple[str, float]]]
# {path: (topic_slug, score)} for high-confidence auto-members.
Assigned = dict[str, tuple[str, float]]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a)) * float(np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _best_topic(vector: np.ndarray, topics: list[Topic]) -> tuple[str, float] | None:
    """Return the (slug, score) of the topic with the highest cosine, or None.

    Topics with a zero-norm centroid are skipped. Ties are broken by slug so the
    result is deterministic regardless of topic ordering.
    """
    best: tuple[str, float] | None = None
    for topic in topics:
        if float(np.linalg.norm(topic.centroid)) == 0.0:
            continue
        score = _cosine(vector, topic.centroid)
        if best is None or (score, topic.slug) > (best[1], best[0]):
            best = (topic.slug, score)
    return best


def assign_notes(
    note_vectors: Mapping[str, np.ndarray],
    topics: list[Topic],
    high: float,
    low: float,
) -> tuple[Assigned, Borderline]:
    """Assign each note to its nearest topic centroid by cosine similarity.

    ``score >= high`` → auto-member (``assigned``); ``low <= score < high`` →
    reported for review (``borderline``); ``score < low`` → unassigned. Notes
    are processed in sorted-path order for deterministic output.
    """
    assigned: Assigned = {}
    borderline: Borderline = []
    for path in sorted(note_vectors):
        best = _best_topic(note_vectors[path], topics)
        if best is None:
            continue
        slug, score = best
        if score >= high:
            assigned[path] = (slug, score)
        elif score >= low:
            borderline.append((path, (slug, score)))
    return assigned, borderline
