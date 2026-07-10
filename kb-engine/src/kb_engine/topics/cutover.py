"""Mass-retag cutover: rewrite vault tags from a human-approved migration proposal.

The cutover consumes ONLY the parsed, approved ``MigrationProposal`` (decisions
stay human-gated, D14) and rewrites each note's frontmatter tags — dropping the
legacy two-level/category tags, adding ``topic/<slug>`` for map/topic decisions,
and settling exactly one ``area/<slug>``. ``dry_run=True`` (the default) computes
everything — counts, diff, would-be new topics — but writes NOTHING (no files, no
store rows), so a supervised dry-run diff can precede the live apply.

Idempotency: a second real run changes nothing — the tags are already migrated
(so per-note rewrites are no-ops) and the manual topics already exist (creation is
skipped). Note-area precedence per note: an existing ``area/*`` tag always wins;
else the note's existing primary topic's area; else the majority implied area of
its dropped tags (ties → the first disposed tag in the note's original order).
"""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics._math import cosine
from kb_engine.topics.migration import MigrationProposal, TagDisposition
from kb_engine.vault import load_post, write_post_atomic

_TOPIC_PREFIX = "topic/"
_AREA_PREFIX = "area/"


@dataclass(frozen=True)
class CutoverResult:
    notes_changed: int
    tags_dropped: int
    topic_tags_added: int
    area_tags_added: int
    topics_created: tuple[str, ...]
    skipped_unreadable: tuple[str, ...]
    diff_lines: tuple[str, ...]  # per-note "path: -Dev/Rust +topic/rust-learning +area/dev"


@dataclass(frozen=True)
class _NoteEdits:
    notes_changed: int
    tags_dropped: int
    topic_tags_added: int
    area_tags_added: int
    skipped_unreadable: tuple[str, ...]
    diff_lines: tuple[str, ...]


def _as_tag_list(value: object) -> list[str]:
    """Normalize a frontmatter ``tags`` value (absent/scalar/list) to a list."""
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        return [str(value)]
    return [str(item) for item in value]


def _topic_label(tag: str) -> str:
    """Label for a bootstrapped topic: a two-level tag's subcategory, title-cased
    (``Business/Marketing`` → ``Marketing``); a bare category tag verbatim
    (``GameDev`` → ``GameDev``)."""
    if "/" in tag:
        return tag.split("/", 1)[1].title()
    return tag


def _unit_mean(vectors: list[np.ndarray]) -> np.ndarray | None:
    """Unit-normalized mean of ``vectors``; ``None`` if the mean has zero norm."""
    mean = np.mean(np.stack(vectors), axis=0)
    norm = float(np.linalg.norm(mean))
    if norm == 0.0:
        return None
    return (mean / norm).astype(np.float32)


def _effective_topic_area(store: Store, proposal: MigrationProposal) -> dict[str, str]:
    """Topic slug → area after overlaying the proposal's (non-empty) topic→area rows.

    Computed from a pre-cutover snapshot + the proposal, so it is identical in
    dry-run and real runs (never re-reads a mutated store)."""
    area_by_slug = {t.slug: t.area for t in store.load_topics() if t.area}
    for row in proposal.topic_areas:
        if row.proposed_area:
            area_by_slug[row.slug] = row.proposed_area
    return area_by_slug


def _note_primary_area(store: Store, effective_area: dict[str, str]) -> dict[str, str]:
    """Note path → its existing primary topic's (effective) area — cutover
    precedence tier 1. Reads existing primary memberships only; the topics
    created by this cutover never feed back into precedence."""
    out: dict[str, str] = {}
    for topic in store.load_topics():
        area = effective_area.get(topic.slug)
        if not area:
            continue
        for member in store.topic_members(topic.slug):
            if member.is_primary:
                out[member.note_path] = area
    return out


def _pinned_primary_paths(store: Store) -> set[str]:
    """Notes already primary somewhere (any source) — they must not become the
    primary of a newly bootstrapped topic (they keep their existing home)."""
    pinned = set(store.user_primary_paths())
    for topic in store.load_topics():
        for member in store.topic_members(topic.slug):
            if member.is_primary:
                pinned.add(member.note_path)
    return pinned


def _create_new_topics(
    store: Store, proposal: MigrationProposal, dry_run: bool
) -> tuple[list[str], list[str]]:
    """Bootstrap a manual topic per ``topic:`` disposition (idempotent, gated).

    Returns ``(created_slugs, skip_diff_lines)``. Existing slugs are skipped
    (idempotent re-run). A tag whose notes have no usable vectors is skipped and
    recorded in the diff (its notes' tags are still rewritten downstream)."""
    existing = {t.slug for t in store.load_topics()}
    notes_by_tag = store.notes_by_tag()
    topic_disps = [d for d in proposal.dispositions if d.decision.startswith("topic:")]
    all_paths = sorted({p for d in topic_disps for p in notes_by_tag.get(d.tag, ())})
    vectors = store.note_vectors_for(all_paths)
    pinned = _pinned_primary_paths(store)
    created: list[str] = []
    skips: list[str] = []
    for disposition in topic_disps:
        slug = disposition.decision.split(":", 1)[1]
        if slug in existing:
            continue
        vecs = [
            (p, vectors[p])
            for p in sorted(notes_by_tag.get(disposition.tag, ()))
            if p in vectors
        ]
        centroid = _unit_mean([v for _, v in vecs]) if vecs else None
        if centroid is None:
            skips.append(f"topic-skip: {slug} — no usable vectors for {disposition.tag}")
            continue
        created.append(slug)
        members = [
            TopicMember(p, cosine(v, centroid), "auto", is_primary=p not in pinned)
            for p, v in vecs
        ]
        pinned.update(p for p, _ in vecs)
        if not dry_run:
            _persist_topic(store, slug, disposition, centroid, members)
    return created, skips


def _persist_topic(
    store: Store,
    slug: str,
    disposition: TagDisposition,
    centroid: np.ndarray,
    members: list[TopicMember],
) -> None:
    try:
        store.add_manual_topic(
            slug, _topic_label(disposition.tag),
            f"Migrated from tag {disposition.tag}", centroid,
        )
    except ValueError:
        return  # already exists (raced/idempotent) — leave it and its members be
    store.set_topic_area(slug, disposition.area)
    store.set_members(slug, members)


def _majority_dropped_area(
    drops: list[str], disp_by_tag: dict[str, TagDisposition]
) -> str | None:
    """Majority implied area across the note's dropped tags; ties resolve to the
    area of the first dropped tag in the note's original order."""
    areas = [disp_by_tag[t].area for t in drops if disp_by_tag[t].area]
    if not areas:
        return None
    counts = Counter(areas)
    top = max(counts.values())
    return next(area for area in areas if counts[area] == top)


def _note_tag_rewrite(
    tags: list[str],
    note_dispositions: list[TagDisposition],
    primary_area: str | None,
) -> tuple[list[str], list[str], list[str]]:
    """Compute one note's new tag list from its disposed tags. Returns
    ``(new_tags, drops, adds)``: disposed tags dropped (order-preserving), a
    ``topic/<slug>`` appended per map/topic decision (no dupes), and at most one
    ``area/<slug>`` — unless the note already carries an ``area/*`` (existing wins)."""
    disp_by_tag = {d.tag: d for d in note_dispositions}
    drops = [t for t in tags if t in disp_by_tag]
    kept = [t for t in tags if t not in disp_by_tag]
    adds: list[str] = []
    for disposition in note_dispositions:
        if disposition.decision.startswith(("map:", "topic:")):
            topic_tag = _TOPIC_PREFIX + disposition.decision.split(":", 1)[1]
            if topic_tag not in kept and topic_tag not in adds:
                adds.append(topic_tag)
    if not any(t.startswith(_AREA_PREFIX) for t in kept):
        area = primary_area or _majority_dropped_area(drops, disp_by_tag)
        if area:
            adds.append(_AREA_PREFIX + area)
    return kept + adds, drops, adds


def _diff_line(rel: str, drops: list[str], adds: list[str]) -> str:
    return f"{rel}: " + " ".join([f"-{d}" for d in drops] + [f"+{a}" for a in adds])


def _write_note(path: Path, post, new_tags: list[str]) -> None:
    post["tags"] = new_tags
    write_post_atomic(path, post)


def _rewrite_notes(
    store: Store,
    vault_path: Path,
    proposal: MigrationProposal,
    note_primary_area: dict[str, str],
    dry_run: bool,
) -> _NoteEdits:
    """Rewrite every note carrying a disposed tag (union over dispositions)."""
    disp_by_tag = {d.tag: d for d in proposal.dispositions}
    notes_by_tag = store.notes_by_tag()
    candidates = sorted({p for tag in disp_by_tag for p in notes_by_tag.get(tag, ())})
    vault_resolved = vault_path.resolve()
    changed = dropped = topic_added = area_added = 0
    skipped: list[str] = []
    diff_lines: list[str] = []
    for rel in candidates:
        resolved = (vault_path / rel).resolve()
        if not resolved.is_relative_to(vault_resolved) or not resolved.is_file():
            continue
        try:
            post = load_post(resolved.read_text())
        except OSError:
            skipped.append(rel)
            continue
        tags = _as_tag_list(post.get("tags"))
        note_disps = [disp_by_tag[t] for t in tags if t in disp_by_tag]
        if not note_disps:
            continue
        new_tags, drops, adds = _note_tag_rewrite(
            tags, note_disps, note_primary_area.get(rel)
        )
        if new_tags == tags:
            continue
        changed += 1
        dropped += len(drops)
        topic_added += sum(1 for a in adds if a.startswith(_TOPIC_PREFIX))
        area_added += sum(1 for a in adds if a.startswith(_AREA_PREFIX))
        diff_lines.append(_diff_line(rel, drops, adds))
        if not dry_run:
            _write_note(resolved, post, new_tags)
    return _NoteEdits(
        changed, dropped, topic_added, area_added, tuple(skipped), tuple(diff_lines)
    )


def apply_cutover(
    store: Store, vault_path: Path, proposal: MigrationProposal, dry_run: bool = True
) -> CutoverResult:
    """Execute the approved taxonomy migration. Dry-run (default) writes nothing
    but reports the same counts/diff as a live apply would produce."""
    effective_area = _effective_topic_area(store, proposal)
    note_primary_area = _note_primary_area(store, effective_area)
    diff_lines = [
        f"topic-area: {row.slug} -> {row.proposed_area}"
        for row in proposal.topic_areas
        if row.proposed_area
    ]
    if not dry_run:
        for row in proposal.topic_areas:
            if row.proposed_area:
                store.set_topic_area(row.slug, row.proposed_area)
    created, skips = _create_new_topics(store, proposal, dry_run)
    diff_lines.extend(skips)
    edits = _rewrite_notes(store, vault_path, proposal, note_primary_area, dry_run)
    return CutoverResult(
        notes_changed=edits.notes_changed,
        tags_dropped=edits.tags_dropped,
        topic_tags_added=edits.topic_tags_added,
        area_tags_added=edits.area_tags_added,
        topics_created=tuple(created),
        skipped_unreadable=edits.skipped_unreadable,
        diff_lines=tuple(diff_lines) + edits.diff_lines,
    )
