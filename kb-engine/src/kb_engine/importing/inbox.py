"""Write proper-schema inbox stubs for imported URLs, with dedup.

URLs are deduped against existing vault note URLs (scanning ``Knowledge/**/*.md``
frontmatter ``url``) and within the import batch, both on the normalized URL.
Surviving URLs become ``Knowledge/inbox/<slug>.md`` stubs matching the KB inbox
schema. Dates are injected by the caller (the engine core never calls ``now()``)
so the logic stays deterministic.
"""

from dataclasses import dataclass
from pathlib import Path

import frontmatter

from kb_engine.importing.notes import next_free_path, slug_for
from kb_engine.importing.urls import infer_source, normalize_url
from kb_engine.vault import iter_notes

_KNOWLEDGE = "Knowledge"
_INBOX = "inbox"
_STUB_BODY = "## Notes\n\nPending processing."
_IMPORT_CONTEXT = "Imported from Things"


@dataclass(frozen=True)
class ImportResult:
    written: int
    skipped_existing: int
    skipped_dup_in_batch: int


def existing_urls(vault: Path) -> set[str]:
    """Return the set of normalized ``url`` frontmatter values across the vault."""
    knowledge = Path(vault) / _KNOWLEDGE
    if not knowledge.is_dir():
        return set()
    urls: set[str] = set()
    for note in iter_notes(knowledge, base=vault):
        url = note.frontmatter.get("url")
        if url:
            urls.add(normalize_url(str(url)))
    return urls


def _write_stub(path: Path, title: str, url: str, date_added: str) -> None:
    metadata = {
        "title": title,
        "url": url,
        "source": infer_source(url),
        "date_added": date_added,
        "summary": "",
        "status": _INBOX,
        "context": _IMPORT_CONTEXT,
        "tags": [],
    }
    post = frontmatter.Post(_STUB_BODY, **metadata)
    path.write_text(frontmatter.dumps(post) + "\n")


def import_urls(
    vault: Path,
    items: list[tuple[str, str]],
    date_added: str | None = None,
) -> ImportResult:
    """Write inbox stubs for ``(url, title)`` items, deduping along the way.

    Each URL is normalized; it is skipped if already present in the vault
    (``skipped_existing``) or already seen earlier in this batch
    (``skipped_dup_in_batch``). ``date_added`` is stamped verbatim (blank if
    ``None``) — the caller is responsible for any "today" semantics.
    """
    vault = Path(vault)
    inbox_dir = vault / _KNOWLEDGE / _INBOX
    inbox_dir.mkdir(parents=True, exist_ok=True)
    stamp = date_added or ""

    seen_existing = existing_urls(vault)
    seen_batch: set[str] = set()
    taken_slugs: set[str] = set()
    written = skipped_existing = skipped_dup_in_batch = 0

    for url, title in items:
        normalized = normalize_url(url)
        if normalized in seen_existing:
            skipped_existing += 1
            continue
        if normalized in seen_batch:
            skipped_dup_in_batch += 1
            continue
        seen_batch.add(normalized)
        slug = slug_for(title, normalized)
        path = next_free_path(inbox_dir, slug, taken_slugs)
        _write_stub(path, title, normalized, stamp)
        written += 1

    return ImportResult(
        written=written,
        skipped_existing=skipped_existing,
        skipped_dup_in_batch=skipped_dup_in_batch,
    )
