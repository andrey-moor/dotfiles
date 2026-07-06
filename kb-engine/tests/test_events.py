from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.store import Store


def test_record_and_count_events(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.record_event("search", query="q", top_path="Knowledge/a.md", hit_rank=1)
    store.record_event("open", top_path="Knowledge/a.md")
    assert store.count_events() == 2
    assert store.count_events(kind="search") == 1


def test_search_command_logs_an_event(tmp_path, monkeypatch):
    k = tmp_path / "Knowledge"
    k.mkdir(parents=True)
    (k / "a.md").write_text("---\ntitle: Alpha\nsummary: alpha\n---\nalpha")
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    runner = CliRunner()
    db = tmp_path / "kb.db"
    assert runner.invoke(main, ["--vault", str(tmp_path), "--db", str(db), "sync"]).exit_code == 0
    assert runner.invoke(main, ["--vault", str(tmp_path), "--db", str(db), "search", "alpha"]).exit_code == 0
    store = Store(db)
    store.init_schema()
    assert store.count_events(kind="search") == 1


def test_log_event_command_records_open(tmp_path):
    runner = CliRunner()
    db = tmp_path / "kb.db"
    (tmp_path / "Knowledge").mkdir(parents=True)
    result = runner.invoke(
        main,
        ["--vault", str(tmp_path), "--db", str(db), "log-event", "--kind", "open", "--path", "Knowledge/a.md"],
    )
    assert result.exit_code == 0, result.output
    store = Store(db)
    store.init_schema()
    assert store.count_events(kind="open") == 1
