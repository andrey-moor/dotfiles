"""Deterministic KB state digest.

Renders an idempotent markdown report of the knowledge base's review state:
inbox backlog, proposals awaiting naming/approval, topic/area counts, unfiled
notes, and a "needs review" checklist. The body contains no timestamps so
re-running produces an identical file; a caller may pass a date for context.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from kb_engine.config import Config
from kb_engine.models import Topic
from kb_engine.store import Store

# Discovered topics in these statuses still need a human to name/approve them.
# (Valid statuses are proposed/active/deprecated — "discovered" is a kind, never
# a status, so it has no place here.)
_PROPOSAL_STATUSES = frozenset({"proposed"})
_MAX_UNFILED_LISTED = 25
_MAX_QUEUE_LISTED = 10
_DIGEST_RELPATH = Path("_system") / "kb-digest.md"


@dataclass(frozen=True)
class DigestStatus:
    """A run's outcome, rendered as the digest's leading ``## Status`` section.

    ``outcomes`` is a ``tuple[StepOutcome, ...]`` (each with ``.name``/``.ok``/
    ``.detail``) but is typed loosely as ``tuple`` here to avoid a pipeline<->digest
    import cycle.
    """

    tier: str
    ok: bool
    outcomes: tuple


def _status_section(status: DigestStatus) -> list[str]:
    """Render the leading ``## Status`` block. The timestamp is computed here at
    render time (the only non-deterministic line in the whole digest)."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    state = "✅ ok" if status.ok else "⚠️ FAILED"
    lines = [
        "## Status",
        "",
        f"- Last run: {stamp} · tier: {status.tier} · {state}",
    ]
    lines.extend(f"- {o.name}: {o.detail}" for o in status.outcomes)
    lines.append("")
    return lines


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
    status: DigestStatus | None = None,
) -> str:
    """Render the KB review digest as deterministic markdown.

    ``inbox_count`` is the inbox backlog size and ``unfiled`` the list of notes
    not assigned to any topic — both computed by the caller from the vault/store
    so this function stays pure and testable. When ``status`` is given, a leading
    ``## Status`` section (with a render-time timestamp) is prepended; the body
    below ``## Summary`` stays deterministic.
    """
    topics = store.load_topics()
    areas = store.load_areas()
    queue = store.load_review_queue()
    n_proposals = count_proposals(topics)
    n_topics = len(topics)
    n_areas = len(areas)
    n_unfiled = len(unfiled)

    lines: list[str] = ["# KB Digest", ""]
    if status is not None:
        lines.extend(_status_section(status))
    lines.extend([
        "## Summary",
        "",
        f"- Inbox backlog: {inbox_count}",
        f"- Topic proposals awaiting review: {n_proposals}",
        f"- Topics: {n_topics}",
        f"- Areas: {n_areas}",
        f"- Unfiled notes: {n_unfiled}",
    ])
    if queue:
        lines.append(f"- Borderline queue: {len(queue)}")
    lines.extend(["", "## Needs review", ""])

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
    if queue:
        checklist.append(
            f"- [ ] Decide {len(queue)} borderline assignment(s) (`/kb:review`)"
        )
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

    if queue:
        lines.extend(["", "## Borderline queue", ""])
        for entry in queue[:_MAX_QUEUE_LISTED]:
            options = ", ".join(
                f"{slug} ({score:.2f})" for slug, score in entry.candidates
            )
            lines.append(f"- [[{entry.note_path}]] → {options}")
        if len(queue) > _MAX_QUEUE_LISTED:
            lines.append(f"- …and {len(queue) - _MAX_QUEUE_LISTED} more")

    return "\n".join(lines).rstrip() + "\n"


def write_digest(
    cfg: Config, store: Store, status: DigestStatus | None = None
) -> Path:
    """Render the digest and write it to ``<vault>/_system/kb-digest.md``.

    The file-writing wrapper the pipeline calls. Inbox/unfiled counts come from
    the pipeline helpers, imported lazily to avoid a pipeline<->digest cycle.
    Returns the absolute path written.
    """
    from kb_engine.pipeline import count_inbox, unfiled_notes

    text = build_digest(
        store,
        vault_path=cfg.vault_path,
        inbox_count=count_inbox(cfg.vault_path),
        unfiled=unfiled_notes(store),
        status=status,
    )
    digest_path = cfg.vault_path / _DIGEST_RELPATH
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(text)
    return digest_path
