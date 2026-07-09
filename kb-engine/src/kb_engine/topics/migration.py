"""Taxonomy→areas/topics migration proposal: generate, render, parse.

The proposal is a FILE the human edits (decisions stay human-gated, D14):
``render_migration_proposal`` writes strict pipe tables;
``parse_migration_proposal`` reads them back with validation. The cutover
engine consumes only the parsed, human-approved result. The human edits ONLY
the ``decision`` column (tag table) and ``area`` column (topic table); every
other column is regenerable display context and is NOT round-tripped
semantically.
"""
import re
from collections import Counter
from dataclasses import dataclass

from kb_engine.store import Store
from kb_engine.topics.areas_registry import CATEGORY_TO_AREA, SEEDED_AREAS
from kb_engine.topics.labeling import slugify
from kb_engine.topics.taxonomy import diff_taxonomy

MAP_OVERLAP_MIN = 0.20
NEW_TOPIC_MIN_COUNT = 8
_VALID_AREAS = {a.slug for a in SEEDED_AREAS}
_DECISION_RE = re.compile(r"^(map:[a-z0-9-]+|topic:[a-z0-9-]+|area)$")
_DIVIDER_CELL_RE = re.compile(r"^:?-+:?$")

_TOPIC_HEADING = "## Topic → area"
_DISPOSITION_HEADING = "## Tag dispositions"
_TOPIC_HEADER = ("topic", "area", "evidence")
_DISPOSITION_HEADER = ("tag", "count", "area", "best topic (jaccard)", "decision")
_NO_TOPIC_CELL = "—"

_INSTRUCTIONS = (
    "# Taxonomy → Areas/Topics Migration Proposal\n"
    "\n"
    "_Edit the **decision** / **area** columns, then approve. Valid decisions:_\n"
    "_`map:<topic-slug>` (notes gain that topic tag), `topic:<new-slug>` (a new manual_\n"
    "_topic is created from this tag), `area` (tag retires; notes keep just the area)._"
)


@dataclass(frozen=True)
class TagDisposition:
    tag: str                 # e.g. "AI/RAG" or "GameDev"
    count: int               # notes carrying it
    area: str                # implied area slug (from the category)
    best_topic: str | None   # highest-Jaccard aligned topic
    overlap: float           # that Jaccard (0.0 when none)
    decision: str            # "map:<slug>" | "topic:<slug>" | "area"


@dataclass(frozen=True)
class TopicArea:
    slug: str                # topic slug
    proposed_area: str       # area slug ("" when no evidence)
    evidence: str            # e.g. "18/23 member notes tagged AI/*"


@dataclass(frozen=True)
class MigrationProposal:
    topic_areas: tuple[TopicArea, ...]
    dispositions: tuple[TagDisposition, ...]


# --- generation ---------------------------------------------------------------


def _tag_category(tag: str) -> str:
    return tag.split("/", 1)[0]


def _implied_area(tag: str) -> str | None:
    return CATEGORY_TO_AREA.get(_tag_category(tag))


def _propose_decision(count: int, best: str | None, overlap: float, tag: str) -> str:
    if best is not None and overlap >= MAP_OVERLAP_MIN:
        return f"map:{best}"
    if count >= NEW_TOPIC_MIN_COUNT:
        return f"topic:{slugify(tag.replace('/', ' '))}"
    return "area"


def build_migration_proposal(store: Store, declared_tags: set[str]) -> MigrationProposal:
    notes_by_tag = store.notes_by_tag()
    # Category tags = declared two-level tags in live use + the single-level
    # category tag GameDev; junk/facet tags never enter.
    live_tags = {
        tag for tag in notes_by_tag
        if (("/" in tag and not tag.startswith(("topic/", "area/"))) or
            tag in CATEGORY_TO_AREA)
        and _implied_area(tag) is not None
        and (tag in declared_tags or tag in CATEGORY_TO_AREA)
    }
    topic_members = {
        t.slug: {m.note_path for m in store.topic_members(t.slug)}
        for t in store.load_topics()
    }
    diff = diff_taxonomy(
        {tag: notes_by_tag[tag] for tag in sorted(live_tags)}, topic_members
    )
    dispositions = []
    for tag in sorted(live_tags):
        ranked = diff.mapping.get(tag, [])
        best, overlap = (ranked[0] if ranked else (None, 0.0))
        count = len(notes_by_tag[tag])
        dispositions.append(
            TagDisposition(
                tag=tag, count=count, area=_implied_area(tag),
                best_topic=best, overlap=overlap,
                decision=_propose_decision(count, best, overlap, tag),
            )
        )
    topic_areas = _propose_topic_areas(store, notes_by_tag)
    return MigrationProposal(
        topic_areas=tuple(topic_areas), dispositions=tuple(dispositions)
    )


def _note_categories(notes_by_tag: dict[str, set[str]]) -> dict[str, set[str]]:
    """Map each note path to the set of area-mapped categories among its tags."""
    out: dict[str, set[str]] = {}
    for tag, notes in notes_by_tag.items():
        category = _tag_category(tag)
        if category not in CATEGORY_TO_AREA:
            continue
        for note in notes:
            out.setdefault(note, set()).add(category)
    return out


def _topic_area_for(slug: str, counts: Counter, n_members: int) -> TopicArea:
    if not counts:
        return TopicArea(slug=slug, proposed_area="", evidence="")
    # Majority category: higher count first, then alphabetical for stable ties.
    category, top_count = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return TopicArea(
        slug=slug,
        proposed_area=CATEGORY_TO_AREA[category],
        evidence=f"{top_count}/{n_members} member notes tagged {category}/*",
    )


def _propose_topic_areas(
    store: Store, notes_by_tag: dict[str, set[str]]
) -> list[TopicArea]:
    note_categories = _note_categories(notes_by_tag)
    result: list[TopicArea] = []
    for topic in store.load_topics():
        members = [m.note_path for m in store.topic_members(topic.slug)]
        counts: Counter = Counter()
        for note in members:
            for category in note_categories.get(note, ()):
                counts[category] += 1
        result.append(_topic_area_for(topic.slug, counts, len(members)))
    return result


# --- rendering ----------------------------------------------------------------


def _best_topic_cell(disposition: TagDisposition) -> str:
    if disposition.best_topic is None:
        return _NO_TOPIC_CELL
    return f"{disposition.best_topic} ({disposition.overlap:.2f})"


def _row(cells: tuple[str, ...]) -> str:
    return "| " + " | ".join(cells) + " |"


def _divider(n: int) -> str:
    return "|" + "|".join(["---"] * n) + "|"


def _render_topic_areas(topic_areas: tuple[TopicArea, ...]) -> str:
    lines = [_TOPIC_HEADING, "", _row(_TOPIC_HEADER), _divider(len(_TOPIC_HEADER))]
    lines.extend(
        _row((ta.slug, ta.proposed_area, ta.evidence)) for ta in topic_areas
    )
    return "\n".join(lines)


def _render_dispositions(dispositions: tuple[TagDisposition, ...]) -> str:
    lines = [
        _DISPOSITION_HEADING, "",
        _row(_DISPOSITION_HEADER), _divider(len(_DISPOSITION_HEADER)),
    ]
    lines.extend(
        _row((d.tag, str(d.count), d.area, _best_topic_cell(d), d.decision))
        for d in dispositions
    )
    return "\n".join(lines)


def render_migration_proposal(proposal: MigrationProposal) -> str:
    """Render the human-editable artifact (instructions + two strict tables)."""
    sections = [
        _INSTRUCTIONS,
        _render_topic_areas(proposal.topic_areas),
        _render_dispositions(proposal.dispositions),
    ]
    return "\n\n".join(sections) + "\n"


# --- parsing ------------------------------------------------------------------


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_divider(cells: list[str]) -> bool:
    return bool(cells) and all(_DIVIDER_CELL_RE.match(cell) for cell in cells)


def _section_rows(text: str, heading: str, header: tuple[str, ...]) -> list[list[str]]:
    """Return the data-row cell lists under ``heading`` (header/divider skipped).

    Text outside the ``## `` sections is ignored; the human edits cells only.
    A heading appearing more than once is rejected: a duplicated section would
    silently merge rows from both copies into the cutover (over-inclusion).
    """
    lines = text.splitlines()
    if sum(1 for line in lines if line.strip() == heading) > 1:
        raise ValueError(f"duplicate section: {heading}")
    rows: list[list[str]] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped == heading
            continue
        if not in_section or not stripped.startswith("|"):
            continue
        cells = _split_row(stripped)
        if _is_divider(cells) or tuple(c.lower() for c in cells) == header:
            continue
        rows.append(cells)
    return rows


def _parse_topic_areas(rows: list[list[str]]) -> list[TopicArea]:
    result: list[TopicArea] = []
    for cells in rows:
        if len(cells) < 3:
            raise ValueError(f"row {cells!r}: malformed topic→area row")
        slug, area, evidence = cells[0], cells[1], cells[2]
        if area and area not in _VALID_AREAS:
            raise ValueError(f"row {slug!r}: unknown area {area!r}")
        result.append(TopicArea(slug=slug, proposed_area=area, evidence=evidence))
    return result


def _build_disposition(
    tag: str, count_text: str, area: str, decision: str, known_slugs: set[str]
) -> TagDisposition:
    try:
        count = int(count_text)
    except ValueError:
        raise ValueError(f"row {tag!r}: non-integer count {count_text!r}") from None
    if area not in _VALID_AREAS:
        raise ValueError(f"row {tag!r}: unknown area {area!r}")
    if not _DECISION_RE.match(decision):
        raise ValueError(f"row {tag!r}: invalid decision {decision!r}")
    if decision.startswith("map:") and decision.split(":", 1)[1] not in known_slugs:
        raise ValueError(f"row {tag!r}: map target not a known topic ({decision!r})")
    # best_topic/overlap are display-only; the human never edits them, so they
    # are not reconstructed here (see module docstring).
    return TagDisposition(
        tag=tag, count=count, area=area,
        best_topic=None, overlap=0.0, decision=decision,
    )


def _parse_dispositions(
    rows: list[list[str]], known_slugs: set[str]
) -> list[TagDisposition]:
    result: list[TagDisposition] = []
    for cells in rows:
        if len(cells) < 5:
            raise ValueError(f"row {cells!r}: malformed disposition row")
        tag, count_text, area, _best, decision = cells[:5]
        result.append(
            _build_disposition(tag, count_text, area, decision, known_slugs)
        )
    return result


def parse_migration_proposal(text: str) -> MigrationProposal:
    """Re-read a rendered (possibly human-edited) proposal, validating cells.

    Round-trips ``(tag, count, area, decision)`` and ``(slug, proposed_area)``
    exactly. Rejects unknown decisions/areas and ``map:`` targets absent from
    the doc's topic list, naming the offending row in the ``ValueError``.
    """
    topic_rows = _section_rows(text, _TOPIC_HEADING, _TOPIC_HEADER)
    disposition_rows = _section_rows(text, _DISPOSITION_HEADING, _DISPOSITION_HEADER)
    topic_areas = _parse_topic_areas(topic_rows)
    known_slugs = {ta.slug for ta in topic_areas}
    dispositions = _parse_dispositions(disposition_rows, known_slugs)
    return MigrationProposal(
        topic_areas=tuple(topic_areas), dispositions=tuple(dispositions)
    )
