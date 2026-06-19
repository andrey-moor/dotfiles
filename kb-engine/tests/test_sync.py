import types

import numpy as np

from kb_engine.chunking import embedding_text
from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
from kb_engine.models import Note
from kb_engine.store import Store
from kb_engine.sync import SyncStats, _index_note, rebuild, sync


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


def test_sync_no_knowledge_dir_is_clean_noop(tmp_path):
    # Vault with no Knowledge/ subdir at all → nothing to embed, no error.
    cfg = Config(vault_path=tmp_path, db_path=tmp_path / "t.db")
    st = sync(cfg, Store(cfg.db_path), FakeEmbedder(dim=16))
    assert st.added == 0 and st.changed == 0 and st.deleted == 0


def test_sync_skips_directory_named_like_markdown(tmp_path):
    # rglob("*.md") also matches directories; a dir ending in .md must be skipped.
    v = _vault(tmp_path)
    (v / "Knowledge" / "weird.md").mkdir()  # a *directory* whose name ends in .md
    cfg = Config(vault_path=v, db_path=tmp_path / "t.db")
    # Only the real a.md file is embedded; the bogus directory is ignored.
    assert sync(cfg, Store(cfg.db_path), FakeEmbedder(dim=16)).added == 1


def test_index_note_embeds_summary_and_ftss_full_body(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    emb = FakeEmbedder(dim=64)
    note = Note(
        path="Knowledge/a.md",
        title="Rust Macros",
        body="A very long body. " * 200,
        tags=("Dev/Rust",),
        wikilinks=(),
        frontmatter=types.MappingProxyType({"summary": "Declarative macros guide."}),
        sha256="x",
    )
    _index_note(store, note, emb)

    vecs = list(store.note_vectors())
    assert len(vecs) == 1                       # one vector, no dilution
    expected = emb.embed_passages([embedding_text(note)])[0]
    assert np.allclose(vecs[0][1], expected)
    assert store.keyword_search("body")          # body word still in FTS
