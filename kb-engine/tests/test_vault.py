from pathlib import Path
from kb_engine.vault import read_note, iter_notes

FIX = Path(__file__).parent / "fixtures" / "notes"


def test_read_note_parses_frontmatter_tags_and_wikilinks():
    note = read_note(FIX / "rag.md", base=FIX)
    assert note.title  # from frontmatter title
    assert "AI/RAG" in note.tags          # frontmatter tag
    assert "extra" in note.tags           # inline #extra tag, deduped, no '#'
    assert "colbert" in note.wikilinks    # [[colbert]] → "colbert"
    assert len(note.sha256) == 64


def test_iter_notes_skips_non_md_and_returns_relative_paths(tmp_path):
    (tmp_path / "a.md").write_text("---\ntitle: A\n---\nbody")
    (tmp_path / "ignore.txt").write_text("nope")
    notes = list(iter_notes(tmp_path))
    assert [n.path for n in notes] == ["a.md"]
