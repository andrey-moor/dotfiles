"""Write proper-schema inbox stubs for imported URLs, with dedup.

URLs are deduped against existing vault note URLs (scanning ``Knowledge/**/*.md``
frontmatter ``url``) and within the import batch, both on the normalized URL.
Surviving URLs become ``Knowledge/inbox/<slug>.md`` stubs matching the KB inbox
schema. Dates are injected by the caller (the engine core never calls ``now()``)
so the logic stays deterministic.
"""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import frontmatter

from kb_engine.importing.urls import infer_source, normalize_url
from kb_engine.topics.labeling import slugify
from kb_engine.vault import iter_notes

_KNOWLEDGE = "Knowledge"
_INBOX = "inbox"
_STUB_BODY = "## Notes\n\nPending processing."
_IMPORT_CONTEXT = "Imported from Things"
_FALLBACK_SLUG = "untitled"


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


def _slug_from_url(url: str) -> str:
    """Slug derived from the URL path, falling back to the host."""
    parts = urlsplit(url)
    return slugify(parts.path.strip("/")) or slugify(parts.hostname or "")


def _slug_for(title: str, url: str) -> str:
    """Slug from the title; fall back to the URL path, then a constant.

    A title that is itself a URL carries no naming signal (it would slugify the
    scheme/host), so it is treated as absent and the URL path is used instead.
    """
    slug = "" if title.strip().lower().startswith(("http://", "https://")) else slugify(title)
    if not slug:
        slug = _slug_from_url(url)
    return slug or _FALLBACK_SLUG


def _next_free_path(inbox_dir: Path, slug: str, taken: set[str]) -> Path:
    """Return ``<slug>.md`` if free, else ``<slug>-2.md``, ``<slug>-3.md``, …."""
    candidate = slug
    if candidate in taken or (inbox_dir / f"{candidate}.md").exists():
        suffix = 2
        while (
            f"{slug}-{suffix}" in taken
            or (inbox_dir / f"{slug}-{suffix}.md").exists()
        ):
            suffix += 1
        candidate = f"{slug}-{suffix}"
    taken.add(candidate)
    return inbox_dir / f"{candidate}.md"


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
        slug = _slug_for(title, normalized)
        path = _next_free_path(inbox_dir, slug, taken_slugs)
        _write_stub(path, title, normalized, stamp)
        written += 1

    return ImportResult(
        written=written,
        skipped_existing=skipped_existing,
        skipped_dup_in_batch=skipped_dup_in_batch,
    )
