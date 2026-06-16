from dataclasses import dataclass


@dataclass(frozen=True)
class Note:
    path: str  # vault-relative path, e.g. "Knowledge/foo.md"
    title: str
    body: str
    tags: tuple[str, ...]
    wikilinks: tuple[str, ...]
    frontmatter: dict
    sha256: str


@dataclass(frozen=True)
class Chunk:
    note_path: str
    ordinal: int
    text: str


@dataclass(frozen=True)
class SearchHit:
    note_path: str
    title: str
    score: float
    snippet: str
