from kb_engine.models import Note

_BODY_FALLBACK_CHARS = 280


def _frontmatter_str(note: Note, key: str) -> str:
    """Frontmatter value as a stripped string; non-str (e.g. a YAML list) → ""."""
    value = note.frontmatter.get(key) if note.frontmatter else None
    if not isinstance(value, str):
        return ""
    return value.strip()


def summary_of(note: Note) -> str:
    return _frontmatter_str(note, "summary")


def embedding_text(note: Note) -> str:
    """Text embedded into the note's semantic vector: title + summary + why.

    Falls back to the first ``_BODY_FALLBACK_CHARS`` of the body when there is no
    summary, and to the title alone when both are empty. A non-empty ``why``
    (why-this-was-captured) is appended so capture intent is retrievable.
    """
    summary = summary_of(note)
    if not summary:
        summary = note.body.strip()[:_BODY_FALLBACK_CHARS]
    title = note.title.strip()
    text = f"{title}\n\n{summary}" if summary else title
    why = _frontmatter_str(note, "why")
    if why:
        text = f"{text}\n\n{why}"
    return text


def fts_text(note: Note) -> str:
    """Full text indexed for keyword (FTS) recall: title + full body."""
    body = note.body.strip()
    title = note.title.strip()
    return f"{title}\n\n{body}" if body else title
