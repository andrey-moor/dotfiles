import os

from kb_engine.vault import iter_notes


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_iter_notes_skips_unreadable_files_and_reports(tmp_path):
    _write(tmp_path / "Knowledge" / "ok.md", "---\ntitle: ok\n---\nbody")
    bad = tmp_path / "Knowledge" / "bad.md"
    _write(bad, "---\ntitle: bad\n---\nbody")
    os.chmod(bad, 0o000)
    failures = []
    try:
        notes = list(
            iter_notes(
                tmp_path / "Knowledge",
                base=tmp_path,
                on_error=lambda path, exc: failures.append(path.name),
            )
        )
    finally:
        os.chmod(bad, 0o644)  # so tmp_path cleanup works
    assert [n.title for n in notes] == ["ok"]
    assert failures == ["bad.md"]


def test_iter_notes_without_handler_still_skips(tmp_path):
    bad = tmp_path / "Knowledge" / "bad.md"
    _write(bad, "x")
    os.chmod(bad, 0o000)
    try:
        assert list(iter_notes(tmp_path / "Knowledge", base=tmp_path)) == []
    finally:
        os.chmod(bad, 0o644)
