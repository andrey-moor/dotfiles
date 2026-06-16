from dataclasses import dataclass
from pathlib import Path

from kb_engine.store import Store

# A wiki article at Knowledge/wiki/<slug>.md means the topic is already
# synthesized, so it stops being a candidate.
_WIKI_RELDIR = Path("Knowledge") / "wiki"


@dataclass(frozen=True)
class Candidate:
    slug: str
    label: str
    size: int


def synthesis_candidates(
    store: Store, vault_path: Path, min_members: int = 5
) -> list[Candidate]:
    """Topics with >= ``min_members`` and no wiki article yet, biggest first.

    A topic is excluded when ``<vault>/Knowledge/wiki/<slug>.md`` already exists.
    The match is case-insensitive so ``wiki/RAG.md`` excludes slug ``rag`` on
    case-sensitive filesystems (ext4) too, not just on case-insensitive APFS.
    The result is sorted by member count descending so the richest synthesis
    targets surface first.
    """
    wiki_dir = vault_path / _WIKI_RELDIR
    existing = (
        {f.stem.lower() for f in wiki_dir.iterdir() if f.suffix == ".md"}
        if wiki_dir.exists()
        else set()
    )
    candidates = [
        Candidate(slug=topic.slug, label=topic.label, size=size)
        for topic in store.load_topics()
        if (size := len(store.topic_members(topic.slug))) >= min_members
        and topic.slug not in existing  # topic.slug is already lowercase
    ]
    candidates.sort(key=lambda c: c.size, reverse=True)
    return candidates
