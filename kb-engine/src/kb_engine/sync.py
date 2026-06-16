from dataclasses import dataclass

from kb_engine.chunking import chunk_note
from kb_engine.config import Config
from kb_engine.embeddings import Embedder
from kb_engine.models import Note
from kb_engine.store import Store
from kb_engine.vault import iter_notes

# Inbox holds unprocessed captures; never embed it. Everything else under
# Knowledge/ (including synthesized wiki/ articles) is indexed.
EXCLUDED_DIRS = ("inbox",)


@dataclass(frozen=True)
class SyncStats:
    added: int
    changed: int
    deleted: int


def _disk_notes(cfg: Config) -> dict[str, Note]:
    """Vault-relative notes under Knowledge/, excluding the inbox."""
    knowledge_dir = cfg.knowledge_dir
    if not knowledge_dir.is_dir():
        return {}
    return {
        note.path: note
        for note in iter_notes(
            knowledge_dir, base=cfg.vault_path, exclude_dirs=EXCLUDED_DIRS
        )
    }


def _index_note(store: Store, note: Note, embedder: Embedder, max_tokens: int) -> None:
    chunks = chunk_note(note, max_tokens=max_tokens)
    vectors = embedder.embed_passages([c.text for c in chunks])
    store.upsert_note(
        path=note.path, title=note.title, sha256=note.sha256, tags=list(note.tags)
    )
    store.replace_chunks(
        note.path,
        [(c.ordinal, c.text, vec) for c, vec in zip(chunks, vectors)],
    )


def sync(cfg: Config, store: Store, embedder: Embedder) -> SyncStats:
    """Incremental files-as-truth sync: embed new/changed, drop deleted."""
    store.init_schema()
    disk = _disk_notes(cfg)
    db_shas = store.all_note_shas()

    added = changed = deleted = 0

    for path, note in disk.items():
        if path not in db_shas:
            _index_note(store, note, embedder, cfg.chunk_tokens)
            added += 1
        elif db_shas[path] != note.sha256:
            _index_note(store, note, embedder, cfg.chunk_tokens)
            changed += 1

    for path in db_shas:
        if path not in disk:
            store.delete_note(path)
            deleted += 1

    return SyncStats(added=added, changed=changed, deleted=deleted)


def rebuild(cfg: Config, store: Store, embedder: Embedder) -> SyncStats:
    """Drop the entire cache and re-embed the vault from scratch."""
    store.drop_all()
    store.init_schema()
    return sync(cfg, store, embedder)
