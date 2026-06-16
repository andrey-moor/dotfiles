"""Deterministic KB state digest.

Renders an idempotent markdown report of the knowledge base's review state:
inbox backlog, proposals awaiting naming/approval, topic/area counts, unfiled
notes, and a "needs review" checklist. The body contains no timestamps so
re-running produces an identical file; a caller may pass a date for context.
"""

from pathlib import Path

from kb_engine.models import Topic
from kb_engine.store import Store

# Discovered topics in these statuses still need a human to name/approve them.
_PROPOSAL_STATUSES = frozenset({"proposed", "discovered"})
_MAX_UNFILED_LISTED = 25


def count_proposals(topics: list[Topic]) -> int:
    """Number of discovered topics still awaiting naming/approval."""
    return sum(
        1
        for t in topics
        if t.kind == "discovered" and t.status in _PROPOSAL_STATUSES
    )


def build_digest(
    store: Store,
    vault_path: Path,
    inbox_count: int,
    unfiled: list[str],
) -> str:
    """Render the KB review digest as deterministic markdown.

    ``inbox_count`` is the inbox backlog size and ``unfiled`` the list of notes
    not assigned to any topic — both computed by the caller from the vault/store
    so this function stays pure and testable.
    """
    topics = store.load_topics()
    areas = store.load_areas()
    n_proposals = count_proposals(topics)
    n_topics = len(topics)
    n_areas = len(areas)
    n_unfiled = len(unfiled)

    lines: list[str] = [
        "# KB Digest",
        "",
        "## Summary",
        "",
        f"- Inbox backlog: {inbox_count}",
        f"- Topic proposals awaiting review: {n_proposals}",
        f"- Topics: {n_topics}",
        f"- Areas: {n_areas}",
        f"- Unfiled notes: {n_unfiled}",
        "",
        "## Needs review",
        "",
    ]

    checklist: list[str] = []
    if inbox_count:
        checklist.append(
            f"- [ ] Process {inbox_count} inbox stub(s) (`kb-engine`/`/kb:process`)"
        )
    if n_proposals:
        checklist.append(
            f"- [ ] Name/approve {n_proposals} proposed topic(s) "
            "(`kb-engine topics list`)"
        )
    if n_unfiled:
        checklist.append(f"- [ ] File {n_unfiled} unfiled note(s)")
    if not checklist:
        checklist.append("- [x] Nothing to review.")
    lines.extend(checklist)

    if unfiled:
        lines.extend(["", "## Unfiled notes", ""])
        for note_path in sorted(unfiled)[:_MAX_UNFILED_LISTED]:
            lines.append(f"- [[{note_path}]]")
        remaining = n_unfiled - _MAX_UNFILED_LISTED
        if remaining > 0:
            lines.append(f"- …and {remaining} more")

    return "\n".join(lines).rstrip() + "\n"
