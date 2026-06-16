from collections import Counter

import numpy as np

from kb_engine.models import Area, Topic
from kb_engine.topics.labeling import slugify

_AREA_LABEL_TOPICS = 3  # how many member topic labels to join into an area label


def _area_from_group(group: list[Topic], fallback_index: int) -> Area:
    """Build one Area from a list of member topics.

    Slug = slugify of the most common keyword across members (fallback
    ``area-{i}``); label = the first few member labels joined with " / ";
    topic_slugs = sorted member slugs.
    """
    keyword_counts: Counter[str] = Counter(
        keyword for topic in group for keyword in topic.keywords
    )
    slug = ""
    if keyword_counts:
        # most_common breaks ties by insertion order; sort for determinism.
        top_count = keyword_counts.most_common(1)[0][1]
        candidates = sorted(
            word for word, count in keyword_counts.items() if count == top_count
        )
        slug = slugify(candidates[0])
    if not slug:
        slug = f"area-{fallback_index}"

    label = " / ".join(topic.label for topic in group[:_AREA_LABEL_TOPICS])
    topic_slugs = tuple(sorted(topic.slug for topic in group))
    return Area(slug=slug, label=label, topic_slugs=topic_slugs)


def _dedupe_slug(base: str, used: set[str]) -> str:
    if base not in used:
        return base
    suffix = 2
    while f"{base}-{suffix}" in used:
        suffix += 1
    return f"{base}-{suffix}"


def build_areas(topics: list[Topic], distance_threshold: float) -> list[Area]:
    """Group topics into areas by agglomerative clustering on their centroids.

    Empty input yields ``[]``; a single topic becomes its own area. Otherwise
    centroids are stacked and clustered with cosine/average linkage cut at
    ``distance_threshold``. Groups are ordered largest-first (then by slug) for
    deterministic output; colliding slugs are disambiguated with a ``-N`` suffix.
    """
    if not topics:
        return []
    if len(topics) == 1:
        return [_area_from_group(list(topics), fallback_index=0)]

    from sklearn.cluster import AgglomerativeClustering

    centroids = np.vstack([topic.centroid for topic in topics]).astype(np.float32)
    labels = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=distance_threshold,
        metric="cosine",
        linkage="average",
    ).fit_predict(centroids)

    groups: dict[int, list[Topic]] = {}
    for topic, label in zip(topics, labels):
        groups.setdefault(int(label), []).append(topic)

    # Largest groups first, then by member slugs, for deterministic ordering.
    ordered_labels = sorted(
        groups,
        key=lambda label: (
            -len(groups[label]),
            sorted(topic.slug for topic in groups[label]),
        ),
    )

    areas: list[Area] = []
    used_slugs: set[str] = set()
    for index, label in enumerate(ordered_labels):
        area = _area_from_group(groups[label], fallback_index=index)
        slug = _dedupe_slug(area.slug, used_slugs)
        used_slugs.add(slug)
        areas.append(Area(slug=slug, label=area.label, topic_slugs=area.topic_slugs))
    return areas
