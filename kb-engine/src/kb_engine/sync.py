import logging
from dataclasses import dataclass

from kb_engine.chunking import embedding_text, fts_text, summary_of
from kb_engine.config import Config
from kb_engine.embeddings import Embedder
from kb_engine.models import Note
from kb_engine.store import Store
from kb_engine.vault import iter_notes

# Inbox holds unprocessed captures; never embed it. Everything else under
# Knowledge/ (including synthesized wiki/ articles) is indexed.
EXCLUDED_DIRS = ("inbox",)

logger = logging.getLogger(__name__)


def _log_unreadable(path, exc) -> None:
    logger.warning("skipping unreadable note %s: %s", path, exc)


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
            knowledge_dir,
            base=cfg.vault_path,
            exclude_dirs=EXCLUDED_DIRS,
            on_error=_log_unreadable,
        )
    }


def _url_msgid(note: Note) -> tuple[str | None, str | None]:
    """Extract url and message_id from note frontmatter as (url, message_id)."""
    url = note.frontmatter.get("url") or None
    message_id = note.frontmatter.get("message_id") or None
    return (
        str(url) if url is not None else None,
        str(message_id) if message_id is not None else None,
    )


def _index_note(store: Store, note: Note, embedder: Embedder) -> None:
    # Semantic vector = title + summary (one clean vector). FTS = full body.
    vector = embedder.embed_passages([embedding_text(note)])[0]
    url, message_id = _url_msgid(note)
    store.upsert_note(
        path=note.path, title=note.title, sha256=note.sha256,
        tags=list(note.tags), summary=summary_of(note),
        url=url,
        message_id=message_id,
    )
    store.replace_chunks(note.path, [(0, fts_text(note), vector)])


def sync(cfg: Config, store: Store, embedder: Embedder) -> SyncStats:
    """Incremental files-as-truth sync: embed new/changed, drop deleted."""
    store.init_schema()
    disk = _disk_notes(cfg)
    db_shas = store.all_note_shas()

    added = changed = deleted = 0

    for path, note in disk.items():
        if path not in db_shas:
            _index_note(store, note, embedder)
            added += 1
        elif db_shas[path] != note.sha256:
            _index_note(store, note, embedder)
            changed += 1
        else:
            # sha unchanged: skip the expensive re-embed, but keep url/message_id
            # current so cache-based dedup covers already-filed notes.
            store.set_note_metadata(path, *_url_msgid(note))

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
