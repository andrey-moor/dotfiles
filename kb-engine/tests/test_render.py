import numpy as np

from kb_engine.models import Area, Topic, TopicMember
from kb_engine.store import Store
from kb_engine.topics.areas_registry import seed_areas
from kb_engine.topics.render import (
    PROPOSALS_END,
    PROPOSALS_START,
    RenderResult,
    _one_liner,
    _render_topic_moc,
    _render_unfiled_by_area,
    _render_unfiled_by_category,
    _splice_proposals,
    render_tags_base,
    render_topics,
)


def _store_with_topics(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    # two notes per rust topic, one for llm
    for path in ("Knowledge/a.md", "Knowledge/b.md", "Knowledge/c.md"):
        s.upsert_note(path=path, title=path, sha256="h", tags=[])
    rust = Topic(
        slug="rust-macros",
        label="Rust Macros",
        keywords=("rust", "macros", "borrow"),
        centroid=np.array([1, 0, 0], np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics(
        [rust],
        {
            "rust-macros": [
                TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto"),
                TopicMember(note_path="Knowledge/b.md", score=0.7, source="auto"),
            ],
        },
    )
    # manual topic added separately so save_topics doesn't drop it
    s.add_manual_topic("llm", "Llm Prompt", "llm prompt", np.array([0, 1, 0], np.float32))
    s.set_members(
        "llm", [TopicMember(note_path="Knowledge/c.md", score=0.8, source="auto")]
    )
    # No areas seeded here → the pre-cutover world (render keeps today's behavior).
    return s


def _store_with_areas(tmp_path):
    """Post-cutover fixture: the topics store plus a seeded area registry.

    ``ai`` owns both topics (membership composed from ``topics.area``). Tests
    that need the pre-cutover (no-areas) world use ``_store_with_topics``.
    """
    s = _store_with_topics(tmp_path)
    s.save_areas(
        [Area(slug="ai", label="AI", topic_slugs=(), description="LLMs and agents")]
    )
    s.set_topic_area("rust-macros", "ai")
    s.set_topic_area("llm", "ai")
    return s


def test_render_writes_topic_and_area_mocs_idempotently(tmp_path):
    s = _store_with_topics(tmp_path)
    out = render_topics(s, vault_path=tmp_path)
    assert isinstance(out, RenderResult)
    index = tmp_path / "_system" / "topics" / "index.md"
    moc = index.read_text()
    assert "rust" in moc.lower()
    # wikilinks to per-topic MOCs use the _system/topics/<slug> target
    assert "[[_system/topics/rust-macros]]" in moc
    before = index.read_text()
    render_topics(s, vault_path=tmp_path)
    assert index.read_text() == before  # idempotent — no timestamps in body


def test_render_index_has_system_frontmatter(tmp_path):
    s = _store_with_topics(tmp_path)
    render_topics(s, vault_path=tmp_path)
    import frontmatter

    post = frontmatter.load(tmp_path / "_system" / "topics" / "index.md")
    assert post["type"] == "system"
    assert post["generated"] is True


def test_render_topic_moc_lists_members_sorted_by_score(tmp_path):
    s = _store_with_topics(tmp_path)
    render_topics(s, vault_path=tmp_path)
    moc = (tmp_path / "_system" / "topics" / "rust-macros.md").read_text()
    assert "## Notes" in moc
    assert "[[Knowledge/a.md]]" in moc
    assert "[[Knowledge/b.md]]" in moc
    # higher score (a, 0.9) listed before lower (b, 0.7)
    assert moc.index("Knowledge/a.md") < moc.index("Knowledge/b.md")
    # keywords + kind/status surfaced
    assert "rust" in moc and "macros" in moc
    assert "proposed" in moc


def test_render_topic_moc_idempotent(tmp_path):
    s = _store_with_topics(tmp_path)
    render_topics(s, vault_path=tmp_path)
    moc_path = tmp_path / "_system" / "topics" / "rust-macros.md"
    before = moc_path.read_text()
    render_topics(s, vault_path=tmp_path)
    assert moc_path.read_text() == before


def test_render_proposals_replaces_only_between_markers(tmp_path):
    s = _store_with_topics(tmp_path)
    sysdir = tmp_path / "_system"
    sysdir.mkdir(parents=True, exist_ok=True)
    taxonomy = sysdir / "_taxonomy.md"
    taxonomy.write_text(
        "# Taxonomy\n\n"
        "## Categories\n- **Dev/Rust** — rust\n\n"
        "## Proposals\n\n"
        f"{PROPOSALS_START}\n"
        "OLD CONTENT TO BE REPLACED\n"
        f"{PROPOSALS_END}\n\n"
        "## Deprecated\nkeep me\n"
    )
    render_topics(s, vault_path=tmp_path)
    text = taxonomy.read_text()
    # surrounding content preserved
    assert "## Categories" in text
    assert "- **Dev/Rust** — rust" in text
    assert "## Deprecated\nkeep me" in text
    # old proposal content gone, only the proposed (discovered) topic rendered
    assert "OLD CONTENT TO BE REPLACED" not in text
    assert "rust-macros" in text
    # manual/active topic is NOT a proposal
    block = text.split(PROPOSALS_START)[1].split(PROPOSALS_END)[0]
    assert "llm" not in block
    # markers preserved exactly once
    assert text.count(PROPOSALS_START) == 1 and text.count(PROPOSALS_END) == 1


def test_render_proposals_creates_block_when_absent(tmp_path):
    s = _store_with_topics(tmp_path)
    sysdir = tmp_path / "_system"
    sysdir.mkdir(parents=True, exist_ok=True)
    taxonomy = sysdir / "_taxonomy.md"
    taxonomy.write_text("# Taxonomy\n\n## Categories\n- **Dev/Rust** — rust\n")
    render_topics(s, vault_path=tmp_path)
    text = taxonomy.read_text()
    assert PROPOSALS_START in text and PROPOSALS_END in text
    assert "## Categories" in text  # original preserved
    assert "rust-macros" in text


def _well_formed_single_block(text: str) -> bool:
    """Exactly one START and one END, START before END (a single clean block)."""
    return (
        text.count(PROPOSALS_START) == 1
        and text.count(PROPOSALS_END) == 1
        and text.index(PROPOSALS_START) < text.index(PROPOSALS_END)
    )


def test_splice_only_start_marker_produces_single_block():
    out = _splice_proposals(f"# Tax\n\n{PROPOSALS_START}\nleftover\n", "BODY")
    # A lone START is stripped (no dangling marker) and a fresh block appended.
    assert _well_formed_single_block(out)
    assert "BODY" in out
    assert PROPOSALS_START not in out.split("## Proposals")[0]  # no orphan marker


def test_splice_only_end_marker_produces_single_block():
    out = _splice_proposals(f"# Tax\n\nstray\n{PROPOSALS_END}\nafter\n", "BODY")
    assert _well_formed_single_block(out)
    assert "BODY" in out


def test_splice_end_before_start_produces_single_block():
    text = f"# Tax\n\n{PROPOSALS_END}\nmiddle\n{PROPOSALS_START}\n"
    out = _splice_proposals(text, "BODY")
    assert _well_formed_single_block(out)
    assert "BODY" in out


def test_splice_duplicate_markers_produces_single_block():
    text = (
        f"# Tax\n\n{PROPOSALS_START}\nA\n{PROPOSALS_END}\n"
        f"\n{PROPOSALS_START}\nB\n{PROPOSALS_END}\n"
    )
    out = _splice_proposals(text, "BODY")
    assert _well_formed_single_block(out)
    assert "BODY" in out


def test_splice_malformed_is_idempotent_on_second_pass():
    # First splice repairs the malformed markers; a second splice with the same
    # body must be a no-op (render-not-append guarantee holds after repair).
    for text in (
        f"# Tax\n\n{PROPOSALS_START}\nleftover\n",
        f"# Tax\n\nstray\n{PROPOSALS_END}\n",
        f"# Tax\n\n{PROPOSALS_END}\nmiddle\n{PROPOSALS_START}\n",
        f"# Tax\n\n{PROPOSALS_START}\nA\n{PROPOSALS_END}\n{PROPOSALS_START}\nB\n{PROPOSALS_END}\n",
    ):
        once = _splice_proposals(text, "BODY")
        twice = _splice_proposals(once, "BODY")
        assert twice == once
        assert _well_formed_single_block(twice)


def test_render_malformed_markers_repaired_and_idempotent(tmp_path):
    # End-to-end through render_topics: a _taxonomy.md with a lone START marker is
    # repaired to a single well-formed block, and a second render is a no-op.
    s = _store_with_topics(tmp_path)
    sysdir = tmp_path / "_system"
    sysdir.mkdir(parents=True, exist_ok=True)
    taxonomy = sysdir / "_taxonomy.md"
    taxonomy.write_text(
        f"# Taxonomy\n\n## Categories\n- keep\n\n{PROPOSALS_START}\nDANGLING\n"
    )
    render_topics(s, vault_path=tmp_path)
    first = taxonomy.read_text()
    assert _well_formed_single_block(first)  # dangling START repaired
    assert "## Categories" in first and "- keep" in first
    assert "rust-macros" in first
    render_topics(s, vault_path=tmp_path)
    assert taxonomy.read_text() == first  # idempotent after repair


def test_render_proposals_idempotent_with_existing_block(tmp_path):
    s = _store_with_topics(tmp_path)
    sysdir = tmp_path / "_system"
    sysdir.mkdir(parents=True, exist_ok=True)
    taxonomy = sysdir / "_taxonomy.md"
    taxonomy.write_text("# Taxonomy\n\n## Categories\n- **Dev/Rust** — rust\n")
    render_topics(s, vault_path=tmp_path)
    once = taxonomy.read_text()
    render_topics(s, vault_path=tmp_path)
    assert taxonomy.read_text() == once  # second render is a no-op


def test_render_creates_taxonomy_if_missing(tmp_path):
    # When _taxonomy.md doesn't exist at all, render creates a minimal one with
    # the proposals block (so the proposal table always has a home).
    s = _store_with_topics(tmp_path)
    render_topics(s, vault_path=tmp_path)
    taxonomy = tmp_path / "_system" / "_taxonomy.md"
    assert taxonomy.exists()
    assert PROPOSALS_START in taxonomy.read_text()


def test_render_skips_traversal_slug_never_writes_outside_topics_dir(tmp_path):
    # Defense-in-depth: even if a malicious slug reaches the DB (bypassing input
    # validation, e.g. a stale row), render must never write a MOC outside
    # _system/topics/.
    vault = tmp_path / "vault"
    vault.mkdir()
    s = Store(vault / "t.db")
    s.init_schema()
    # craft a topic row directly so the slug bypasses add_manual_topic validation
    s._conn.execute(
        "INSERT INTO topics(slug, label, keywords, centroid, kind, status) "
        "VALUES(?, ?, ?, ?, 'discovered', 'proposed')",
        ("../../escape", "Escape", "[]", np.array([1, 0, 0], np.float32).tobytes()),
    )
    s._conn.commit()
    out = render_topics(s, vault_path=vault)
    # the escaping file must not exist anywhere outside the topics dir
    assert not (tmp_path / "escape.md").exists()
    assert not (vault.parent / "escape.md").exists()
    assert not (vault / "escape.md").exists()
    # and it must not appear in the reported topic paths
    assert all("escape" not in p for p in out.topic_paths)


def test_render_result_paths_are_vault_relative(tmp_path):
    # Phase 3 contract: RenderResult paths are vault-relative posix strings
    # (consistent with note paths), not absolute filesystem paths.
    s = _store_with_topics(tmp_path)
    out = render_topics(s, vault_path=tmp_path)
    assert out.index_path == "_system/topics/index.md"
    assert out.taxonomy_path == "_system/_taxonomy.md"
    assert "_system/topics/rust-macros.md" in out.topic_paths
    assert out.unfiled_path == "_system/topics/_unfiled-by-category.md"
    # all paths relative (no leading slash, no tmp_path prefix)
    for p in [out.index_path, out.taxonomy_path, out.unfiled_path, *out.topic_paths]:
        assert not p.startswith("/")
        assert str(tmp_path) not in p


def test_render_result_topic_paths_is_tuple(tmp_path):
    s = _store_with_topics(tmp_path)
    out = render_topics(s, vault_path=tmp_path)
    assert isinstance(out.topic_paths, tuple)


def test_render_zero_topics(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    out = render_topics(s, vault_path=tmp_path)
    assert out.n_topics == 0
    index = tmp_path / "_system" / "topics" / "index.md"
    assert index.exists()  # an empty index is still written


def test_topic_moc_splits_primary_and_secondary():
    topic = Topic(slug="rust", label="Rust", keywords=("rust",),
                  centroid=np.ones(8, np.float32), kind="manual", status="active")
    members = [
        TopicMember("Knowledge/p.md", 0.9, "auto", is_primary=True),
        TopicMember("Knowledge/s.md", 0.6, "auto", is_primary=False),
    ]
    out = _render_topic_moc(topic, members, {})
    assert "## Notes" in out and "## Also relevant" in out
    notes_block, also_block = out.split("## Also relevant", 1)
    assert "[[Knowledge/p.md]]" in notes_block and "[[Knowledge/p.md]]" not in also_block
    assert "[[Knowledge/s.md]]" in also_block and "[[Knowledge/s.md]]" not in notes_block


def test_topic_moc_omits_also_relevant_when_no_secondaries():
    topic = Topic(slug="rust", label="Rust", keywords=("rust",),
                  centroid=np.ones(8, np.float32), kind="manual", status="active")
    members = [TopicMember("Knowledge/p.md", 0.9, "auto", is_primary=True)]
    out = _render_topic_moc(topic, members, {})
    assert "## Notes" in out
    assert "## Also relevant" not in out  # no secondary members → section omitted


def test_topic_moc_all_secondary_omits_empty_notes_section():
    # A topic whose every member is secondary (each note's home is elsewhere)
    # must not render a misleading empty "## Notes" beside real cross-links.
    topic = Topic(slug="rust", label="Rust", keywords=("rust",),
                  centroid=np.ones(8, np.float32), kind="manual", status="active")
    members = [
        TopicMember("Knowledge/s1.md", 0.8, "auto", is_primary=False),
        TopicMember("Knowledge/s2.md", 0.6, "auto", is_primary=False),
    ]
    out = _render_topic_moc(topic, members, {})
    assert "## Also relevant" in out
    assert "[[Knowledge/s1.md]]" in out and "[[Knowledge/s2.md]]" in out
    assert "## Notes" not in out  # no primary members → no Notes section at all


# --- MOC v3: summary one-liners + collapsed details block --------------------


def _moc_topic() -> Topic:
    return Topic(
        slug="rust", label="Rust", keywords=("rust", "macros"),
        centroid=np.ones(4, np.float32), kind="manual", status="active",
    )


def test_one_liner_takes_first_sentence():
    assert _one_liner("First sentence. Second sentence.") == "First sentence"


def test_one_liner_exact_120_gets_no_marker():
    sentence = "x" * 120
    assert _one_liner(sentence) == sentence  # exactly at the cap → no marker


def test_one_liner_over_120_truncates_with_marker():
    out = _one_liner("y" * 121)
    assert out == "y" * 120 + "…"  # capped at 120 chars, … appended
    assert len(out) == 121


def test_topic_moc_member_line_shows_summary_one_liner_or_link_only():
    members = [
        TopicMember("Knowledge/withsum.md", 0.9, "auto", is_primary=True),
        TopicMember("Knowledge/nosum.md", 0.7, "auto", is_primary=True),
    ]
    summaries = {"Knowledge/withsum.md": "A crisp gist. More detail here."}
    out = _render_topic_moc(_moc_topic(), members, summaries)
    # member WITH a summary → "[[path]] — first sentence"
    assert "- [[Knowledge/withsum.md]] — A crisp gist" in out
    # member WITHOUT a summary → link only, no dash
    assert "- [[Knowledge/nosum.md]]\n" in out
    assert "[[Knowledge/nosum.md]] —" not in out


def test_topic_moc_scores_and_keywords_live_in_details_not_body():
    members = [
        TopicMember("Knowledge/p.md", 0.87, "auto", is_primary=True),
        TopicMember("Knowledge/s.md", 0.42, "auto", is_primary=False),
    ]
    summaries = {"Knowledge/p.md": "Primary gist.", "Knowledge/s.md": "Secondary gist."}
    out = _render_topic_moc(_moc_topic(), members, summaries)
    body, sep, details = out.partition("<details>")
    assert sep == "<details>"  # the collapsed block exists
    # scores moved out of the member lines into the details block
    assert "0.87" not in body and "0.42" not in body
    assert "0.87" in details and "0.42" in details
    # metadata line: slug · kind/status · anchor (anchor_source default "label")
    assert "- slug: `rust` · kind/status: manual/active · anchor: label" in details
    # labeled keywords line + the secondary marker both live in details
    assert "- keywords: rust, macros" in details
    assert "s.md 0.42 (secondary)" in details
    # body keeps section headers + the summary one-liner
    assert "## Notes" in body and "## Also relevant" in body
    assert "- [[Knowledge/p.md]] — Primary gist" in body


def test_topic_moc_render_is_deterministic():
    members = [
        TopicMember("Knowledge/p.md", 0.9, "auto", is_primary=True),
        TopicMember("Knowledge/s.md", 0.6, "auto", is_primary=False),
    ]
    summaries = {"Knowledge/p.md": "Gist p.", "Knowledge/s.md": "Gist s."}
    first = _render_topic_moc(_moc_topic(), members, summaries)
    assert first == _render_topic_moc(_moc_topic(), members, summaries)


def test_unfiled_by_category_groups_by_taxonomy_tag():
    out = _render_unfiled_by_category({
        "Knowledge/b.md": ["AI/Agents"],
        "Knowledge/c.md": ["AI/Agents", "Dev/Tools"],
    })
    assert "## AI/Agents" in out and "## Dev/Tools" in out
    assert "[[Knowledge/b.md]]" in out and "[[Knowledge/c.md]]" in out
    # the multi-tag note appears under BOTH of its tag sections
    ai_section = out.split("## AI/Agents")[1].split("##")[0]
    tools_section = out.split("## Dev/Tools")[1].split("##")[0]
    assert "[[Knowledge/c.md]]" in ai_section
    assert "[[Knowledge/c.md]]" in tools_section


def test_unfiled_by_category_untagged_fallback():
    out = _render_unfiled_by_category({"Knowledge/orphan.md": []})
    assert "## (untagged)" in out
    assert "[[Knowledge/orphan.md]]" in out


def test_render_writes_unfiled_by_category_file(tmp_path):
    # render_topics must emit the by-category index file (deterministic/idempotent).
    s = _store_with_topics(tmp_path)  # existing helper; its notes are all filed
    s.upsert_note(path="Knowledge/lonely.md", title="Lonely", sha256="h", tags=["Personal/Cooking"])
    render_topics(s, vault_path=tmp_path)
    by_cat = tmp_path / "_system" / "topics" / "_unfiled-by-category.md"
    assert by_cat.exists()
    text = by_cat.read_text()
    assert "## Personal/Cooking" in text and "[[Knowledge/lonely.md]]" in text
    before = by_cat.read_text()
    render_topics(s, vault_path=tmp_path)
    assert by_cat.read_text() == before  # idempotent


# --- v2 (post-cutover, areas registry seeded) --------------------------------


def test_render_no_areas_preserves_human_taxonomy(tmp_path):
    # The gate: with NO areas seeded, render behaves exactly as today. The human
    # _taxonomy.md is preserved (proposals-splice only), and none of the v2
    # artifacts (tags.base, area pages, unfiled-by-area) are produced.
    s = _store_with_topics(tmp_path)  # no areas
    sysdir = tmp_path / "_system"
    sysdir.mkdir(parents=True, exist_ok=True)
    (sysdir / "_taxonomy.md").write_text(
        "# Knowledge Base Taxonomy\n\n## Categories\n### AI\n"
        "- **AI/LLMs** — Large language models\n"
    )
    out = render_topics(s, vault_path=tmp_path)
    text = (sysdir / "_taxonomy.md").read_text()
    # human content preserved — NOT regenerated into the v2 registry body
    assert "## Categories" in text
    assert "- **AI/LLMs** — Large language models" in text
    assert "## Areas" not in text  # v2 registry header absent
    # proposals still spliced in
    assert PROPOSALS_START in text and "rust-macros" in text
    # v2 artifacts NOT produced
    assert not (tmp_path / "Knowledge" / "tags.base").exists()
    assert not (tmp_path / "_system" / "topics" / "area-ai.md").exists()
    assert out.area_paths == ()
    assert out.tags_base_path == ""
    # old-path unfiled file, not by-area
    assert out.unfiled_path == "_system/topics/_unfiled-by-category.md"
    assert (tmp_path / "_system" / "topics" / "_unfiled-by-category.md").exists()
    assert not (tmp_path / "_system" / "topics" / "_unfiled-by-area.md").exists()


def test_render_v2_taxonomy_has_areas_and_topics_tables(tmp_path):
    import frontmatter

    s = _store_with_areas(tmp_path)
    render_topics(s, vault_path=tmp_path)
    text = (tmp_path / "_system" / "_taxonomy.md").read_text()
    # generated frontmatter marks it a taxonomy registry
    post = frontmatter.loads(text)
    assert post["type"] == "taxonomy"
    assert post["version"] == "generated"
    assert post["status"] == "active"
    # Areas table: slug | label | description | topics count
    assert "## Areas" in text
    assert "| ai | AI | LLMs and agents | 2 |" in text
    # Topics table carries the area column (slug | label | area | kind/status | notes)
    assert "## Topics" in text
    assert "| rust-macros | Rust Macros | ai | discovered/proposed | 2 |" in text
    # Facets section — the four hardcoded facet tags
    assert "## Facets" in text
    assert "**Tutorials**" in text and "**Tools**" in text
    # proposals splice block still present; the discovered topic is listed there
    assert PROPOSALS_START in text and PROPOSALS_END in text
    block = text.split(PROPOSALS_START)[1].split(PROPOSALS_END)[0]
    assert "rust-macros" in block


def test_render_v2_taxonomy_idempotent(tmp_path):
    s = _store_with_areas(tmp_path)
    render_topics(s, vault_path=tmp_path)
    taxonomy = tmp_path / "_system" / "_taxonomy.md"
    once = taxonomy.read_text()
    render_topics(s, vault_path=tmp_path)
    assert taxonomy.read_text() == once  # regenerated deterministically


def test_render_v2_writes_area_pages(tmp_path):
    s = _store_with_areas(tmp_path)
    out = render_topics(s, vault_path=tmp_path)
    page = tmp_path / "_system" / "topics" / "area-ai.md"
    assert page.exists()
    text = page.read_text()
    assert "# AI" in text
    assert "LLMs and agents" in text  # description
    assert "[[_system/topics/rust-macros]] — Rust Macros (2 notes)" in text
    assert out.area_paths == ("_system/topics/area-ai.md",)


def test_render_v2_empty_area_page_says_none_yet(tmp_path):
    # Every registry area gets a page, even ones with no topics assigned.
    s = _store_with_topics(tmp_path)
    seed_areas(s)  # 9 registry areas, no topic assigned to any of them
    render_topics(s, vault_path=tmp_path)
    page = (tmp_path / "_system" / "topics" / "area-gamedev.md").read_text()
    assert "# GameDev" in page
    assert "_None yet._" in page


def test_render_v2_index_links_area_pages(tmp_path):
    s = _store_with_areas(tmp_path)
    render_topics(s, vault_path=tmp_path)
    index = (tmp_path / "_system" / "topics" / "index.md").read_text()
    assert "## [[_system/topics/area-ai|AI]]" in index


def test_render_v2_unfiled_by_area_groups_by_area_tag(tmp_path):
    s = _store_with_areas(tmp_path)
    # two topicless notes: one area-tagged, one bare
    s.upsert_note(path="Knowledge/dev-note.md", title="Dev", sha256="h", tags=["area/dev"])
    s.upsert_note(path="Knowledge/orphan.md", title="Orphan", sha256="h", tags=[])
    out = render_topics(s, vault_path=tmp_path)
    by_area = (tmp_path / "_system" / "topics" / "_unfiled-by-area.md").read_text()
    assert "## area/dev" in by_area and "[[Knowledge/dev-note.md]]" in by_area
    assert "## (no area)" in by_area and "[[Knowledge/orphan.md]]" in by_area
    assert out.unfiled_path == "_system/topics/_unfiled-by-area.md"
    before = by_area
    render_topics(s, vault_path=tmp_path)
    assert (tmp_path / "_system" / "topics" / "_unfiled-by-area.md").read_text() == before


def test_render_v2_removes_old_unfiled_by_category(tmp_path):
    # One-time cleanup: the retired _unfiled-by-category.md is deleted when present.
    s = _store_with_areas(tmp_path)
    topics_dir = tmp_path / "_system" / "topics"
    topics_dir.mkdir(parents=True, exist_ok=True)
    stale = topics_dir / "_unfiled-by-category.md"
    stale.write_text("# stale\n")
    render_topics(s, vault_path=tmp_path)
    assert not stale.exists()
    assert (topics_dir / "_unfiled-by-area.md").exists()


def test_render_v2_writes_tags_base_with_nine_views(tmp_path):
    s = _store_with_topics(tmp_path)
    seed_areas(s)  # 9 registry areas
    out = render_topics(s, vault_path=tmp_path)
    base_path = tmp_path / "Knowledge" / "tags.base"
    assert base_path.exists()
    base = base_path.read_text()
    assert base.count("- type: table") == 9  # one view per area
    assert 'file.hasTag("area/ai")' in base
    assert 'file.inFolder("Knowledge")' in base
    assert out.tags_base_path == "Knowledge/tags.base"


def test_render_tags_base_view_format():
    out = render_tags_base(
        [Area(slug="ai", label="AI", topic_slugs=(), description="x")]
    )
    assert out.startswith("views:\n")
    assert "  - type: table" in out
    assert "    name: AI" in out
    assert '        - file.inFolder("Knowledge")' in out
    assert '        - file.ext == "md"' in out
    assert '        - file.hasTag("area/ai")' in out
    assert "      - property: date_added" in out
    assert "        direction: DESC" in out


def test_unfiled_by_area_groups_by_area_tag():
    out = _render_unfiled_by_area(
        {"Knowledge/x.md": ["area/dev"], "Knowledge/y.md": []},
        {"Knowledge/x.md": {"area/dev", "Tutorials"}},
    )
    assert "## area/dev" in out and "[[Knowledge/x.md]]" in out
    assert "## (no area)" in out and "[[Knowledge/y.md]]" in out


def test_unfiled_by_area_frontmatter_is_system():
    import frontmatter

    post = frontmatter.loads(
        _render_unfiled_by_area({"Knowledge/x.md": []}, {})
    )
    assert post["type"] == "system"
    assert post["generated"] is True
