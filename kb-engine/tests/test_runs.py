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


def test_last_run_finished_only_skips_unfinished_current_run(tmp_path):
    # During a pipeline run the current (unfinished) row is newest by id, so a
    # plain last_run returns it. finished_only must skip it and return the last
    # COMPLETED run — what the digest health line needs.
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    a = store.start_run("pipeline", tier="weekly")
    store.finish_run(a, ok=True, counts={"eval": "recall@5 1.00"})
    store.start_run("pipeline")  # B: started, still in flight (NULL finished_at)
    finished = store.last_run("pipeline", finished_only=True)
    assert finished["counts"] == {"eval": "recall@5 1.00"}
    assert finished["finished_at"] is not None
    # default behaviour unchanged: newest row wins even though it's unfinished
    assert store.last_run("pipeline")["finished_at"] is None
