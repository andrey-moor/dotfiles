"""Shared note-writing primitives used by every capture channel (DRY)."""

from pathlib import Path

from kb_engine.topics.labeling import slugify

INBOX_RELDIR = "Knowledge/inbox"
_FALLBACK_SLUG = "untitled"


def slug_for(title: str, url: str) -> str:
    """Slug from the title; fall back to the URL path, then a constant.

    A title that is itself a URL carries no naming signal, so it is treated as
    absent and the URL path is used instead.
    """
    from urllib.parse import urlsplit

    if title.strip().lower().startswith(("http://", "https://")):
        slug = ""
    else:
        slug = slugify(title)
    if not slug:
        parts = urlsplit(url)
        slug = slugify(parts.path.strip("/")) or slugify(parts.hostname or "")
    return slug or _FALLBACK_SLUG


def next_free_path(inbox_dir: Path, slug: str, taken: set[str]) -> Path:
    """Return ``<slug>.md`` if free, else ``<slug>-2.md``, ``<slug>-3.md``, …."""
    candidate = slug
    if candidate in taken or (inbox_dir / f"{candidate}.md").exists():
        suffix = 2
        while f"{slug}-{suffix}" in taken or (inbox_dir / f"{slug}-{suffix}.md").exists():
            suffix += 1
        candidate = f"{slug}-{suffix}"
    taken.add(candidate)
    return inbox_dir / f"{candidate}.md"
