import hashlib
import os
import re
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

import frontmatter

from kb_engine.models import Note


def load_post(text: str) -> frontmatter.Post:
    """Parse frontmatter into a Post, tolerating a ``content`` metadata key.

    ``frontmatter.loads`` raises when the frontmatter has a key named ``content``
    (it collides with ``Post``'s positional body arg); ``parse`` does not, so the
    Post is built from the parsed ``(metadata, body)``. Use this for any
    read-modify-write of a note that may carry backfill's ``content: unavailable``.
    """
    metadata, body = frontmatter.parse(text)
    post = frontmatter.Post(body)
    post.metadata = metadata
    return post


def write_post_atomic(path: Path, post: frontmatter.Post) -> None:
    """Write a python-frontmatter Post atomically, preserving frontmatter order.

    ``sort_keys=False`` keeps untouched fields in their original file order (new
    keys append at the end); the tmp-file + ``os.replace`` dance makes the write
    atomic, so a crash mid-write can never truncate the note. The tmp name ends
    in ``.md.tmp`` (not ``.md``) so it stays invisible to the note walk. Shared
    by every vault writer (enrichment, backfill) so the house rules — atomicity
    and key-order preservation — live in one place.
    """
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(frontmatter.dumps(post, sort_keys=False))
    os.replace(tmp, path)

# Inline tags: #Category/Sub, #tag — captured without the leading '#'.
_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z0-9][\w/-]*)")
# Wikilinks: [[target]] or [[target|alias]] — capture the target before '|'.
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def _extract_inline_tags(body: str) -> list[str]:
    return [m.group(1) for m in _TAG_RE.finditer(body)]


def _extract_wikilinks(body: str) -> list[str]:
    return [m.group(1).strip() for m in _WIKILINK_RE.finditer(body)]


def _frontmatter_tags(metadata: dict) -> list[str]:
    raw = metadata.get("tags") or []
    if isinstance(raw, str):
        return [raw]
    return [str(t) for t in raw]


def _dedupe_preserve_order(items: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def read_note(path: Path, base: Path) -> Note:
    raw = path.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    # ``frontmatter.parse`` (not ``loads``): a note whose frontmatter has a key
    # literally named ``content`` (e.g. backfill's ``content: unavailable``)
    # would crash ``loads`` — it collides with ``Post``'s positional body arg.
    metadata, body = frontmatter.parse(raw.decode("utf-8"))

    title = str(metadata.get("title") or path.stem)
    tags = _dedupe_preserve_order(_frontmatter_tags(metadata) + _extract_inline_tags(body))
    wikilinks = _dedupe_preserve_order(_extract_wikilinks(body))
    rel_path = path.relative_to(base).as_posix()

    return Note(
        path=rel_path,
        title=title,
        body=body,
        tags=tags,
        wikilinks=wikilinks,
        frontmatter=types.MappingProxyType(dict(metadata)),
        sha256=sha256,
    )


def iter_notes(
    root: Path,
    base: Path | None = None,
    exclude_dirs: tuple[str, ...] = (),
    on_error: Callable[[Path, OSError], None] | None = None,
) -> Iterator[Note]:
    """Yield notes for every ``*.md`` file under ``root``, sorted by path.

    ``base`` anchors the returned ``Note.path`` (defaults to ``root``), so a
    vault root can be passed to get vault-relative ``Knowledge/...`` paths.
    ``exclude_dirs`` skips top-level subdirectories of ``root`` by name.

    Unreadable files (iCloud eviction, permissions) are skipped, reported via
    ``on_error`` when given — a single bad file must never abort a sync.
    """
    anchor = root if base is None else base
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        if exclude_dirs and path.relative_to(root).parts[0] in exclude_dirs:
            continue
        try:
            note = read_note(path, base=anchor)
        except OSError as exc:
            if on_error is not None:
                on_error(path, exc)
            continue
        yield note


@dataclass(frozen=True)
class NoteStat:
    path: str  # vault-relative posix path
    abs_path: Path
    mtime: float
    size: int


def iter_note_stats(
    root: Path, base: Path | None = None, exclude_dirs: tuple[str, ...] = ()
) -> Iterator[NoteStat]:
    """Stat-only walk — never reads file contents (iCloud-safe)."""
    anchor = root if base is None else base
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        if exclude_dirs and path.relative_to(root).parts[0] in exclude_dirs:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        yield NoteStat(
            path=path.relative_to(anchor).as_posix(),
            abs_path=path,
            mtime=st.st_mtime,
            size=st.st_size,
        )


def evicted_note_paths(
    root: Path, base: Path | None = None, exclude_dirs: tuple[str, ...] = ()
) -> frozenset[str]:
    """Vault-relative .md paths currently evicted by iCloud (.<name>.md.icloud)."""
    anchor = root if base is None else base
    out: set[str] = set()
    for path in root.rglob("*.icloud"):
        name = path.name
        if not (name.startswith(".") and name.endswith(".icloud")):
            continue
        original = name[1 : -len(".icloud")]
        if not original.endswith(".md"):
            continue
        rel_parts = path.relative_to(root).parts
        if exclude_dirs and rel_parts[0] in exclude_dirs:
            continue
        out.add((path.parent / original).relative_to(anchor).as_posix())
    return frozenset(out)
