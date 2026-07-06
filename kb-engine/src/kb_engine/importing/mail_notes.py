"""Write Knowledge/inbox/ body-notes for fetched mail, deduped by normalized
URL (inbox-only scan + caller-supplied extras) and by Message-ID."""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import frontmatter

from kb_engine.importing.mail import (
    MailMessage,
    body_markdown,
    canonical_url,
    connect,
    fetch_labeled,
)
from kb_engine.importing.notes import next_free_path, slug_for
from kb_engine.importing.urls import normalize_url
from kb_engine.store import Store
from kb_engine.vault import iter_notes

logger = logging.getLogger(__name__)

_KNOWLEDGE = "Knowledge"
_INBOX = "inbox"

# Single source of the mail-channel defaults, surfaced by the import-mail CLI
# flags and used unattended by the pipeline.
DEFAULT_KB_LABEL = "Knowledge Base"
DEFAULT_MAIL_LIMIT = 50


@dataclass(frozen=True)
class MailImportResult:
    written: int
    skipped_existing_url: int
    skipped_existing_msgid: int
    skipped_dup_in_batch: int


def inbox_urls_and_msgids(vault: Path) -> tuple[set[str], set[str]]:
    """Walk only Knowledge/inbox/ collecting normalized URLs and message_ids."""
    inbox = Path(vault) / _KNOWLEDGE / _INBOX
    urls: set[str] = set()
    ids: set[str] = set()
    if not inbox.is_dir():
        return urls, ids
    for note in iter_notes(inbox, base=vault):
        url = note.frontmatter.get("url")
        if url:
            urls.add(normalize_url(str(url)))
        mid = note.frontmatter.get("message_id")
        if mid:
            ids.add(str(mid))
    return urls, ids


def _url_for(msg: MailMessage) -> str:
    """The dedup/link URL: the canonical permalink (normalized) if the body has
    one, else a synthetic mail:<message-id> so the note stays reachable + deduped."""
    canon = canonical_url(msg)
    if canon:
        return normalize_url(canon)
    if msg.message_id:
        return f"mail:{msg.message_id}"
    from kb_engine.topics.labeling import slugify
    return f"mail:{msg.received_at}:{slugify(msg.subject)}"  # last-resort unique-ish key


def import_mail(
    vault: Path,
    messages: list[MailMessage],
    date_added: str | None = None,
    extra_seen_urls: frozenset[str] = frozenset(),
    extra_seen_msgids: frozenset[str] = frozenset(),
) -> MailImportResult:
    vault = Path(vault)
    inbox_dir = vault / _KNOWLEDGE / _INBOX
    inbox_dir.mkdir(parents=True, exist_ok=True)
    stamp = date_added or ""

    inbox_urls, inbox_msgids = inbox_urls_and_msgids(vault)
    seen_urls: set[str] = inbox_urls | extra_seen_urls
    seen_msgids: set[str] = inbox_msgids | extra_seen_msgids
    batch_urls: set[str] = set()
    taken: set[str] = set()
    written = skip_url = skip_msgid = skip_batch = 0

    for msg in messages:
        if msg.message_id and msg.message_id in seen_msgids:
            skip_msgid += 1
            continue
        url = _url_for(msg)
        if url in seen_urls:
            skip_url += 1
            continue
        if url in batch_urls:
            skip_batch += 1
            continue
        batch_urls.add(url)
        if msg.message_id:
            seen_msgids.add(msg.message_id)
        metadata = {
            "title": msg.subject or "(untitled)",
            "url": url,
            "source": "newsletter",  # every email-channel note is a newsletter body
            "date_added": stamp,
            "summary": "",
            "status": _INBOX,
            "context": f"Email · {msg.sender}",
            "tags": [],
            "message_id": msg.message_id,
            "why": "",
            "project": "",
        }
        if msg.list_id:
            metadata["list_id"] = msg.list_id
        path = next_free_path(inbox_dir, slug_for(msg.subject, url), taken)
        path.write_text(frontmatter.dumps(frontmatter.Post(body_markdown(msg), **metadata)) + "\n")
        written += 1

    return MailImportResult(written, skip_url, skip_msgid, skip_batch)


def run_import_mail(
    vault: Path,
    store: Store,
    token: str,
    label: str = DEFAULT_KB_LABEL,
    limit: int = DEFAULT_MAIL_LIMIT,
) -> tuple[int, MailImportResult]:
    """Fetch ``<label>`` mail over JMAP, dedup against cache + inbox, write inbox notes.

    The one function both the ``import-mail`` CLI command and the maintenance
    pipeline call (DRY). ``connect``/``fetch_labeled`` may raise ``ValueError``
    (missing label / JMAP error) — callers decide how to surface it. Cache reads
    degrade to inbox-only dedup if the cache is unavailable. Returns
    ``(fetched_count, result)``.
    """
    account_id, call = connect(token)
    messages = fetch_labeled(call, account_id, label, limit)
    try:
        store.init_schema()
        extra_urls = frozenset(store.existing_urls())
        extra_msgids = frozenset(store.existing_message_ids())
    except (sqlite3.Error, OSError):
        logger.warning("cache unavailable; deduping against inbox only")
        extra_urls = extra_msgids = frozenset()
    result = import_mail(
        vault,
        messages,
        date_added=date.today().isoformat(),
        extra_seen_urls=extra_urls,
        extra_seen_msgids=extra_msgids,
    )
    return len(messages), result
