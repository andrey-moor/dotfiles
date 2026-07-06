"""Auto-enrichment: draft summaries/whys and repair garbled titles.

Walks ``Knowledge/`` (inbox INCLUDED — new clips are the point) and, for notes
with an empty ``summary``, drafts a factual summary, a "why saved" line (only if
missing), and repairs a garbled machine-slug title (only if it looks like one).
Every write carries ``provenance: auto`` so a later run — and a human — can tell
what the machine touched: a non-empty ``summary``/``why``/``title`` that has no
auto mark is human and is NEVER overwritten. Per-note LLM/HTTP errors are
collected, never raised, so one bad note never aborts the run.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from kb_engine.config import Config
from kb_engine.llm import LLM
from kb_engine.models import Note
from kb_engine.vault import iter_notes

DEFAULT_LIMIT = 50
_BODY_CHARS = 6000  # cap the content handed to the LLM

SUMMARY_SYSTEM = (
    "You write 2-3 sentence factual summaries of saved web content for a personal "
    "knowledge base. Plain prose. No markdown, no preamble, no 'This article...'."
)
WHY_SYSTEM = (
    "Given a saved item, propose ONE short line (max 15 words) guessing why the owner "
    "saved it, grounded in the content and capture channel. Return only the line."
)
TITLE_SYSTEM = (
    "Repair this garbled machine slug into a clean human-readable title (max 80 "
    "chars). Return only the title."
)

# A slug-garbage title is a machine artifact, not human text: "foo-bar-baz"
# (>=3 hyphen-joined tokens), a "-status-<n>" tail, or an untitled placeholder.
_GARBAGE_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+){2,}")
_STATUS_SLUG = re.compile(r"-status-\d+")
_UNTITLED = {"untitled", "(untitled)"}


@dataclass(frozen=True)
class EnrichStats:
    summarized: int
    whys: int
    titles: int
    skipped: int
    failures: tuple[str, ...]


def _is_empty(value: object) -> bool:
    """True when a frontmatter field is missing or blank."""
    return value is None or not str(value).strip()


def _is_garbage_title(title: str) -> bool:
    """True when a title looks machine-generated (safe to repair)."""
    t = title.strip()
    return bool(
        re.fullmatch(_GARBAGE_SLUG, t)
        or re.search(_STATUS_SLUG, t)
        or t.lower() in _UNTITLED
    )


def _needs(note: Note) -> bool:
    """Candidate for enrichment: its ``summary`` frontmatter is empty/missing."""
    return _is_empty(note.frontmatter.get("summary"))


def _draft(llm: LLM, system: str, user: str) -> str:
    return llm.complete(system, user).strip()


def _user_content(note: Note) -> str:
    source = note.frontmatter.get("source") or ""
    context = note.frontmatter.get("context") or ""
    return (
        f"Title: {note.title}\n"
        f"Channel: {source} · {context}\n"
        f"Content:\n{note.body[:_BODY_CHARS]}"
    )


def enrich_notes(cfg: Config, llm: LLM, limit: int = DEFAULT_LIMIT) -> EnrichStats:
    """Draft summaries/whys/titles for empty-summary notes under ``Knowledge/``.

    Inbox is INCLUDED (``exclude_dirs=()``). Notes with a non-empty ``summary``
    are skipped (never selected); an empty-body note whose title is not garbage
    has nothing to work from and is counted as ``skipped``. ``limit`` bounds the
    number of notes that reach the LLM in one run. Per-note LLM/HTTP failures are
    collected in ``failures`` and never abort the walk; unreadable files are
    skipped the same way.
    """
    summarized = whys = titles = skipped = 0
    failures: list[str] = []
    llm_calls = 0

    for note in iter_notes(
        cfg.knowledge_dir, base=cfg.vault_path, exclude_dirs=(), on_error=_ignore_error
    ):
        if not _needs(note):
            continue
        if not note.body.strip() and not _is_garbage_title(note.title):
            skipped += 1  # nothing to summarize, title already clean
            continue
        if llm_calls >= limit:
            break
        llm_calls += 1

        try:
            user = _user_content(note)
            summary = _draft(llm, SUMMARY_SYSTEM, user)
            why = (
                _draft(llm, WHY_SYSTEM, user)
                if _is_empty(note.frontmatter.get("why"))
                else None
            )
            new_title = (
                _draft(llm, TITLE_SYSTEM, user)
                if _is_garbage_title(note.title)
                else None
            )
        except Exception:  # noqa: BLE001 — a bad note is recorded, never fatal
            failures.append(note.path)
            continue

        _write_note(cfg.vault_path / note.path, summary, why, new_title)
        summarized += 1
        whys += 1 if why is not None else 0
        titles += 1 if new_title is not None else 0

    return EnrichStats(
        summarized=summarized,
        whys=whys,
        titles=titles,
        skipped=skipped,
        failures=tuple(failures),
    )


def _write_note(
    path: Path, summary: str, why: str | None, new_title: str | None
) -> None:
    """Round-trip the note via python-frontmatter, body byte-unchanged."""
    post = frontmatter.loads(path.read_text())
    post["summary"] = summary
    if why is not None:
        post["why"] = why
    if new_title is not None:
        post["title"] = new_title
    post["provenance"] = "auto"
    path.write_text(frontmatter.dumps(post))


def _ignore_error(_path: Path, _exc: OSError) -> None:
    """Unreadable files (iCloud eviction, permissions) never abort enrichment."""
