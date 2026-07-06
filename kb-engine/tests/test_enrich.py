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
    assert post.content.strip() == "long body text"


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
