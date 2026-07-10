import re
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from kb_engine.models import Area, Topic, TopicMember
from kb_engine.store import Store

PROPOSALS_START = "<!-- KB-PROPOSALS:START -->"
PROPOSALS_END = "<!-- KB-PROPOSALS:END -->"

_TOPICS_RELDIR = Path("_system") / "topics"
_TAXONOMY_RELPATH = Path("_system") / "_taxonomy.md"
_TAGS_BASE_RELPATH = Path("Knowledge") / "tags.base"
_TOPIC_LINK_PREFIX = "_system/topics"

_TAXONOMY_INTRO = (
    "One hierarchy: areas → topics. Tags: `area/<slug>`, `topic/<slug>`; "
    "facets combine freely."
)
# The four cross-cutting facet tags (mirrors the taxonomy's Cross-cutting section).
_FACETS: tuple[str, ...] = (
    "- **Tutorials** — Step-by-step how-to content",
    "- **Reference** — Documentation, specs, guidelines",
    "- **Inspiration** — Ideas to try, examples to follow",
    "- **Tools** — Specific tools evaluated or recommended",
)


@dataclass(frozen=True)
class RenderResult:
    n_topics: int
    n_areas: int
    index_path: str  # vault-relative posix
    topic_paths: tuple[str, ...]  # vault-relative posix
    taxonomy_path: str  # vault-relative posix
    unfiled_path: str  # vault-relative posix
    area_paths: tuple[str, ...] = ()  # vault-relative posix (v2 area pages)
    tags_base_path: str = ""  # vault-relative posix ("" pre-cutover)


def _topics_by_slug(topics: list[Topic]) -> dict[str, Topic]:
    return {topic.slug: topic for topic in topics}


def _render_index(
    areas: list[Area],
    topics: list[Topic],
    members_by_slug: dict[str, list[TopicMember]],
) -> str:
    """Render the areas→topics outline. Deterministic (no timestamps)."""
    by_slug = _topics_by_slug(topics)
    lines: list[str] = ["# Topics", ""]

    def topic_line(slug: str) -> str:
        topic = by_slug[slug]
        count = len(members_by_slug.get(slug, []))
        return (
            f"- [[{_TOPIC_LINK_PREFIX}/{slug}]] — {topic.label} "
            f"({count} notes) [{topic.kind}/{topic.status}]"
        )

    grouped: set[str] = set()
    for area in areas:
        area_slugs = [slug for slug in area.topic_slugs if slug in by_slug]
        if not area_slugs:
            continue
        # Area headers only exist when the registry is seeded (v2): link the page.
        lines.append(f"## [[{_TOPIC_LINK_PREFIX}/area-{area.slug}|{area.label}]]")
        for slug in sorted(area_slugs):
            lines.append(topic_line(slug))
            grouped.add(slug)
        lines.append("")

    ungrouped = sorted(slug for slug in by_slug if slug not in grouped)
    if ungrouped:
        lines.append("## Ungrouped")
        for slug in ungrouped:
            lines.append(topic_line(slug))
        lines.append("")

    body = "\n".join(lines).rstrip() + "\n"
    post = frontmatter.Post(body, type="system", generated=True)
    return frontmatter.dumps(post) + "\n"


def _render_topic_moc(topic: Topic, members: list[TopicMember]) -> str:
    """Render one topic MOC, splitting primary (home) from secondary members.

    Primary members are listed under ``## Notes``; secondary (cross-link) members
    under ``## Also relevant``. A section is omitted when it has no members, so an
    all-secondary topic shows no empty ``## Notes`` placeholder; a topic with no
    members at all still gets a ``## Notes`` section. Each section is sorted by
    score desc, then path, for deterministic output.
    """
    keywords = ", ".join(topic.keywords)
    lines = [
        f"# {topic.label}",
        "",
        f"- slug: `{topic.slug}`",
        f"- kind/status: {topic.kind}/{topic.status}",
        f"- keywords: {keywords}",
        "",
    ]

    def block(header: str, items: list[TopicMember]) -> None:
        lines.extend([header, ""])
        ordered = sorted(items, key=lambda m: (-m.score, m.note_path))
        if ordered:
            lines.extend(f"- [[{m.note_path}]] ({m.score:.2f})" for m in ordered)
        else:
            lines.append("_None._")
        lines.append("")

    primary = [m for m in members if m.is_primary]
    secondary = [m for m in members if not m.is_primary]
    if primary:
        block("## Notes", primary)
    if secondary:
        block("## Also relevant", secondary)
    if not primary and not secondary:
        # A topic with no members at all still gets a Notes section placeholder.
        block("## Notes", [])

    body = "\n".join(lines).rstrip() + "\n"
    post = frontmatter.Post(body, type="system", generated=True)
    return frontmatter.dumps(post) + "\n"


def _render_unfiled_by_category(by_note: dict[str, list[str]]) -> str:
    """Group topicless notes under each taxonomy tag (a note may appear under several)."""
    by_tag: dict[str, list[str]] = {}
    for note_path, tags in by_note.items():
        for tag in (tags or ["(untagged)"]):
            by_tag.setdefault(tag, []).append(note_path)
    lines = [
        "# Unfiled by Category",
        "",
        "_Notes in no topic, grouped by taxonomy tag._",
        "",
    ]
    for tag in sorted(by_tag):
        lines.append(f"## {tag}")
        for note_path in sorted(by_tag[tag]):
            lines.append(f"- [[{note_path}]]")
        lines.append("")
    body = "\n".join(lines).rstrip() + "\n"
    return frontmatter.dumps(frontmatter.Post(body, type="system", generated=True)) + "\n"


def _area_of(tags: set[str]) -> str:
    """The group key: the note's first ``area/<slug>`` tag, else '(no area)'."""
    area_tags = sorted(tag for tag in tags if tag.startswith("area/"))
    return area_tags[0] if area_tags else "(no area)"


def _render_unfiled_by_area(
    by_note: dict[str, list[str]], tags_by_note: dict[str, set[str]]
) -> str:
    """Group topicless notes by their ``area/<slug>`` tag (v2 unfiled index).

    ``by_note`` supplies the set of topicless notes; ``tags_by_note`` maps each
    note to its tags (for the area lookup). A note with no ``area/*`` tag lands
    under "(no area)".
    """
    by_area: dict[str, list[str]] = {}
    for note_path in by_note:
        by_area.setdefault(_area_of(tags_by_note.get(note_path, set())), []).append(
            note_path
        )
    lines = [
        "# Unfiled by Area",
        "",
        "_Notes in no topic, grouped by area tag._",
        "",
    ]
    for key in sorted(by_area):
        lines.append(f"## {key}")
        for note_path in sorted(by_area[key]):
            lines.append(f"- [[{note_path}]]")
        lines.append("")
    body = "\n".join(lines).rstrip() + "\n"
    return frontmatter.dumps(frontmatter.Post(body, type="system", generated=True)) + "\n"


def _invert_tags(by_tag: dict[str, set[str]]) -> dict[str, set[str]]:
    """Invert ``{tag: {paths}}`` into ``{path: {tags}}`` for per-note area lookup."""
    out: dict[str, set[str]] = {}
    for tag, paths in by_tag.items():
        for path in paths:
            out.setdefault(path, set()).add(tag)
    return out


def _render_area_page(
    area: Area,
    topics_by_slug: dict[str, Topic],
    members_by_slug: dict[str, list[TopicMember]],
) -> str:
    """Render one per-area page: heading, description, its member topics."""
    lines = [f"# {area.label}", ""]
    if area.description:
        lines.extend([area.description, ""])
    lines.extend(["## Topics", ""])
    slugs = [slug for slug in sorted(area.topic_slugs) if slug in topics_by_slug]
    if slugs:
        for slug in slugs:
            topic = topics_by_slug[slug]
            count = len(members_by_slug.get(slug, []))
            lines.append(
                f"- [[{_TOPIC_LINK_PREFIX}/{slug}]] — {topic.label} ({count} notes)"
            )
    else:
        lines.append("_None yet._")
    lines.append("")
    body = "\n".join(lines).rstrip() + "\n"
    return frontmatter.dumps(frontmatter.Post(body, type="system", generated=True)) + "\n"


def _tags_base_view(area: Area) -> list[str]:
    """One Obsidian Bases table view (indented under the ``views:`` list)."""
    return [
        "  - type: table",
        f"    name: {area.label}",
        "    filters:",
        "      and:",
        '        - file.inFolder("Knowledge")',
        '        - file.ext == "md"',
        f'        - file.hasTag("area/{area.slug}")',
        "    order:",
        "      - file.name",
        "      - title",
        "      - tags",
        "      - source",
        "      - date_added",
        "      - summary",
        "    sort:",
        "      - property: date_added",
        "        direction: DESC",
    ]


def render_tags_base(areas: list[Area]) -> str:
    """Render the Obsidian Bases ``tags.base``: one table view per registry area.

    Built as a deterministic string template (no YAML writer dependency): each
    view filters ``Knowledge/`` markdown to a single ``area/<slug>`` tag.
    """
    lines = ["views:"]
    for area in areas:
        lines.extend(_tags_base_view(area))
    return "\n".join(lines) + "\n"


def _areas_table(areas: list[Area]) -> list[str]:
    """The ``## Areas`` registry table (slug | label | description | topics count)."""
    lines = [
        "## Areas",
        "",
        "| Slug | Label | Description | Topics |",
        "|------|-------|-------------|--------|",
    ]
    for area in areas:
        lines.append(
            f"| {area.slug} | {area.label} | {area.description} | "
            f"{len(area.topic_slugs)} |"
        )
    lines.append("")
    return lines


def _topics_table(
    topics: list[Topic], members_by_slug: dict[str, list[TopicMember]]
) -> list[str]:
    """The ``## Topics`` table (slug | label | area | kind/status | notes count)."""
    lines = [
        "## Topics",
        "",
        "| Slug | Label | Area | Kind/Status | Notes |",
        "|------|-------|------|-------------|-------|",
    ]
    for topic in sorted(topics, key=lambda t: t.slug):
        count = len(members_by_slug.get(topic.slug, []))
        lines.append(
            f"| {topic.slug} | {topic.label} | {topic.area or ''} | "
            f"{topic.kind}/{topic.status} | {count} |"
        )
    lines.append("")
    return lines


def _render_taxonomy_v2(
    areas: list[Area],
    topics: list[Topic],
    members_by_slug: dict[str, list[TopicMember]],
) -> str:
    """The generated ``_taxonomy.md`` v2 body: areas + topics registry + facets.

    The proposals block is spliced in via ``_splice_proposals`` (same markers as
    the pre-cutover path), so ``render_topics`` keeps maintaining it in place.
    """
    lines = [
        "# Knowledge Base Taxonomy",
        "",
        _TAXONOMY_INTRO,
        "",
        *_areas_table(areas),
        *_topics_table(topics, members_by_slug),
        "## Facets",
        "",
        *_FACETS,
        "",
    ]
    body = "\n".join(lines).rstrip() + "\n"
    doc = frontmatter.dumps(
        frontmatter.Post(body, type="taxonomy", version="generated", status="active")
    ) + "\n"
    return _splice_proposals(doc, _render_proposals_block(topics, members_by_slug))


def _render_proposals_block(
    topics: list[Topic], members_by_slug: dict[str, list[TopicMember]]
) -> str:
    """Render the proposals table body (between markers, excluding the markers)."""
    proposed = sorted(
        (t for t in topics if t.kind == "discovered" and t.status == "proposed"),
        key=lambda t: t.slug,
    )
    lines = [
        "_Discovered topics awaiting review. Regenerated by `kb-engine topics render`._",
        "",
        "| Slug | Keywords | Size |",
        "|------|----------|------|",
    ]
    for topic in proposed:
        keywords = ", ".join(topic.keywords)
        size = len(members_by_slug.get(topic.slug, []))
        lines.append(f"| {topic.slug} | {keywords} | {size} |")
    return "\n".join(lines)


def _strip_markers(text: str) -> str:
    """Remove every stray START/END marker line, collapsing the blank gap left.

    Used to recover from a malformed taxonomy (lone, out-of-order, or duplicate
    markers) before a clean block is re-appended.
    """
    stripped = re.sub(
        rf"[ \t]*(?:{re.escape(PROPOSALS_START)}|{re.escape(PROPOSALS_END)})[ \t]*\n?",
        "",
        text,
    )
    return re.sub(r"\n{3,}", "\n\n", stripped)


def _splice_proposals(existing_text: str, block_body: str) -> str:
    """Replace content between the proposal markers, preserving the rest.

    Only a *well-formed* pair (a START followed by an END) is spliced in place.
    Any malformed state — lone marker, END-before-START, or duplicates — is
    repaired by stripping every stray marker, then appending a single fresh
    block. This keeps the result a single well-formed block and idempotent.
    """
    marked = f"{PROPOSALS_START}\n{block_body}\n{PROPOSALS_END}"
    start = existing_text.find(PROPOSALS_START)
    end = existing_text.find(PROPOSALS_END)
    well_formed = (
        start != -1
        and end != -1
        and start < end
        and existing_text.count(PROPOSALS_START) == 1
        and existing_text.count(PROPOSALS_END) == 1
    )
    if well_formed:
        pattern = re.compile(
            re.escape(PROPOSALS_START) + r".*?" + re.escape(PROPOSALS_END),
            re.DOTALL,
        )
        return pattern.sub(lambda _: marked, existing_text, count=1)

    base = _strip_markers(existing_text).rstrip("\n")
    section = f"## Proposals\n\n{marked}\n"
    if base:
        return f"{base}\n\n{section}"
    return section


def _write_proposals(
    taxonomy_path: Path,
    topics: list[Topic],
    members_by_slug: dict[str, list[TopicMember]],
) -> None:
    block_body = _render_proposals_block(topics, members_by_slug)
    if taxonomy_path.exists():
        existing = taxonomy_path.read_text()
    else:
        existing = "# Knowledge Base Taxonomy\n"
    taxonomy_path.write_text(_splice_proposals(existing, block_body))


def _write_mocs(
    topics_dir: Path,
    vault_resolved: Path,
    topics_dir_resolved: Path,
    topics: list[Topic],
    members_by_slug: dict[str, list[TopicMember]],
) -> list[str]:
    """Write each topic MOC (traversal-guarded); return vault-relative posix paths."""
    topic_paths: list[str] = []
    for topic in topics:
        moc_path = (topics_dir / f"{topic.slug}.md").resolve()
        # Defense-in-depth: a malicious slug (bypassing input validation) must
        # never write outside _system/topics/. Skip rather than write.
        if not moc_path.is_relative_to(topics_dir_resolved):
            continue
        moc_path.write_text(
            _render_topic_moc(topic, members_by_slug.get(topic.slug, []))
        )
        # Vault-relative posix (Phase 3 contract: consistent with note paths).
        topic_paths.append(moc_path.relative_to(vault_resolved).as_posix())
    return topic_paths


def _render_pre_cutover(
    store: Store,
    vault_path: Path,
    topics_dir: Path,
    topics: list[Topic],
    members_by_slug: dict[str, list[TopicMember]],
) -> str:
    """Today's behavior: by-category unfiled index + proposals spliced in place."""
    (topics_dir / "_unfiled-by-category.md").write_text(
        _render_unfiled_by_category(store.notes_without_topic())
    )
    taxonomy_path = vault_path / _TAXONOMY_RELPATH
    taxonomy_path.parent.mkdir(parents=True, exist_ok=True)
    _write_proposals(taxonomy_path, topics, members_by_slug)
    return (_TOPICS_RELDIR / "_unfiled-by-category.md").as_posix()


def _render_post_cutover(
    store: Store,
    vault_path: Path,
    topics_dir: Path,
    areas: list[Area],
    topics: list[Topic],
    members_by_slug: dict[str, list[TopicMember]],
) -> tuple[str, list[str], str]:
    """v2 artifacts: area pages, unfiled-by-area, taxonomy registry, tags.base."""
    topics_by_slug = _topics_by_slug(topics)
    area_paths: list[str] = []
    for area in areas:
        (topics_dir / f"area-{area.slug}.md").write_text(
            _render_area_page(area, topics_by_slug, members_by_slug)
        )
        area_paths.append((_TOPICS_RELDIR / f"area-{area.slug}.md").as_posix())

    (topics_dir / "_unfiled-by-area.md").write_text(
        _render_unfiled_by_area(
            store.notes_without_topic(), _invert_tags(store.notes_by_tag())
        )
    )
    # One-time cleanup: the retired by-category index is deleted post-cutover.
    (topics_dir / "_unfiled-by-category.md").unlink(missing_ok=True)

    taxonomy_path = vault_path / _TAXONOMY_RELPATH
    taxonomy_path.parent.mkdir(parents=True, exist_ok=True)
    taxonomy_path.write_text(_render_taxonomy_v2(areas, topics, members_by_slug))

    tags_base_path = vault_path / _TAGS_BASE_RELPATH
    tags_base_path.parent.mkdir(parents=True, exist_ok=True)
    tags_base_path.write_text(render_tags_base(areas))

    return (
        (_TOPICS_RELDIR / "_unfiled-by-area.md").as_posix(),
        area_paths,
        _TAGS_BASE_RELPATH.as_posix(),
    )


def render_topics(store: Store, vault_path: Path) -> RenderResult:
    """Render topic/area MOCs to ``_system/topics/`` + the ``_taxonomy.md`` registry.

    Render-not-append and idempotent (no timestamps, deterministic ordering).
    Gated on the areas registry: with **no areas seeded** it behaves exactly as
    pre-cutover (by-category unfiled index, proposals-splice-only taxonomy, no
    tags.base / area pages — the human taxonomy file is never nuked). Once areas
    are seeded it emits the v2 artifacts. ``_system/topics/`` lives outside
    ``Knowledge/`` so those files are never embedded.
    """
    topics = store.load_topics()
    areas = store.load_areas()
    members_by_slug = {
        topic.slug: store.topic_members(topic.slug) for topic in topics
    }

    vault_resolved = vault_path.resolve()
    topics_dir = vault_path / _TOPICS_RELDIR
    topics_dir.mkdir(parents=True, exist_ok=True)
    topics_dir_resolved = topics_dir.resolve()

    (topics_dir / "index.md").write_text(
        _render_index(areas, topics, members_by_slug)
    )
    topic_paths = _write_mocs(
        topics_dir, vault_resolved, topics_dir_resolved, topics, members_by_slug
    )

    if areas:
        unfiled_relpath, area_paths, tags_base_path = _render_post_cutover(
            store, vault_path, topics_dir, areas, topics, members_by_slug
        )
    else:
        unfiled_relpath = _render_pre_cutover(
            store, vault_path, topics_dir, topics, members_by_slug
        )
        area_paths, tags_base_path = [], ""

    return RenderResult(
        n_topics=len(topics),
        n_areas=len(areas),
        index_path=_TOPICS_RELDIR.joinpath("index.md").as_posix(),
        topic_paths=tuple(topic_paths),
        taxonomy_path=_TAXONOMY_RELPATH.as_posix(),
        unfiled_path=unfiled_relpath,
        area_paths=tuple(area_paths),
        tags_base_path=tags_base_path,
    )
