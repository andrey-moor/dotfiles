import logging
from dataclasses import dataclass

from kb_engine.chunking import embedding_text, fts_text, summary_of
from kb_engine.config import Config
from kb_engine.embeddings import Embedder
from kb_engine.models import Note
from kb_engine.store import Store
from kb_engine.vault import evicted_note_paths, iter_note_stats, read_note

# Inbox holds unprocessed captures; never embed it. Everything else under
# Knowledge/ (including synthesized wiki/ articles) is indexed.
EXCLUDED_DIRS = ("inbox",)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncStats:
    added: int
    changed: int
    deleted: int
    unchanged: int = 0
    evicted: int = 0
    failures: tuple[str, ...] = ()


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
    """Incremental files-as-truth sync: stat-prefiltered, eviction-aware, tolerant."""
    store.init_schema()
    knowledge_dir = cfg.knowledge_dir
    if not knowledge_dir.is_dir():
        return SyncStats(added=0, changed=0, deleted=0)

    disk = {
        s.path: s
        for s in iter_note_stats(
            knowledge_dir, base=cfg.vault_path, exclude_dirs=EXCLUDED_DIRS
        )
    }
    evicted = evicted_note_paths(
        knowledge_dir, base=cfg.vault_path, exclude_dirs=EXCLUDED_DIRS
    )
    db_stats = store.all_note_stats()

    added = changed = unchanged = 0
    failures: list[str] = []
    for path, stat in disk.items():
        known = db_stats.get(path)
        if known is not None and known[1] == stat.mtime and known[2] == stat.size:
            unchanged += 1
            continue  # not even read — the iCloud-safety win
        try:
            note = read_note(stat.abs_path, base=cfg.vault_path)
        except OSError as exc:
            logger.warning("skipping unreadable note %s: %s", stat.abs_path, exc)
            failures.append(path)  # vault-relative, matching the rest of sync
            continue
        if known is None:
            _index_note(store, note, embedder)
            added += 1
        elif known[0] != note.sha256:
            _index_note(store, note, embedder)
            changed += 1
        else:
            # Stat changed but content identical: no re-embed, but refresh
            # url/message_id so cache-based dedup covers already-filed notes.
            store.set_note_metadata(path, *_url_msgid(note))
            unchanged += 1
        store.set_note_stat(path, stat.mtime, stat.size)

    deleted = 0
    for path in db_stats:
        if path not in disk and path not in evicted:
            store.delete_note(path)
            deleted += 1

    return SyncStats(
        added=added,
        changed=changed,
        deleted=deleted,
        unchanged=unchanged,
        evicted=len(evicted & set(db_stats)),
        failures=tuple(failures),
    )


def rebuild(cfg: Config, store: Store, embedder: Embedder) -> SyncStats:
    """Drop the entire cache and re-embed the vault from scratch."""
    store.drop_all()
    store.init_schema()
    return sync(cfg, store, embedder)
