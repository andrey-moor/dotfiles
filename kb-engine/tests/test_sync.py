from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
from kb_engine.store import Store
from kb_engine.sync import SyncStats, rebuild, sync


def _vault(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir()
    (k / "a.md").write_text("---\ntitle: A\ntags: [AI/RAG]\n---\nalpha content")
    return tmp_path


def test_initial_sync_embeds_all(tmp_path):
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path / "t.db")
    st = sync(cfg, Store(cfg.db_path), FakeEmbedder(dim=16))
    assert st.added == 1 and st.changed == 0 and st.deleted == 0


def test_second_sync_is_noop_when_unchanged(tmp_path):
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    sync(cfg, store, FakeEmbedder(dim=16))
    st2 = sync(cfg, store, FakeEmbedder(dim=16))
    assert st2.added == 0 and st2.changed == 0


def test_edit_triggers_reembed_and_delete_removes(tmp_path):
    v = _vault(tmp_path)
    cfg = Config(vault_path=v, db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    sync(cfg, store, FakeEmbedder(dim=16))
    (v / "Knowledge" / "a.md").write_text("---\ntitle: A\n---\nDIFFERENT body now")
    assert sync(cfg, store, FakeEmbedder(dim=16)).changed == 1
    (v / "Knowledge" / "a.md").unlink()
    assert sync(cfg, store, FakeEmbedder(dim=16)).deleted == 1


def test_sync_skips_inbox_but_includes_wiki(tmp_path):
    v = _vault(tmp_path)
    k = v / "Knowledge"
    inbox = k / "inbox"
    inbox.mkdir()
    (inbox / "unprocessed.md").write_text("---\ntitle: Raw\n---\nunprocessed dump")
    wiki = k / "wiki"
    wiki.mkdir()
    (wiki / "topic.md").write_text("---\ntitle: Topic\n---\nsynthesized article")
    cfg = Config(vault_path=v, db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    # a.md + wiki/topic.md = 2 added; inbox/unprocessed.md skipped.
    assert sync(cfg, store, FakeEmbedder(dim=16)).added == 2
    shas = store.all_note_shas()
    assert "Knowledge/wiki/topic.md" in shas
    assert "Knowledge/inbox/unprocessed.md" not in shas


def test_sync_stats_is_frozen():
    stats = SyncStats(added=1, changed=2, deleted=3)
    try:
        stats.added = 9  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("SyncStats must be frozen")


def test_rebuild_drops_then_resyncs(tmp_path):
    v = _vault(tmp_path)
    cfg = Config(vault_path=v, db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    sync(cfg, store, FakeEmbedder(dim=16))
    # Stale note left in the DB that no longer exists on disk.
    store.upsert_note(path="Knowledge/ghost.md", title="Ghost", sha256="x", tags=[])
    st = rebuild(cfg, store, FakeEmbedder(dim=16))
    assert st.added == 1 and st.deleted == 0
    assert store.note_sha("Knowledge/ghost.md") is None
