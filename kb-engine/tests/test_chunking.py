from kb_engine.chunking import chunk_note
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
