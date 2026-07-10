"""Reconcile discovered topics against the hand-maintained ``_taxonomy.md`` tags.

Parses declared ``Category/Sub`` and bolded single-word tags out of the taxonomy
file, then diffs them against discovered topics by Jaccard overlap of their
member sets — producing a ``TaxonomyDiff`` of per-tag topic mappings, topics
already covered by a tag, brand-new topics no tag aligns with, and orphan tags no
topic matches. Read-only analysis: it proposes, the human decides.
"""
import re
from dataclasses import dataclass
from pathlib import Path

# Two-level tag like "AI/RAG" or "Dev/Rust": Capitalized category / subtoken.
_TWO_LEVEL_RE = re.compile(r"\b[A-Z][A-Za-z0-9]+/[A-Za-z0-9]+\b")
# A bolded list token like "**GameDev**" or "**Tutorials**" (single-word tags).
_BOLD_TOKEN_RE = re.compile(r"\*\*([A-Za-z0-9/]+)\*\*")

# Per-tag mapping value: ranked (topic_slug, jaccard_overlap), highest first.
TagMapping = dict[str, list[tuple[str, float]]]


@dataclass(frozen=True)
class TaxonomyDiff:
    mapping: TagMapping  # existing tag -> ranked [(topic_slug, overlap), ...]
    covered_topics: list[str]  # topics aligned with at least one tag
    new_topics: list[str]  # discovered topics no existing tag aligns with
    orphan_tags: list[str]  # tags no topic aligns with


def parse_taxonomy_tags(path: Path) -> set[str]:
    """Extract declared tags from a ``_taxonomy.md`` file.

    Only list-item lines (starting with ``-``) are considered, so prose that
    happens to contain a slash (e.g. the format hint ``Category/Subcategory``)
    is ignored. On each list line we capture two-level ``Cat/Sub`` tokens and
    single-word bolded tokens (``**GameDev**``), tolerating the real file's
    ``- **Cat/Sub** — description`` layout.
    """
    tags: set[str] = set()
    for raw_line in Path(path).read_text().splitlines():
        line = raw_line.strip()
        if not line.startswith("-"):
            continue
        for match in _TWO_LEVEL_RE.findall(line):
            tags.add(match)
        for token in _BOLD_TOKEN_RE.findall(line):
            tags.add(token)
    return tags


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def diff_taxonomy(
    existing_tag_notes: dict[str, set[str]],
    topic_member_notes: dict[str, set[str]],
) -> TaxonomyDiff:
    """Compare existing taxonomy tags against discovered topic membership.

    Pure Jaccard set math over note paths. For each tag, topics sharing at least
    one note are ranked by descending Jaccard overlap (ties broken by slug). A
    topic is *covered* if it aligns with any tag; *new* otherwise (structure the
    data found that the taxonomy lacks). A tag with no aligned topic is an
    *orphan*. Output lists are sorted for deterministic results.
    """
    mapping: TagMapping = {}
    covered: set[str] = set()
    for tag in sorted(existing_tag_notes):
        tag_notes = existing_tag_notes[tag]
        ranked = sorted(
            (
                (slug, _jaccard(tag_notes, members))
                for slug, members in topic_member_notes.items()
                if tag_notes & members
            ),
            key=lambda item: (-item[1], item[0]),
        )
        mapping[tag] = ranked
        covered.update(slug for slug, _ in ranked)

    new_topics = sorted(set(topic_member_notes) - covered)
    orphan_tags = sorted(tag for tag, ranked in mapping.items() if not ranked)

    return TaxonomyDiff(
        mapping=mapping,
        covered_topics=sorted(covered),
        new_topics=new_topics,
        orphan_tags=orphan_tags,
    )
