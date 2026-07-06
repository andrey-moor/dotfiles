from kb_engine.store import Store


def test_store_uses_wal_and_busy_timeout(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    journal = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    timeout = store._conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert journal == "wal"
    assert timeout == 5000
