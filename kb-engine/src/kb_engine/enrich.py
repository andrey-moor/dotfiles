"""Auto-enrichment: draft summaries/whys and repair garbled titles.

Walks ``Knowledge/`` (inbox INCLUDED — new clips are the point) and, for notes
with an empty ``summary``, drafts a factual summary, a "why saved" line (only if
missing), and repairs a garbled machine-slug title (only if it looks like one).
Notes that backfill will still fetch (thin body + fetchable url — the shared
``is_backfill_candidate`` predicate) are deferred, not summarized: the T8 live
run showed the LLM answers title-only stubs with polite refusals, which would
be written back as permanent "summaries". A refusal-marker guard backstops the
gate. Every write carries ``provenance: auto`` so a later run — and a human — can tell
what the machine touched: a non-empty ``summary``/``why``/``title`` that has no
auto mark is human and is NEVER overwritten. Writes are atomic (tmp file +
``os.replace``) and order-preserving (``sort_keys=False``), so untouched
frontmatter keeps its file order and a crash can never truncate a note.
Per-note LLM/HTTP/write errors — and unreadable files — are collected in
``failures``, never raised, so one bad note never aborts the run.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from kb_engine.backfill import is_backfill_candidate
from kb_engine.config import Config
from kb_engine.llm import LLM
from kb_engine.models import Note
from kb_engine.vault import iter_notes, load_post, write_post_atomic

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

# Cheap insurance behind the defer-gate: a draft that reads as an LLM refusal
# ("I don't have any content to summarize…") must never be written as a
# summary — it would block re-enrichment forever. Matched case-insensitively.
_REFUSAL_MARKERS = (
    "i don't have",
    "i do not have",
    "i don't see any",  # 2 of the 9 live T8 refusals used this phrasing
    "please share",
    "please provide",
    "no actual content",
    "unable to summarize",
)


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


def _is_refusal(summary: str) -> bool:
    """True when a draft reads as an LLM refusal rather than a summary."""
    text = summary.lower().replace("’", "'")  # live refusals use "don’t"
    return any(marker in text for marker in _REFUSAL_MARKERS)


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
    are skipped (never selected). Backfill candidates (thin fetchable stubs)
    are deferred — counted ``skipped`` — until backfill gives them content;
    once backfill exhausts (``content: unavailable``) they ARE enriched from
    title + stub, the best available. An empty-body note whose title is not
    garbage has nothing to work from and is counted as ``skipped``. ``limit``
    bounds the number of notes that reach the LLM in one run. Per-note
    LLM/HTTP/write failures — a blank or refusal-shaped summary draft counts
    as one — and unreadable files are collected in ``failures`` and never
    abort the walk.
    """
    summarized = whys = titles = skipped = 0
    failures: list[str] = []
    llm_calls = 0

    def _unreadable(path: Path, _exc: OSError) -> None:
        failures.append(path.relative_to(cfg.vault_path).as_posix())

    for note in iter_notes(
        cfg.knowledge_dir, base=cfg.vault_path, exclude_dirs=(), on_error=_unreadable
    ):
        if not _needs(note):
            continue
        if is_backfill_candidate(note):
            # Content-less fetchable stubs defer to backfill; enrich picks
            # them up once content exists. (T8: summarizing title-only stubs
            # produced LLM refusals written back as permanent summaries.)
            skipped += 1
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
            if not summary or _is_refusal(summary):
                # A blank draft would re-qualify forever; a refusal draft would
                # be baked in as a permanent "summary". Write nothing, record.
                failures.append(note.path)
                continue
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
            _write_note(cfg.vault_path / note.path, summary, why, new_title)
        except Exception:  # noqa: BLE001 — a bad note is recorded, never fatal
            failures.append(note.path)
            continue

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
    """Round-trip via python-frontmatter: body byte-unchanged, key order kept.

    Uses the shared ``load_post`` (tolerates a ``content`` frontmatter key —
    backfill's ``content: unavailable`` would crash ``frontmatter.loads``) and
    ``write_post_atomic`` (tmp-file + ``os.replace``, ``sort_keys=False``) so
    untouched fields keep their file order and a crash mid-write can never
    truncate the note.
    """
    post = load_post(path.read_text())
    post["summary"] = summary
    if why is not None:
        post["why"] = why
    if new_title is not None:
        post["title"] = new_title
    post["provenance"] = "auto"
    write_post_atomic(path, post)
