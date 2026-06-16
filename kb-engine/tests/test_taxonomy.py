from kb_engine.topics.taxonomy import (
    TaxonomyDiff,
    diff_taxonomy,
    parse_taxonomy_tags,
)


def test_parse_taxonomy_tags(tmp_path):
    f = tmp_path / "_taxonomy.md"
    f.write_text("# Taxonomy\n## Categories\n- AI/RAG — retrieval\n- Dev/Rust — rust\n")
    tags = parse_taxonomy_tags(f)
    assert "AI/RAG" in tags and "Dev/Rust" in tags


def test_parse_taxonomy_tags_real_bold_format(tmp_path):
    # The real _taxonomy.md bolds tags: "- **AI/LLMs** — description".
    f = tmp_path / "_taxonomy.md"
    f.write_text(
        "## Categories\n"
        "### AI\n"
        "- **AI/LLMs** — Large language models\n"
        "- **AI/RAG** — Retrieval augmented generation\n"
        "### GameDev\n"
        "- **GameDev** — Game development\n"
        "## Cross-cutting Tags\n"
        "- **Tutorials** — Step-by-step how-to content\n"
    )
    tags = parse_taxonomy_tags(f)
    assert "AI/LLMs" in tags
    assert "AI/RAG" in tags
    # single-word bolded list tags are captured too
    assert "GameDev" in tags
    assert "Tutorials" in tags


def test_parse_taxonomy_tags_ignores_prose(tmp_path):
    # Prose mentioning a slash (e.g. "Category/Subcategory") must not be captured
    # as a tag; only list items and bold tokens count.
    f = tmp_path / "_taxonomy.md"
    f.write_text(
        "Tags use two-level format: `Category/Subcategory`.\n"
        "## Categories\n"
        "- **Dev/Rust** — rust\n"
    )
    tags = parse_taxonomy_tags(f)
    assert "Dev/Rust" in tags
    assert "Category/Subcategory" not in tags


def test_diff_taxonomy_maps_existing_to_topics():
    # existing tag -> set of note paths; topic -> member note paths
    existing = {
        "Dev/Rust": {"Knowledge/a.md", "Knowledge/b.md"},
        "AI/RAG": {"Knowledge/c.md"},
    }
    topic_members = {
        "rust-macros": {"Knowledge/a.md", "Knowledge/b.md"},
        "retrieval": {"Knowledge/c.md"},
    }
    d = diff_taxonomy(existing, topic_members)
    assert isinstance(d, TaxonomyDiff)
    # Dev/Rust aligns with rust-macros; AI/RAG with retrieval
    assert d.mapping["Dev/Rust"][0][0] == "rust-macros"
    assert "rust-macros" in d.covered_topics
    assert "retrieval" in d.covered_topics


def test_diff_taxonomy_ranks_overlap_descending():
    # A tag whose notes split across two topics ranks the higher-overlap topic
    # first (Jaccard), and reports the overlap score.
    existing = {"Dev/Rust": {"a", "b", "c", "d"}}
    topic_members = {
        "rust-core": {"a", "b", "c"},  # jaccard 3/4
        "rust-edge": {"d", "e", "f"},  # jaccard 1/6
    }
    d = diff_taxonomy(existing, topic_members)
    ranked = d.mapping["Dev/Rust"]
    assert ranked[0][0] == "rust-core"
    assert ranked[0][1] > ranked[1][1]  # overlap descending
    assert abs(ranked[0][1] - 3 / 4) < 1e-9


def test_diff_taxonomy_new_topics_have_no_aligned_tag():
    # A discovered topic that no existing tag aligns with is "new structure".
    existing = {"Dev/Rust": {"a", "b"}}
    topic_members = {
        "rust": {"a", "b"},
        "quantum-computing": {"x", "y", "z"},  # nothing in existing overlaps
    }
    d = diff_taxonomy(existing, topic_members)
    assert "quantum-computing" in d.new_topics
    assert "rust" not in d.new_topics


def test_diff_taxonomy_orphan_tags_have_no_aligned_topic():
    # A tag whose notes match no topic at all is an orphan.
    existing = {"Dev/Rust": {"a", "b"}, "Home/Gear": {"q", "r"}}
    topic_members = {"rust": {"a", "b"}}
    d = diff_taxonomy(existing, topic_members)
    assert "Home/Gear" in d.orphan_tags
    assert "Dev/Rust" not in d.orphan_tags


def test_diff_taxonomy_empty_inputs():
    d = diff_taxonomy({}, {})
    assert d.mapping == {}
    assert d.new_topics == []
    assert d.orphan_tags == []
    assert d.covered_topics == []
