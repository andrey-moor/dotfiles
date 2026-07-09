"""Per-topic assignment thresholds derived from member-similarity distributions.

Formula (spec §6 Phase 4, validated on live data at plan time):
``high = max(0.45, p25(member sims vs current centroid))``,
``secondary = high - 0.08``. Derive AFTER re-anchoring so member-based topics
measure against their member-mean anchor.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.store import Store

THRESHOLD_FLOOR = 0.45
SECONDARY_OFFSET = 0.08


@dataclass(frozen=True)
class TopicThresholdStats:
    slug: str
    n_members: int
    p25: float
    p50: float
    p75: float
    high: float
    secondary: float


def derive_thresholds(
    store: Store, statuses: tuple[str, ...] = ("active",)
) -> list[TopicThresholdStats]:
    """Member-sim distribution stats + derived thresholds per topic (by slug).

    Topics with no member vectors (or a degenerate centroid) are skipped —
    they keep whatever thresholds they had (usually None → global fallback).
    """
    out: list[TopicThresholdStats] = []
    for topic in store.load_topics():
        if topic.status not in statuses:
            continue
        centroid_norm = float(np.linalg.norm(topic.centroid))
        if centroid_norm == 0.0:
            continue
        c_unit = topic.centroid / centroid_norm
        member_paths = [m.note_path for m in store.topic_members(topic.slug)]
        vectors = store.note_vectors_for(member_paths)
        if not vectors:
            continue
        sims = np.array([
            float((v / (np.linalg.norm(v) or 1.0)) @ c_unit)
            for v in vectors.values()
        ])
        p25, p50, p75 = (float(np.percentile(sims, q)) for q in (25, 50, 75))
        high = max(THRESHOLD_FLOOR, p25)
        out.append(
            TopicThresholdStats(
                slug=topic.slug,
                n_members=len(sims),
                p25=p25,
                p50=p50,
                p75=p75,
                high=high,
                secondary=high - SECONDARY_OFFSET,
            )
        )
    return out


def persist_thresholds(store: Store, stats: list[TopicThresholdStats]) -> int:
    """Write derived thresholds to the topics table; returns rows written."""
    for s in stats:
        store.set_topic_thresholds(s.slug, s.high, s.secondary)
    return len(stats)
