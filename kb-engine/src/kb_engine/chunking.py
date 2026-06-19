from semantic_text_splitter import TextSplitter

from kb_engine.models import Chunk, Note

_BODY_FALLBACK_CHARS = 280


def _summary_of(note: Note) -> str:
    value = note.frontmatter.get("summary") if note.frontmatter else None
    return str(value).strip() if value else ""


def embedding_text(note: Note) -> str:
    """Text embedded into the note's semantic vector: title + summary.

    Falls back to the first ``_BODY_FALLBACK_CHARS`` of the body when there is no
    summary, and to the title alone when both are empty.
    """
    summary = _summary_of(note)
    if not summary:
        summary = note.body.strip()[:_BODY_FALLBACK_CHARS]
    title = note.title.strip()
    return f"{title}\n\n{summary}" if summary else title


def fts_text(note: Note) -> str:
    """Full text indexed for keyword (FTS) recall: title + full body."""
    body = note.body.strip()
    title = note.title.strip()
    return f"{title}\n\n{body}" if body else title


def chunk_note(note: Note, max_tokens: int = 512) -> list[Chunk]:
    """Split a note into ordered chunks for embedding.

    The title is prepended for retrieval context. An empty/whitespace body
    yields a single chunk of just the title.
    """
    body = note.body.strip()
    if not body:
        return [Chunk(note_path=note.path, ordinal=0, text=note.title)]

    text = f"{note.title}\n\n{body}"
    splitter = TextSplitter(max_tokens)
    pieces = splitter.chunks(text)
    return [
        Chunk(note_path=note.path, ordinal=i, text=piece)
        for i, piece in enumerate(pieces)
    ]
