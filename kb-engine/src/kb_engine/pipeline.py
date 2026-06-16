"""Deterministic, LLM-free maintenance pipeline.

Composes the already-tested engine steps into one unattended run:

1. ``sync`` — embed new/changed notes, drop deleted (cache follows the vault).
2. ``apply_topic_tags(only_status=("active",))`` — write ``topic/<slug>`` tags,
   but only for *approved* (active) topics. Discovered proposals stay
   ``proposed``, so a scheduled run never silently mis-tags notes.
3. ``sticky_discover`` — cluster the residual into new ``proposed`` topics.
4. ``build_digest`` — render ``<vault>/_system/kb-digest.md`` (the review entry
   point). Regenerable; no note mutation.

This is what the weekly launchd agent runs. It is pure compute + a regenerable
digest, safe to run unattended.
"""

from dataclasses import dataclass
from pathlib import Path

from kb_engine.config import Config
from kb_engine.embeddings import Embedder
from kb_engine.importing.digest import build_digest
from kb_engine.store import Store
from kb_engine.sync import sync
from kb_engine.topics.apply import apply_topic_tags
from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.sticky import sticky_discover

_INBOX_RELDIR = Path("Knowledge") / "inbox"
_DIGEST_RELPATH = Path("_system") / "kb-digest.md"

# Unattended runs apply only approved topics; proposals stay proposed.
_ACTIVE_ONLY = ("active",)


@dataclass(frozen=True)
class PipelineResult:
    synced: int  # notes added or changed this run
    applied: int  # notes that gained a topic/ tag (active topics only)
    proposals: int  # new discovered topics from the residual
    inbox: int  # inbox stubs awaiting processing (Knowledge/inbox/)
    unfiled: int  # notes assigned to no topic
    digest_path: str  # vault-relative path of the written digest


def count_inbox(vault_path: Path) -> int:
    """Number of markdown stubs in ``Knowledge/inbox/``."""
    inbox = vault_path / _INBOX_RELDIR
    if not inbox.is_dir():
        return 0
    return sum(1 for _ in inbox.glob("*.md"))


def unfiled_notes(store: Store) -> list[str]:
    """Note paths in the store assigned to no topic, sorted."""
    all_notes = set(store.all_note_shas())
    filed = {
        member.note_path
        for topic in store.load_topics()
        for member in store.topic_members(topic.slug)
    }
    return sorted(all_notes - filed)


def run_pipeline(
    cfg: Config, store: Store, embedder: Embedder, clusterer: Clusterer
) -> PipelineResult:
    """Run the full deterministic maintenance pipeline; return a summary.

    Mutates notes only for ``active`` topics (the gated apply); everything else
    is engine-cache plus a regenerable ``_system/kb-digest.md``.
    """
    store.init_schema()

    sync_stats = sync(cfg, store, embedder)
    synced = sync_stats.added + sync_stats.changed

    apply_result = apply_topic_tags(store, cfg.vault_path, only_status=_ACTIVE_ONLY)

    sticky_result = sticky_discover(store, clusterer)

    inbox_count = count_inbox(cfg.vault_path)
    unfiled = unfiled_notes(store)
    text = build_digest(
        store, vault_path=cfg.vault_path, inbox_count=inbox_count, unfiled=unfiled
    )
    digest_path = cfg.vault_path / _DIGEST_RELPATH
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(text)

    return PipelineResult(
        synced=synced,
        applied=apply_result.n_changed,
        proposals=sticky_result.n_new_topics,
        inbox=inbox_count,
        unfiled=len(unfiled),
        digest_path=_DIGEST_RELPATH.as_posix(),
    )
