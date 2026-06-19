import numpy as np

from kb_engine.models import Area, Topic, TopicMember
from kb_engine.store import Store
from kb_engine.topics.render import (
    PROPOSALS_END,
    PROPOSALS_START,
    RenderResult,
    _render_topic_moc,
    _splice_proposals,
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
    s.save_areas([Area(slug="ai", label="AI", topic_slugs=("rust-macros", "llm"))])
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
    # all paths relative (no leading slash, no tmp_path prefix)
    for p in [out.index_path, out.taxonomy_path, *out.topic_paths]:
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
    out = _render_topic_moc(topic, members)
    assert "## Notes" in out and "## Also relevant" in out
    notes_block, also_block = out.split("## Also relevant", 1)
    assert "[[Knowledge/p.md]]" in notes_block and "[[Knowledge/p.md]]" not in also_block
    assert "[[Knowledge/s.md]]" in also_block and "[[Knowledge/s.md]]" not in notes_block


def test_topic_moc_omits_also_relevant_when_no_secondaries():
    topic = Topic(slug="rust", label="Rust", keywords=("rust",),
                  centroid=np.ones(8, np.float32), kind="manual", status="active")
    members = [TopicMember("Knowledge/p.md", 0.9, "auto", is_primary=True)]
    out = _render_topic_moc(topic, members)
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
    out = _render_topic_moc(topic, members)
    assert "## Also relevant" in out
    assert "[[Knowledge/s1.md]]" in out and "[[Knowledge/s2.md]]" in out
    assert "## Notes" not in out  # no primary members → no Notes section at all
