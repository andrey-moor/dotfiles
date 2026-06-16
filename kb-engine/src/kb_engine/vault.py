import hashlib
import re
from pathlib import Path
from typing import Iterator

import frontmatter

from kb_engine.models import Note

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
    post = frontmatter.loads(raw.decode("utf-8"))
    metadata = post.metadata
    body = post.content

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
        frontmatter=dict(metadata),
        sha256=sha256,
    )


def iter_notes(root: Path) -> Iterator[Note]:
    for path in sorted(root.rglob("*.md")):
        if path.is_file():
            yield read_note(path, base=root)
