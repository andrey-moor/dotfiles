"""Backfill full article text for thin captures.

A stub note (a title + url + a short body) has little for search or enrichment
to work from. This step fetches the linked page once and appends the extracted
Markdown under a ``## Content`` heading, so a clip becomes real content.

A candidate is a note whose stripped body is short (< 500 chars), has a ``url``,
whose ``source`` is fetchable (``article``/``github``/``newsletter``), that is
not already marked ``content: unavailable``, that has not already failed three
times (``content_attempts``), and whose body carries no ``## Content`` section
yet (a short extraction must not re-qualify and re-append). Synthesized
``wiki/`` articles are never touched. Inbox notes CAN qualify — they are real
captures.

Fetching follows redirects with a 30s timeout and a polite per-domain >=2s
spacing (a monotonic-clock dict). On success the extracted Markdown, capped at
4000 words, is appended (with a truncation marker linking the source when
capped). On failure ``content_attempts`` is incremented and, on the third
failure, ``content: unavailable`` is set so the note stops qualifying. Every
write is atomic and order-preserving, and per-item errors are collected (never
raised) so one bad url never aborts the batch. Each run is recorded in ``runs``.
"""

import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from kb_engine.config import Config
from kb_engine.extract import html_to_markdown
from kb_engine.models import Note
from kb_engine.store import Store
from kb_engine.vault import iter_notes, load_post, write_post_atomic

DEFAULT_LIMIT = 50

_BODY_MAX_CHARS = 500  # a note with a shorter stripped body is a stub
_MAX_ATTEMPTS = 3  # give up (mark unavailable) after this many failures
_WORD_CAP = 4000  # cap appended content at this many words
_FETCH_TIMEOUT_S = 30
_DOMAIN_SPACING_S = 2.0  # minimum seconds between requests to one domain
_USER_AGENT = "kb-engine/0.1"
_FETCHABLE_SOURCES = frozenset({"article", "github", "newsletter"})

_CONTENT_HEADER = "\n\n## Content\n\n"
_CONTENT_HEADING = "## Content"  # already backfilled — short extractions must not re-qualify
_TRUNCATION_MARKER = "\n\n…truncated — full text at {url}\n"

_WORD_RE = re.compile(r"\S+")

# Per-item outcome sentinels (mutually exclusive over the processed batch).
_FETCHED = "fetched"
_UNAVAILABLE = "unavailable"
_FAILED = "failed"


@dataclass(frozen=True)
class BackfillStats:
    fetched: int
    unavailable: int
    skipped: int
    failures: tuple[str, ...]


def _attempts(metadata: object) -> int:
    """Parse ``content_attempts`` (int, default 0) defensively."""
    try:
        return int(metadata.get("content_attempts") or 0)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        return 0


def is_backfill_candidate(note: Note) -> bool:
    """A thin, fetchable, not-yet-exhausted capture (see module docstring).

    Shared predicate: enrich imports this as its defer-gate (a note backfill
    will still fetch must not be summarized yet), so the ruleset lives in
    exactly one place.
    """
    if "wiki" in Path(note.path).parts:
        return False
    fm = note.frontmatter
    if not str(fm.get("url") or "").strip():
        return False
    if str(fm.get("source") or "") not in _FETCHABLE_SOURCES:
        return False
    if str(fm.get("content") or "").strip().lower() == "unavailable":
        return False
    if _attempts(fm) >= _MAX_ATTEMPTS:
        return False
    if _CONTENT_HEADING in note.body:
        return False  # already backfilled — short extractions must not re-qualify
    return len(note.body.strip()) < _BODY_MAX_CHARS


def backfill_candidates(cfg: Config) -> list[str]:
    """Vault-relative paths of thin captures eligible for content backfill."""
    return [
        note.path
        for note in iter_notes(cfg.knowledge_dir, base=cfg.vault_path, exclude_dirs=())
        if is_backfill_candidate(note)
    ]


def _cap_words(text: str, cap: int) -> tuple[str, bool]:
    """Truncate ``text`` to at most ``cap`` words. Returns (text, was_capped).

    Counts whitespace-delimited word runs and slices the ORIGINAL text at the
    end of the cap-th word, so formatting (newlines, markdown) is preserved up
    to the cut rather than collapsed.
    """
    matches = list(_WORD_RE.finditer(text))
    if len(matches) <= cap:
        return text, False
    return text[: matches[cap - 1].end()], True


def _new_client() -> httpx.Client:
    return httpx.Client(
        follow_redirects=True,
        timeout=_FETCH_TIMEOUT_S,
        headers={"User-Agent": _USER_AGENT},
    )


def _respect_domain_spacing(url: str, last_seen: dict[str, float]) -> None:
    """Sleep so requests to a single domain are spaced >= ``_DOMAIN_SPACING_S``."""
    domain = httpx.URL(url).host or ""
    prev = last_seen.get(domain)
    if prev is not None:
        elapsed = time.monotonic() - prev
        if elapsed < _DOMAIN_SPACING_S:
            time.sleep(_DOMAIN_SPACING_S - elapsed)
    last_seen[domain] = time.monotonic()


def _fetch(client: httpx.Client, url: str, last_seen: dict[str, float]) -> str:
    """Fetch ``url`` and return its extracted Markdown, or raise on any problem."""
    _respect_domain_spacing(url, last_seen)
    resp = client.get(url)
    resp.raise_for_status()
    markdown = html_to_markdown(resp.text)
    if not markdown:
        raise ValueError(f"no content extracted: {url}")
    return markdown


def _append_content(abs_path: Path, markdown: str, url: str) -> None:
    """Append a capped ``## Content`` section to the note body (atomic write)."""
    capped, was_capped = _cap_words(markdown, _WORD_CAP)
    addition = _CONTENT_HEADER + capped
    if was_capped:
        addition += _TRUNCATION_MARKER.format(url=url)
    post = load_post(abs_path.read_text())
    post.content = post.content + addition
    write_post_atomic(abs_path, post)


def _record_failure(abs_path: Path) -> str:
    """Increment ``content_attempts``; mark unavailable on the 3rd. Returns outcome.

    Returns ``_UNAVAILABLE`` when this failure crosses the attempt threshold,
    ``_FAILED`` otherwise (a retryable transient failure, or a note we could not
    even update).
    """
    try:
        post = load_post(abs_path.read_text())
        attempts = _attempts(post.metadata) + 1
        post["content_attempts"] = attempts
        terminal = attempts >= _MAX_ATTEMPTS
        if terminal:
            post["content"] = "unavailable"
        write_post_atomic(abs_path, post)
        return _UNAVAILABLE if terminal else _FAILED
    except Exception:  # noqa: BLE001 — couldn't record the attempt; retry next run
        return _FAILED


def _process(cfg: Config, client: httpx.Client, rel_path: str, last_seen: dict[str, float]) -> str:
    """Fetch + append content for one note; never raises (returns an outcome)."""
    abs_path = cfg.vault_path / rel_path
    try:
        post = load_post(abs_path.read_text())
        url = str(post["url"])
        markdown = _fetch(client, url, last_seen)
    except Exception:  # noqa: BLE001 — fetch/read/extract failed; record an attempt
        return _record_failure(abs_path)
    try:
        _append_content(abs_path, markdown, url)
    except Exception:  # noqa: BLE001 — write failed; retryable
        return _FAILED
    return _FETCHED


def backfill_content(
    cfg: Config,
    store: Store,
    limit: int = DEFAULT_LIMIT,
    client: httpx.Client | None = None,
) -> BackfillStats:
    """Fetch + append full content for up to ``limit`` thin captures.

    Candidates beyond ``limit`` are deferred (counted as ``skipped``). Each item
    is processed under its own try/except so one bad url never aborts the batch;
    the run is recorded in ``runs`` regardless. An ``httpx.Client`` may be
    injected (tests); otherwise one is created and closed here.
    """
    store.init_schema()
    run_id = store.start_run("backfill")

    candidates = backfill_candidates(cfg)
    batch = candidates[:limit]
    skipped = len(candidates) - len(batch)
    fetched = unavailable = 0
    failures: list[str] = []

    owns_client = client is None
    if client is None:
        client = _new_client()
    last_seen: dict[str, float] = {}  # domain -> monotonic time of last request
    try:
        for rel_path in batch:
            outcome = _process(cfg, client, rel_path, last_seen)
            if outcome == _FETCHED:
                fetched += 1
            elif outcome == _UNAVAILABLE:
                unavailable += 1
            else:
                failures.append(rel_path)
    finally:
        if owns_client:
            client.close()
        store.finish_run(
            run_id,
            ok=True,
            counts={"fetched": fetched, "unavailable": unavailable, "skipped": skipped},
            errors=list(failures),
        )

    return BackfillStats(fetched, unavailable, skipped, tuple(failures))
