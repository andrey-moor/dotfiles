import os

import frontmatter

from kb_engine.config import Config
from kb_engine.enrich import enrich_notes
from kb_engine.llm import FakeLLM


def _vault(tmp_path):
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    return Config(vault_path=tmp_path, db_path=tmp_path / "kb.db")


def _write(cfg, rel, text):
    p = cfg.vault_path / rel
    p.write_text(text)
    return p


def test_enriches_empty_summary_and_marks_provenance(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(cfg, "Knowledge/inbox/some-slug-thing-here.md",
               "---\ntitle: some-slug-thing-here\nsummary: ''\nwhy: ''\nsource: article\n---\nlong body text")
    stats = enrich_notes(cfg, FakeLLM(reply="drafted."))
    assert stats.summarized == 1 and stats.whys == 1 and stats.titles == 1
    post = frontmatter.loads(p.read_text())
    assert post["summary"] == "drafted."
    assert post["why"] == "drafted."
    assert post["title"] == "drafted."
    assert post["provenance"] == "auto"
    assert post.content == "long body text"  # body byte-exact, not just stripped
    # Pin frontmatter.dumps' convention: blank line after the closing delimiter,
    # body verbatim, no appended trailing newline.
    assert p.read_text().endswith("\n---\n\nlong body text")


def test_never_overwrites_human_text(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(cfg, "Knowledge/filed.md",
               "---\ntitle: A Human Title\nsummary: human summary\nwhy: human why\n---\nbody")
    llm = FakeLLM()
    stats = enrich_notes(cfg, llm)
    assert stats.summarized == 0 and llm.calls == []
    post = frontmatter.loads(p.read_text())
    assert post["summary"] == "human summary" and "provenance" not in post.metadata


def test_partial_enrich_keeps_existing_why(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(cfg, "Knowledge/n.md",
               "---\ntitle: Clean Title\nsummary: ''\nwhy: my own reason\n---\nbody")
    stats = enrich_notes(cfg, FakeLLM(reply="s."))
    assert stats.summarized == 1 and stats.whys == 0 and stats.titles == 0
    post = frontmatter.loads(p.read_text())
    assert post["why"] == "my own reason" and post["summary"] == "s."


def test_limit_bounds_llm_notes(tmp_path):
    cfg = _vault(tmp_path)
    for i in range(3):
        _write(cfg, f"Knowledge/n{i}.md", f"---\ntitle: T{i}\nsummary: ''\n---\nb{i}")
    stats = enrich_notes(cfg, FakeLLM(reply="s."), limit=2)
    assert stats.summarized == 2


def test_llm_failure_collected_not_raised(tmp_path):
    cfg = _vault(tmp_path)
    _write(cfg, "Knowledge/bad.md", "---\ntitle: T\nsummary: ''\n---\nbody")

    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("api down")

    stats = enrich_notes(cfg, Boom())
    assert stats.failures == ("Knowledge/bad.md",) and stats.summarized == 0


def _frontmatter_keys(raw):
    """Top-level frontmatter key names, in file order, parsed from raw text."""
    block = raw.split("---\n")[1]
    return [
        line.split(":", 1)[0]
        for line in block.splitlines()
        if line and not line.startswith((" ", "-"))
    ]


def test_preserves_untouched_fields_and_key_order(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(
        cfg,
        "Knowledge/inbox/realistic.md",
        "---\n"
        "title: Kubernetes Operators, Explained\n"
        "url: https://example.com/k8s-operators\n"
        "source: newsletter\n"
        "date_added: '2026-07-01'\n"
        "tags:\n"
        "- kubernetes\n"
        "- infra\n"
        "message_id: <20260701.abc@lists.example.com>\n"
        "status: inbox\n"
        "summary: ''\n"
        "why: ''\n"
        "---\n"
        "body text here",
    )
    stats = enrich_notes(cfg, FakeLLM(reply="drafted."))
    assert stats.summarized == 1 and stats.whys == 1 and stats.titles == 0

    raw = p.read_text()
    # Untouched keys keep their original file order; provenance appends last.
    assert _frontmatter_keys(raw) == [
        "title", "url", "source", "date_added", "tags",
        "message_id", "status", "summary", "why", "provenance",
    ]
    post = frontmatter.loads(raw)
    assert post["title"] == "Kubernetes Operators, Explained"  # clean title untouched
    assert post["url"] == "https://example.com/k8s-operators"
    assert post["source"] == "newsletter"
    assert post["date_added"] == "2026-07-01"
    assert post["tags"] == ["kubernetes", "infra"]
    assert post["message_id"] == "<20260701.abc@lists.example.com>"
    assert post["status"] == "inbox"
    assert post["summary"] == "drafted." and post["why"] == "drafted."
    assert post["provenance"] == "auto"
    assert post.content == "body text here"


def test_rerun_is_noop_zero_calls_bytes_identical(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(cfg, "Knowledge/inbox/garbled-note-slug.md",
               "---\ntitle: garbled-note-slug\nsummary: ''\nwhy: ''\n---\nreal body")
    first_stats = enrich_notes(cfg, FakeLLM(reply="drafted."))
    assert first_stats.summarized == 1
    first_bytes = p.read_bytes()

    llm2 = FakeLLM(reply="SHOULD-NOT-APPEAR")
    stats2 = enrich_notes(cfg, llm2)
    assert stats2.summarized == 0 and llm2.calls == []
    assert p.read_bytes() == first_bytes


def test_empty_body_clean_title_counted_skipped_no_llm_call(tmp_path):
    cfg = _vault(tmp_path)
    original = "---\ntitle: A Clean Human Title\nsummary: ''\n---\n"
    p = _write(cfg, "Knowledge/empty.md", original)
    llm = FakeLLM(reply="x.")
    stats = enrich_notes(cfg, llm)
    assert stats.skipped == 1 and stats.summarized == 0 and llm.calls == []
    assert p.read_text() == original  # never written


def test_blank_summary_draft_not_written_counted_failed(tmp_path):
    cfg = _vault(tmp_path)
    original = "---\ntitle: T\nsummary: ''\n---\nbody"
    p = _write(cfg, "Knowledge/blank.md", original)
    stats = enrich_notes(cfg, FakeLLM(reply="   "))
    assert stats.summarized == 0
    assert stats.failures == ("Knowledge/blank.md",)
    assert p.read_text() == original  # no empty-summary + auto stamp written


def test_unreadable_note_collected_in_failures(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(cfg, "Knowledge/locked.md", "---\ntitle: T\nsummary: ''\n---\nbody")
    os.chmod(p, 0o000)
    try:
        llm = FakeLLM(reply="x.")
        stats = enrich_notes(cfg, llm)
    finally:
        os.chmod(p, 0o644)  # so tmp_path cleanup works
    assert stats.failures == ("Knowledge/locked.md",)
    assert stats.summarized == 0 and llm.calls == []
