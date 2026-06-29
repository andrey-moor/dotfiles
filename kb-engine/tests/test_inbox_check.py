from pathlib import Path

import frontmatter

from kb_engine.inbox_check import check_inbox, InboxReport


def _write(vault: Path, relpath: str, **fm) -> None:
    p = vault / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(frontmatter.dumps(frontmatter.Post("## Notes\n\nPending processing.", **fm)) + "\n")


def _good_fm(url="https://example.com/a", **over):
    fm = dict(title="A", url=url, source="article", date_added="2026-06-19",
              summary="", status="inbox", context="Web Clipper", tags=[],
              why="for the game project", project="retro-platformer")
    fm.update(over)
    return fm


def test_valid_clip_passes_and_has_why(tmp_path):
    _write(tmp_path, "Knowledge/inbox/a.md", **_good_fm())
    report = check_inbox(tmp_path)
    assert isinstance(report, InboxReport)
    assert report.n_notes == 1
    assert report.schema_ok == ("Knowledge/inbox/a.md",)
    assert report.schema_bad == ()
    assert report.missing_why == ()


def test_missing_required_key_is_schema_bad(tmp_path):
    fm = _good_fm(); del fm["source"]
    _write(tmp_path, "Knowledge/inbox/b.md", **fm)
    report = check_inbox(tmp_path)
    assert report.schema_ok == ()
    assert report.schema_bad == (("Knowledge/inbox/b.md", ("source",)),)


def test_missing_why_is_warned_not_failed(tmp_path):
    fm = _good_fm(); del fm["why"]
    _write(tmp_path, "Knowledge/inbox/c.md", **fm)
    report = check_inbox(tmp_path)
    assert report.schema_ok == ("Knowledge/inbox/c.md",)
    assert report.missing_why == ("Knowledge/inbox/c.md",)


def test_duplicate_urls_within_inbox_are_reported(tmp_path):
    _write(tmp_path, "Knowledge/inbox/d.md", **_good_fm(url="https://example.com/x"))
    _write(tmp_path, "Knowledge/inbox/e.md", **_good_fm(url="https://example.com/x/?utm_source=t"))
    report = check_inbox(tmp_path)
    assert report.dup_in_inbox == (
        ("https://example.com/x", ("Knowledge/inbox/d.md", "Knowledge/inbox/e.md")),
    )


def test_inbox_url_already_filed_is_reported_when_check_filed(tmp_path):
    _write(tmp_path, "Knowledge/articles/filed.md", **_good_fm(url="https://example.com/y", status="reference"))
    _write(tmp_path, "Knowledge/inbox/f.md", **_good_fm(url="https://example.com/y"))
    report = check_inbox(tmp_path, check_filed=True)
    assert report.dup_vs_knowledge == (("Knowledge/inbox/f.md", "https://example.com/y"),)


def test_filed_check_is_off_by_default(tmp_path):
    # The Knowledge-wide scan is slow on a large vault, so it must be opt-in:
    # without check_filed the same filed dup is NOT reported.
    _write(tmp_path, "Knowledge/articles/filed.md", **_good_fm(url="https://example.com/y", status="reference"))
    _write(tmp_path, "Knowledge/inbox/f.md", **_good_fm(url="https://example.com/y"))
    report = check_inbox(tmp_path)  # default: check_filed=False
    assert report.dup_vs_knowledge == ()
