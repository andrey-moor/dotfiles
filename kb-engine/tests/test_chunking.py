import types

from kb_engine.chunking import chunk_note, embedding_text, fts_text
from kb_engine.models import Note


def _note(body: str) -> Note:
    return Note(
        path="Knowledge/x.md",
        title="X",
        body=body,
        tags=(),
        wikilinks=(),
        frontmatter={},
        sha256="0" * 64,
    )


def test_short_note_is_single_chunk_prefixed_with_title():
    chunks = chunk_note(_note("hello world"), max_tokens=512)
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0
    assert "X" in chunks[0].text  # title prepended for context


def test_long_note_splits_into_multiple_ordered_chunks():
    body = "\n\n".join(f"## Section {i}\n" + ("word " * 300) for i in range(4))
    chunks = chunk_note(_note(body), max_tokens=256)
    assert len(chunks) > 1
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_empty_body_yields_single_title_only_chunk():
    chunks = chunk_note(_note("   \n\t  "), max_tokens=512)
    assert len(chunks) == 1
    assert chunks[0].ordinal == 0
    assert chunks[0].text == "X"  # just the title, no body


# --- embedding_text / fts_text ---


def _note_with_summary(title: str, body: str, summary: str) -> Note:
    fm = types.MappingProxyType({"summary": summary} if summary is not None else {})
    return Note(
        path="Knowledge/a.md",
        title=title,
        body=body,
        tags=(),
        wikilinks=(),
        frontmatter=fm,
        sha256="x",
    )


def test_embedding_text_uses_title_and_summary():
    n = _note_with_summary("Rust Macros", "long body " * 100, "A guide to Rust macros.")
    assert embedding_text(n) == "Rust Macros\n\nA guide to Rust macros."


def test_embedding_text_falls_back_to_body_when_no_summary():
    n = _note_with_summary("T", "B" * 500, "")
    out = embedding_text(n)
    assert out.startswith("T\n\n") and len(out) <= 3 + 280 + len("T")


def test_embedding_text_title_only_when_empty_body_and_summary():
    assert embedding_text(_note_with_summary("Only Title", "", "")) == "Only Title"


def test_fts_text_is_title_plus_full_body():
    n = _note_with_summary("T", "the whole body here", "short gist")
    assert fts_text(n) == "T\n\nthe whole body here"
