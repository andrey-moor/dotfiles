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


def _apply_to_note(
    note_path: Path, slugs: list[str], primary_slug: str | None
) -> tuple[bool, int]:
    """Add missing ``topic/<slug>`` tags and set ``primary_topic`` on one note.

    Returns ``(changed, tags_added)``: ``changed`` is True if the file was
    rewritten (tags added and/or the ``primary_topic`` field newly set/changed);
    ``tags_added`` counts only newly-written topic tags.
    """
    post = load_post(note_path.read_text())
    existing = _as_tag_list(post.get("tags"))
    new_tags = [f"{_TOPIC_TAG_PREFIX}/{slug}" for slug in slugs]
    to_add = [tag for tag in new_tags if tag not in existing]

    primary_changed = (
        primary_slug is not None and post.get("primary_topic") != primary_slug
    )
    if not to_add and not primary_changed:
        return (False, 0)

    if to_add:
        post["tags"] = existing + to_add
    if primary_changed:
        post["primary_topic"] = primary_slug
    write_post_atomic(note_path, post)
    return (True, len(to_add))


def apply_topic_tags(
    store: Store,
    vault_path: Path,
    only_status: tuple[str, ...] = DEFAULT_APPLY_STATUSES,
) -> ApplyResult:
    """Write ``topic/<slug>`` tags into member notes' frontmatter (gated, idempotent).

    The only note-mutating operation in the engine. For each topic whose status
    is in ``only_status`` (default ``active`` — proposed topics are skipped), each
    member note gets its ``topic/<slug>`` tag added if absent. Notes whose membership
    includes a primary (``is_primary=True``) entry also get a
    ``primary_topic: <slug>`` frontmatter field. Both writes are idempotent.
    Body and other frontmatter are preserved; member files missing on disk are skipped
    and reported. Re-running adds nothing new.
    """
    by_note = _slugs_to_add_by_note(store, only_status)
    primary_by_note = _primary_by_note(store, only_status)
    vault_resolved = vault_path.resolve()

    n_changed = 0
    n_tags_added = 0
    skipped_missing: list[str] = []
    skipped_outside_vault: list[str] = []
    for note_rel in sorted(by_note):
        resolved = (vault_path / note_rel).resolve()
        # Never write outside the vault: a member path like "../outside.md" is
        # skipped and reported, not applied.
        if not resolved.is_relative_to(vault_resolved):
            skipped_outside_vault.append(note_rel)
            continue
        if not resolved.is_file():
            skipped_missing.append(note_rel)
            continue
        changed, added = _apply_to_note(
            resolved, by_note[note_rel], primary_by_note.get(note_rel)
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
