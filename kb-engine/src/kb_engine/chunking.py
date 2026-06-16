from semantic_text_splitter import TextSplitter

from kb_engine.models import Chunk, Note


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
