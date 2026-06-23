"""Validate Knowledge/inbox/ notes against the clip schema (report-only).

A gate for the capture spike: confirms clipped notes carry the inbox schema,
reports whether each recorded its "why", and surfaces duplicate URLs (within the
inbox and against already-filed notes). It never mutates notes — surfacing,
never guessing, is the contract.
"""

from dataclasses import dataclass
from pathlib import Path

from kb_engine.importing.urls import normalize_url
from kb_engine.vault import iter_notes

# Keys every inbox note must carry (the clip schema, minus summary/context/why
# which may be empty/absent at capture time).
_REQUIRED_KEYS = ("title", "url", "source", "date_added", "status", "tags")
_INBOX_RELDIR = "Knowledge/inbox"


@dataclass(frozen=True)
class InboxReport:
    n_notes: int
    schema_ok: tuple[str, ...]
    schema_bad: tuple[tuple[str, tuple[str, ...]], ...]  # (path, missing keys)
    missing_why: tuple[str, ...]
    dup_in_inbox: tuple[tuple[str, tuple[str, ...]], ...]  # (norm url, paths)
    dup_vs_knowledge: tuple[tuple[str, str], ...]  # (inbox path, norm url)


def _present(fm, key: str) -> bool:
    """True if the key exists and is non-empty (empty string counts as absent;
    an empty tags list still counts as a present 'tags' key)."""
    if key not in fm:
        return False
    value = fm.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def check_inbox(vault: Path) -> InboxReport:
    vault = Path(vault)
    inbox_dir = vault / _INBOX_RELDIR
    schema_ok: list[str] = []
    schema_bad: list[tuple[str, tuple[str, ...]]] = []
    missing_why: list[str] = []
    by_url: dict[str, list[str]] = {}

    notes = list(iter_notes(inbox_dir, base=vault)) if inbox_dir.is_dir() else []
    for note in notes:
        fm = note.frontmatter
        missing = tuple(k for k in _REQUIRED_KEYS if not _present(fm, k))
        if missing:
            schema_bad.append((note.path, missing))
        else:
            schema_ok.append(note.path)
        if not _present(fm, "why"):
            missing_why.append(note.path)
        url = fm.get("url")
        if url:
            by_url.setdefault(normalize_url(str(url)), []).append(note.path)

    dup_in_inbox = tuple(
        (url, tuple(sorted(paths))) for url, paths in sorted(by_url.items()) if len(paths) > 1
    )

    # Already filed = a matching url on a note OUTSIDE the inbox.
    filed: set[str] = set()
    knowledge = vault / "Knowledge"
    if knowledge.is_dir():
        for other in iter_notes(knowledge, base=vault):
            if other.path.startswith(_INBOX_RELDIR + "/"):
                continue
            other_url = other.frontmatter.get("url")
            if other_url:
                filed.add(normalize_url(str(other_url)))
    dup_vs_knowledge = tuple(
        (paths[0], url) for url, paths in sorted(by_url.items()) if url in filed
    )

    return InboxReport(
        n_notes=len(notes),
        schema_ok=tuple(sorted(schema_ok)),
        schema_bad=tuple(sorted(schema_bad)),
        missing_why=tuple(sorted(missing_why)),
        dup_in_inbox=dup_in_inbox,
        dup_vs_knowledge=dup_vs_knowledge,
    )
