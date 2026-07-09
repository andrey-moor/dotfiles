import kb_engine.llm as llm_mod
import kb_engine.pipeline as pipeline_mod
from kb_engine.topics.clustering import FakeClusterer  # returns the label array it is given
from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
from kb_engine.llm import FakeLLM
from kb_engine.pipeline import run_pipeline
from kb_engine.store import Store


def _cfg(tmp_path):
    (tmp_path / "Knowledge").mkdir(parents=True)
    (tmp_path / "_system").mkdir()
    return Config(vault_path=tmp_path, db_path=tmp_path / "kb.db")


def test_failed_sync_still_writes_digest_with_failed_status(tmp_path, monkeypatch):
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)  # import-mail skips, no network
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path)

    def boom(*a, **k):
        raise OSError("EDEADLK simulated")

    monkeypatch.setattr(pipeline_mod, "sync", boom)
    result = run_pipeline(cfg, store, FakeEmbedder(), FakeClusterer([]), tier="daily")
    assert result.ok is False
    digest = (tmp_path / "_system" / "kb-digest.md").read_text()
    assert "FAILED" in digest and "sync" in digest
    assert store.last_run("pipeline")["ok"] is False


def test_daily_tier_skips_topic_steps(tmp_path, monkeypatch):
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)  # import-mail skips, no network
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path)
    result = run_pipeline(cfg, store, FakeEmbedder(), FakeClusterer([]), tier="daily")
    names = [o.name for o in result.outcomes]
    assert ["import-mail", "enrich", "sync"] == names


def test_enrich_step_without_key_pins_skip_string(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = _cfg(tmp_path)
    assert pipeline_mod._enrich_step(cfg) == "skipped: no ANTHROPIC_API_KEY"


def test_enrich_step_pins_success_detail_format(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    # _enrich_step imports AnthropicLLM at call time, so patching the llm module
    # swaps in the offline fake; no network is ever touched.
    monkeypatch.setattr(llm_mod, "AnthropicLLM", lambda model: FakeLLM(reply="d."))
    cfg = _cfg(tmp_path)
    knowledge = tmp_path / "Knowledge"
    (knowledge / "garbled-machine-slug-here.md").write_text(
        "---\ntitle: garbled-machine-slug-here\nsummary: ''\n---\nbody"
    )
    # Empty body + clean title: nothing to summarize from -> the skipped counter.
    (knowledge / "empty.md").write_text("---\ntitle: A Clean Title\nsummary: ''\n---\n")
    assert pipeline_mod._enrich_step(cfg) == (
        "1 summarized · 1 whys · 1 titles · 1 skipped · 0 failed"
    )


def test_weekly_tier_runs_topic_steps_and_records_run(tmp_path, monkeypatch):
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)  # import-mail skips, no network
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path)
    result = run_pipeline(cfg, store, FakeEmbedder(), FakeClusterer([]), tier="weekly")
    names = [o.name for o in result.outcomes]
    assert ["import-mail", "enrich", "backfill", "sync", "apply-topics", "discover", "eval"] == names
    assert store.last_run("pipeline")["tier"] == "weekly"
    digest = (tmp_path / "_system" / "kb-digest.md").read_text()
    assert digest.startswith("# KB Digest")
    assert "## Status" in digest and "Last run:" in digest
