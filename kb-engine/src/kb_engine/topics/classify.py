"""Area classifier — flag-gated LLM path with an embedding-similarity fallback.

Two ways to assign a note to one of the seeded areas:

- **LLM path** (when an ``LLM`` is supplied): a strict-JSON prompt over the nine
  area slugs. Any malformed / refusal / unknown-slug reply falls through to the
  embedding path — bad model output never crashes classification.
- **Embedding path** (also the no-LLM path): best cosine of the note vector
  against the per-area centroids.

Both unavailable → ``None``. This module is pure: it reads, it never writes to
notes or the store (that wiring lives downstream).
"""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from kb_engine.config import Config
from kb_engine.llm import LLM
from kb_engine.models import Area
from kb_engine.store import Store
from kb_engine.topics._math import cosine
from kb_engine.topics.areas_registry import SEEDED_AREAS
from kb_engine.vault import load_post, write_post_atomic

AUTO_AREA_MIN_LLM_CONF = 0.8
AUTO_AREA_MIN_EMBED_COS = 0.55

_SYSTEM_PREFIX = (
    "You assign one AREA to a note. Reply with ONLY a JSON object "
    '{"area": "<slug>", "confidence": 0.0-1.0}. Valid slugs: '
)


@dataclass(frozen=True)
class AreaCandidate:
    slug: str
    confidence: float
    source: str  # "llm" | "embedding"


@dataclass(frozen=True)
class AreaAssignStats:
    """Outcome of the weekly area mop-up over topicless, area-less notes."""

    assigned: int
    skipped_low_confidence: int
    no_signal: int
    # (path, area) for each assigned note, capped at the run's limit — surfaced
    # in the digest's Status section for spot-veto.
    assigned_paths: tuple[tuple[str, str], ...] = ()


def area_centroids(store: Store) -> dict[str, np.ndarray]:
    """Map ``{area_slug: unit mean of that area's topic centroids}``.

    Areas with no topics are absent (they can't be embedding-matched).
    Zero-norm topic centroids are skipped defensively.
    """
    by_area: dict[str, list[np.ndarray]] = {}
    for topic in store.load_topics():
        if topic.area is None or float(np.linalg.norm(topic.centroid)) == 0.0:
            continue
        by_area.setdefault(topic.area, []).append(topic.centroid)
    out: dict[str, np.ndarray] = {}
    for area, vectors in by_area.items():
        mean = np.mean(vectors, axis=0)
        norm = float(np.linalg.norm(mean))
        if norm == 0.0:
            continue
        out[area] = (mean / norm).astype(np.float32)
    return out


def classify_area(
    note_text: str,
    note_vector: np.ndarray | None,
    areas: list[Area],
    centroids: dict[str, np.ndarray],
    llm: LLM | None,
) -> AreaCandidate | None:
    """Classify ``note_text`` into one area; LLM first, embedding fallback."""
    if llm is not None:
        candidate = _llm_candidate(note_text, areas, llm)
        if candidate is not None:
            return candidate
    return _embedding_candidate(note_vector, centroids)


def annotate_queue_reason(reason: str, pick: str, confidence: float) -> str:
    """Append the classifier's pick to a queue reason for human review."""
    return f"{reason}; llm: {pick} ({confidence:.2f})"


def assign_areas(
    cfg: Config,
    store: Store,
    llm: LLM | None,
    limit: int = 50,
) -> AreaAssignStats:
    """Weekly mop-up: assign an area to topicless, area-less notes.

    Targets notes with NO topic membership and no ``area/*`` tag (sorted, up to
    ``limit``). Each is classified with its stored vector; a candidate that clears
    its source's bar (llm ≥ 0.8, embedding ≥ 0.55, compared against the RAW
    confidence) gets ``area/<slug>`` + ``area_provenance: auto`` written to the
    note via house I/O. No key → ``llm`` is None → the embedding path still runs
    (that fallback IS the no-LLM path).
    """
    targets = _area_targets(store, limit)
    vectors = store.note_vectors_for(targets)
    texts = store.note_texts()
    areas = list(SEEDED_AREAS)
    centroids = area_centroids(store)
    vault_resolved = cfg.vault_path.resolve()

    assigned = 0
    skipped_low = 0
    no_signal = 0
    assigned_paths: list[tuple[str, str]] = []
    for path in targets:
        resolved = (cfg.vault_path / path).resolve()
        if not resolved.is_relative_to(vault_resolved) or not resolved.is_file():
            continue
        candidate = classify_area(
            texts.get(path, ""), vectors.get(path), areas, centroids, llm
        )
        if candidate is None:
            no_signal += 1
            continue
        if not _clears_bar(candidate):
            skipped_low += 1
            continue
        _write_area_tag(resolved, candidate.slug)
        assigned += 1
        if len(assigned_paths) < limit:
            assigned_paths.append((path, candidate.slug))
    return AreaAssignStats(
        assigned=assigned,
        skipped_low_confidence=skipped_low,
        no_signal=no_signal,
        assigned_paths=tuple(assigned_paths),
    )


def _area_targets(store: Store, limit: int) -> list[str]:
    """Sorted topicless note paths carrying no ``area/*`` tag (≤ ``limit``)."""
    area_tagged = {
        path
        for tag, paths in store.notes_by_tag().items()
        if tag.startswith("area/")
        for path in paths
    }
    topicless = store.notes_without_topic()
    return sorted(p for p in topicless if p not in area_tagged)[:limit]


def _clears_bar(candidate: AreaCandidate) -> bool:
    """True if the candidate's RAW confidence meets its source's threshold."""
    bar = (
        AUTO_AREA_MIN_LLM_CONF
        if candidate.source == "llm"
        else AUTO_AREA_MIN_EMBED_COS
    )
    return candidate.confidence >= bar


def _write_area_tag(note_path: Path, area_slug: str) -> None:
    """Append ``area/<slug>`` once and stamp ``area_provenance: auto`` (house I/O)."""
    post = load_post(note_path.read_text())
    tags = _normalize_tags(post.get("tags"))
    wanted = f"area/{area_slug}"
    if wanted not in tags:
        tags.append(wanted)
    post["tags"] = tags
    post["area_provenance"] = "auto"
    write_post_atomic(note_path, post)


def _normalize_tags(value: object) -> list[str]:
    """Coerce a frontmatter ``tags`` value (absent/scalar/list) to a list of strings."""
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        return [str(value)]
    return [str(item) for item in value]


def _llm_candidate(
    note_text: str, areas: list[Area], llm: LLM
) -> AreaCandidate | None:
    """Prompt the LLM; parse+validate its reply, else ``None`` (never raises)."""
    valid = {area.slug for area in areas}
    system = _SYSTEM_PREFIX + ", ".join(area.slug for area in areas) + "."
    registry = "\n".join(f"- {area.slug}: {area.description}" for area in areas)
    user = f"{note_text}\n\nAreas:\n{registry}"
    obj = _extract_json(llm.complete(system, user))
    if obj is None:
        return None
    return _parse_candidate(obj, valid)


def _extract_json(text: str) -> dict | None:
    """Parse the first ``{`` … ``}`` span as a JSON object; bad input → None."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def _parse_candidate(obj: dict, valid: set[str]) -> AreaCandidate | None:
    """Validate slug against ``valid`` and clamp confidence to [0, 1]."""
    slug = obj.get("area")
    if slug not in valid:
        return None
    try:
        confidence = float(obj.get("confidence"))
    except (TypeError, ValueError):
        return None
    confidence = max(0.0, min(1.0, confidence))
    return AreaCandidate(slug, confidence, "llm")


def _embedding_candidate(
    note_vector: np.ndarray | None, centroids: dict[str, np.ndarray]
) -> AreaCandidate | None:
    """Best cosine of ``note_vector`` vs ``centroids`` → candidate, else None."""
    if note_vector is None or not centroids:
        return None
    if float(np.linalg.norm(note_vector)) == 0.0:
        return None
    best_slug = None
    best_cos = -2.0  # below cosine's [-1, 1] range so the first centroid wins
    for slug, centroid in centroids.items():
        cos = cosine(note_vector, centroid)
        if cos > best_cos:
            best_slug, best_cos = slug, cos
    return AreaCandidate(best_slug, best_cos, "embedding")
