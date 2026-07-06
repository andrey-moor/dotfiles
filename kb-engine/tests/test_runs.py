from kb_engine.store import Store


def test_run_lifecycle_roundtrip(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    run_id = store.start_run("pipeline", tier="daily")
    assert store.last_run()["finished_at"] is None
    store.finish_run(run_id, ok=True, counts={"added": 3}, errors=[])
    last = store.last_run("pipeline")
    assert last["ok"] is True
    assert last["counts"] == {"added": 3}
    assert last["tier"] == "daily"
    assert last["finished_at"] is not None


def test_last_run_returns_none_when_empty(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    assert store.last_run() is None


def test_failed_run_records_errors(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    run_id = store.start_run("pipeline")
    store.finish_run(run_id, ok=False, errors=["sync: OSError: boom"])
    assert store.last_run()["ok"] is False
    assert store.last_run()["errors"] == ["sync: OSError: boom"]
