import types
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Note:
    path: str  # vault-relative path, e.g. "Knowledge/foo.md"
    title: str
    body: str
    tags: tuple[str, ...]
    wikilinks: tuple[str, ...]
    frontmatter: types.MappingProxyType  # read-only view; Phase 2 will consume it
    sha256: str


@dataclass(frozen=True)
class Chunk:
    note_path: str
    ordinal: int
    text: str


@dataclass(frozen=True)
class SearchHit:
    note_path: str
    title: str
    score: float
    snippet: str


@dataclass(frozen=True)
class Topic:
    slug: str
    label: str
    keywords: tuple[str, ...]
    centroid: np.ndarray  # float32, unit-normalized
    kind: str  # "discovered" | "manual"
    status: str  # "proposed" | "active" | "deprecated"
    anchor_source: str = "label"  # "label" (text anchor) | "members" (centroid of members)
    threshold_high: float | None = None  # per-topic primary bar; None = use global
    threshold_secondary: float | None = None  # per-topic cross-link bar; None = global


@dataclass(frozen=True)
class TopicMember:
    note_path: str
    score: float  # cosine to centroid
    source: str  # "auto" | "seed" | "user"
    is_primary: bool = True  # primary (home) vs secondary (cross-link) membership


@dataclass(frozen=True)
class Area:
    slug: str
    label: str
    topic_slugs: tuple[str, ...]  # member topic slugs
