"""Write Knowledge/inbox/ body-notes for fetched mail, deduped by normalized
URL (vault-wide) and by Message-ID (email notes carry a message_id field)."""

from dataclasses import dataclass
from pathlib import Path

import frontmatter

from kb_engine.importing.mail import MailMessage, body_markdown, canonical_url
from kb_engine.importing.notes import next_free_path, slug_for
from kb_engine.importing.urls import normalize_url
from kb_engine.vault import iter_notes

_KNOWLEDGE = "Knowledge"
_INBOX = "inbox"


@dataclass(frozen=True)
class MailImportResult:
    written: int
    skipped_existing_url: int
    skipped_existing_msgid: int
    skipped_dup_in_batch: int


def existing_message_ids(vault: Path) -> set[str]:
    knowledge = Path(vault) / _KNOWLEDGE
    if not knowledge.is_dir():
        return set()
    ids: set[str] = set()
    for note in iter_notes(knowledge, base=vault):
        mid = note.frontmatter.get("message_id")
        if mid:
            ids.add(str(mid))
    return ids


def existing_urls_and_msgids(vault: Path) -> tuple[set[str], set[str]]:
    """One walk of Knowledge/ collecting both normalized urls and message_ids."""
    knowledge = Path(vault) / _KNOWLEDGE
    urls: set[str] = set()
    ids: set[str] = set()
    if not knowledge.is_dir():
        return urls, ids
    for note in iter_notes(knowledge, base=vault):
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


def import_mail(vault: Path, messages: list[MailMessage], date_added: str | None = None) -> MailImportResult:
    vault = Path(vault)
    inbox_dir = vault / _KNOWLEDGE / _INBOX
    inbox_dir.mkdir(parents=True, exist_ok=True)
    stamp = date_added or ""

    seen_urls, seen_msgids = existing_urls_and_msgids(vault)
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
