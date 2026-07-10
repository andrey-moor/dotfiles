"""Write topic assignments back into note frontmatter (the vault is the record).

For every member note of an in-status topic, apply adds ``topic/<slug>`` tags,
sets ``primary_topic`` to the note's home topic, and fills the ``area/<slug>``
tag from that primary's registry area — falling back to the best-scoring
secondary topic's area for notes that are nobody's primary. Writes go through the
house atomic I/O and skip notes missing from disk or resolving outside the vault.
"""
from dataclasses import dataclass
from pathlib import Path

from kb_engine.store import Store
from kb_engine.vault import load_post, write_post_atomic

_TOPIC_TAG_PREFIX = "topic"
DEFAULT_APPLY_STATUSES = ("active",)


@dataclass(frozen=True)
class ApplyResult:
    n_changed: int  # notes whose frontmatter was rewritten (tags added and/or primary_topic set)
    n_tags_added: int  # total topic tags written across all notes
    skipped_missing: tuple[str, ...] = ()  # member paths not on disk
    skipped_outside_vault: tuple[str, ...] = ()  # member paths that escape the vault


def _as_tag_list(value: object) -> list[str]:
    """Normalize a frontmatter ``tags`` value (absent/scalar/list) to a list.

    A scalar (``str``/``int``/``float`` — e.g. ``tags: 42``) is treated as a
    single-element list so a malformed note can't abort the whole apply with a
    ``TypeError`` from iterating a non-iterable.
    """
    if value is None:
        return []
    if isinstance(value, (str, int, float)):
        return [str(value)]
    return [str(item) for item in value]


def _slugs_to_add_by_note(
    store: Store, only_status: tuple[str, ...]
) -> dict[str, list[str]]:
    """Collect, per member note path, the topic slugs to apply (deterministic).

    Only topics whose ``status`` is in ``only_status`` contribute. Slugs are
    de-duplicated and sorted so output is stable regardless of topic ordering.
    """
    wanted = set(only_status)
    by_note: dict[str, set[str]] = {}
    for topic in store.load_topics():
        if topic.status not in wanted:
            continue
        for member in store.topic_members(topic.slug):
            by_note.setdefault(member.note_path, set()).add(topic.slug)
    return {note: sorted(slugs) for note, slugs in by_note.items()}


def _primary_by_note(store: Store, only_status: tuple[str, ...]) -> dict[str, str]:
    """Map each note to its primary (home) topic slug, for topics in ``only_status``.

    A note is the primary member of at most one topic; if the cache holds more than
    one primary row for a note (data inconsistency), the lexicographically-last
    topic slug wins (topics are sorted by slug here for deterministic output).
    """
    wanted = set(only_status)
    primary: dict[str, str] = {}
    for topic in sorted(store.load_topics(), key=lambda t: t.slug):
        if topic.status not in wanted:
            continue
        for member in store.topic_members(topic.slug):
            if member.is_primary:
                primary[member.note_path] = topic.slug
    return primary


def _area_by_note(store: Store, only_status: tuple[str, ...]) -> dict[str, str]:
    """Map each note to its primary topic's area slug, for topics in ``only_status``.

    Selects the SAME primary as ``_primary_by_note`` (sorted by slug, last wins on
    a data inconsistency), then reports that primary topic's ``area`` — so a note's
    area always matches its chosen primary. Notes whose selected primary has no
    area (``Topic.area is None``) are absent, so apply leaves their ``area/*`` tags
    untouched.
    """
    wanted = set(only_status)
    by_note: dict[str, str | None] = {}
    for topic in sorted(store.load_topics(), key=lambda t: t.slug):
        if topic.status not in wanted:
            continue
        for member in store.topic_members(topic.slug):
            if member.is_primary:
                by_note[member.note_path] = topic.area
    return {note: area for note, area in by_note.items() if area is not None}


def _secondary_fill_by_note(
    store: Store, only_status: tuple[str, ...]
) -> dict[str, str]:
    """Map each secondary-only note to the area of its best-scoring areaed topic.

    A "secondary-only" note has ≥1 membership among ``only_status`` topics yet is
    the primary of none of them, so neither existing writer (the primary path here,
    nor the classifier mop-up over topicless notes) assigns it an area. Scope
    matches ``_primary_by_note``: only ``only_status`` topics are consulted, so a
    note primaried solely in an out-of-status topic still counts as secondary-only.

    Among such a note's secondary memberships in topics that carry a registry
    ``area``, the best wins by (score desc, then slug asc); its area is the fill
    value. Iterating topics in slug order and replacing only on a strictly-greater
    score yields that ordering. Notes with no areaed secondary topic are absent, so
    apply then leaves their ``area/*`` tags alone.
    """
    wanted = set(only_status)
    has_primary: set[str] = set()
    best_score: dict[str, float] = {}
    fill: dict[str, str] = {}
    for topic in sorted(store.load_topics(), key=lambda t: t.slug):
        if topic.status not in wanted:
            continue
        for member in store.topic_members(topic.slug):
            if member.is_primary:
                has_primary.add(member.note_path)
                continue
            if topic.area is None:
                continue
            note = member.note_path
            if note not in best_score or member.score > best_score[note]:
                best_score[note] = member.score
                fill[note] = topic.area
    return {note: area for note, area in fill.items() if note not in has_primary}


def _has_area_tag(tags: list[str]) -> bool:
    """True if any tag is an ``area/*`` tag (the fill path must never overwrite one)."""
    return any(tag.startswith("area/") for tag in tags)


def _with_area_tag(tags: list[str], area_slug: str) -> list[str]:
    """Return ``tags`` carrying exactly one ``area/<slug>``.

    An existing ``area/*`` tag is replaced in place (its position preserved, any
    further ``area/*`` tags dropped); if none is present, ``area/<slug>`` is
    appended. Idempotent when ``tags`` already holds only ``area/<slug>``.
    """
    wanted = f"area/{area_slug}"
    out: list[str] = []
    placed = False
    for tag in tags:
        if tag.startswith("area/"):
            if not placed:
                out.append(wanted)
                placed = True
            # else: drop a stale/duplicate area tag (apply owns the area vocabulary)
        else:
            out.append(tag)
    if not placed:
        out.append(wanted)
    return out


def _apply_to_note(
    note_path: Path,
    slugs: list[str],
    primary_slug: str | None,
    area_slug: str | None = None,
    fill_area_slug: str | None = None,
) -> tuple[bool, int]:
    """Add missing ``topic/<slug>`` tags, own/fill the ``area/<slug>`` tag, and set
    ``primary_topic`` on one note.

    Two mutually exclusive area behaviors: ``area_slug`` (the primary path) OWNS the
    area vocabulary — it replaces any stale ``area/*`` in place; ``fill_area_slug``
    (the secondary-only path) is ADD-ONLY — it appends ``area/<slug>`` solely when
    the note carries no ``area/*`` yet, and never replaces one. The primary path
    takes precedence; the two are disjoint by construction (a note with a primary is
    never in the fill map).

    Returns ``(changed, tags_added)``: ``changed`` is True if the file was
    rewritten (topic tags added, the ``area/*`` tag added/replaced, and/or the
    ``primary_topic`` field newly set/changed); ``tags_added`` counts only
    newly-written topic tags (area edits never count).
    """
    post = load_post(note_path.read_text())
    existing = _as_tag_list(post.get("tags"))
    new_tags = [f"{_TOPIC_TAG_PREFIX}/{slug}" for slug in slugs]
    to_add = [tag for tag in new_tags if tag not in existing]

    tags_after = existing + to_add
    if area_slug is not None:
        tags_after = _with_area_tag(tags_after, area_slug)
    elif fill_area_slug is not None and not _has_area_tag(existing):
        tags_after = tags_after + [f"area/{fill_area_slug}"]

    primary_changed = (
        primary_slug is not None and post.get("primary_topic") != primary_slug
    )
    if tags_after == existing and not primary_changed:
        return (False, 0)

    if tags_after != existing:
        post["tags"] = tags_after
    if primary_changed:
        post["primary_topic"] = primary_slug
    write_post_atomic(note_path, post)
    return (True, len(to_add))


def _apply_members(
    vault_path: Path,
    by_note: dict[str, list[str]],
    primary_by_note: dict[str, str],
    area_by_note: dict[str, str],
    secondary_fill: dict[str, str],
) -> ApplyResult:
    """Execute the per-note plan: apply tags to each member in deterministic order,
    skipping (and reporting) notes missing on disk or escaping the vault.

    A member path like ``../outside.md`` is never written — the engine only mutates
    files inside ``vault_path``.
    """
    vault_resolved = vault_path.resolve()
    n_changed = 0
    n_tags_added = 0
    skipped_missing: list[str] = []
    skipped_outside_vault: list[str] = []
    for note_rel in sorted(by_note):
        resolved = (vault_path / note_rel).resolve()
        if not resolved.is_relative_to(vault_resolved):
            skipped_outside_vault.append(note_rel)
            continue
        if not resolved.is_file():
            skipped_missing.append(note_rel)
            continue
        changed, added = _apply_to_note(
            resolved,
            by_note[note_rel],
            primary_by_note.get(note_rel),
            area_by_note.get(note_rel),
            secondary_fill.get(note_rel),
        )
        if changed:
            n_changed += 1
        n_tags_added += added

    return ApplyResult(
        n_changed=n_changed,
        n_tags_added=n_tags_added,
        skipped_missing=tuple(skipped_missing),
        skipped_outside_vault=tuple(skipped_outside_vault),
    )


def apply_topic_tags(
    store: Store,
    vault_path: Path,
    only_status: tuple[str, ...] = DEFAULT_APPLY_STATUSES,
) -> ApplyResult:
    """Write ``topic/<slug>`` tags into member notes' frontmatter (gated, idempotent).

    The only note-mutating operation in the engine. For each topic whose status is
    in ``only_status`` (default ``active`` — proposed topics are skipped), each member
    note gets its ``topic/<slug>`` tag added if absent. A primary (``is_primary=True``)
    member also gets a ``primary_topic: <slug>`` field, and — when that primary topic
    has a registry area — exactly one ``area/<slug>`` tag (apply owns the ``area/*``
    vocabulary for topicked notes: the single sanctioned tag removal, replacing any
    stale area tag).

    A secondary-only note (member of ``only_status`` topics but primary of none)
    gets an ADD-ONLY area fill from its best-scoring areaed topic, applied solely
    when it carries no ``area/*`` yet (never replaced) — the primary and fill sets
    are disjoint by construction. All writes are idempotent; body/other frontmatter
    preserved.
    """
    return _apply_members(
        vault_path,
        _slugs_to_add_by_note(store, only_status),
        _primary_by_note(store, only_status),
        _area_by_note(store, only_status),
        _secondary_fill_by_note(store, only_status),
    )
