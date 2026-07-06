import os

from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
from kb_engine.store import Store
from kb_engine.sync import sync
from kb_engine.vault import evicted_note_paths


class CountingEmbedder(FakeEmbedder):
    def __init__(self):
        super().__init__()
        self.passage_calls = 0

    def embed_passages(self, texts):
        self.passage_calls += len(texts)
        return super().embed_passages(texts)


def _vault(tmp_path):
    (tmp_path / "Knowledge").mkdir(parents=True)
    return Config(vault_path=tmp_path, db_path=tmp_path / "kb.db")


def _note(cfg, name, text="---\ntitle: t\nsummary: s\n---\nbody"):
    p = cfg.vault_path / "Knowledge" / name
    p.write_text(text)
    return p


def test_unchanged_notes_are_not_reread_or_reembedded(tmp_path):
    cfg = _vault(tmp_path)
    _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    first_calls = emb.passage_calls
    stats = sync(cfg, store, emb)  # nothing touched
    assert emb.passage_calls == first_calls
    assert stats.unchanged == 1 and stats.added == 0 and stats.changed == 0


def test_touched_but_identical_content_does_not_reembed(tmp_path):
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    first_calls = emb.passage_calls
    os.utime(p, (os.path.getatime(p), os.path.getmtime(p) + 10))
    stats = sync(cfg, store, emb)
    assert emb.passage_calls == first_calls  # sha short-circuit
    assert stats.changed == 0


def test_changed_content_reembeds(tmp_path):
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    p.write_text("---\ntitle: t\nsummary: NEW\n---\nnew body")
    stats = sync(cfg, store, emb)
    assert stats.changed == 1


def test_evicted_placeholder_is_not_deleted(tmp_path):
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    p.unlink()
    (cfg.vault_path / "Knowledge" / ".a.md.icloud").write_bytes(b"stub")
    stats = sync(cfg, store, emb)
    assert stats.deleted == 0
    assert stats.evicted == 1
    assert "Knowledge/a.md" in store.all_note_stats()


def test_evicted_note_paths_maps_placeholder_names(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir(parents=True)
    (k / ".some note.md.icloud").write_bytes(b"")
    (k / "other.txt.icloud").write_bytes(b"")  # not a note — ignored
    assert evicted_note_paths(k, base=tmp_path) == frozenset({"Knowledge/some note.md"})


def test_unreadable_but_stat_unchanged_note_is_never_opened(tmp_path):
    # Locks the no-read invariant: a stat-unchanged file must not even be
    # opened — if sync tried, the 0o000 perms would raise and land in failures.
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    first_calls = emb.passage_calls
    os.chmod(p, 0o000)  # unreadable, but mtime/size untouched
    try:
        stats = sync(cfg, store, emb)
    finally:
        os.chmod(p, 0o644)
    assert stats.unchanged == 1
    assert stats.failures == ()
    assert emb.passage_calls == first_calls


def test_unreadable_existing_note_is_kept_and_reported(tmp_path):
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    p.write_text("---\ntitle: t\nsummary: changed\n---\nx")  # force a read attempt
    os.chmod(p, 0o000)
    try:
        stats = sync(cfg, store, emb)
    finally:
        os.chmod(p, 0o644)
    assert stats.deleted == 0
    assert stats.failures == ("Knowledge/a.md",)
    assert "Knowledge/a.md" in store.all_note_stats()
