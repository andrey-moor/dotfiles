import kb_engine.pipeline as pipeline_mod
from kb_engine.topics.clustering import FakeClusterer  # returns the label array it is given
from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
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


def test_weekly_tier_runs_topic_steps_and_records_run(tmp_path, monkeypatch):
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)  # import-mail skips, no network
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path)
    result = run_pipeline(cfg, store, FakeEmbedder(), FakeClusterer([]), tier="weekly")
    names = [o.name for o in result.outcomes]
    assert ["import-mail", "enrich", "sync", "apply-topics", "discover", "eval"] == names
    assert store.last_run("pipeline")["tier"] == "weekly"
    digest = (tmp_path / "_system" / "kb-digest.md").read_text()
    assert digest.startswith("# KB Digest")
    assert "## Status" in digest and "Last run:" in digest
