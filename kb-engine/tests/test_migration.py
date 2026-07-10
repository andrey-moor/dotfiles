import numpy as np
import pytest

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics.areas_registry import seed_areas
from kb_engine.topics.migration import (
    MigrationProposal,
    TagDisposition,
    TopicArea,
    build_migration_proposal,
    parse_migration_proposal,
    render_migration_proposal,
)


def _seed(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    seed_areas(store)
    store.add_manual_topic("rust-learning", "Rust", "d", np.ones(4, np.float32))
    members = []
    for i in range(4):
        p = f"Knowledge/rust-{i}.md"
        store.upsert_note(p, p, f"sha-{i}", ["Dev/Rust", "Reference"])
        members.append(TopicMember(p, 0.8, "auto"))
    store.set_members("rust-learning", members)
    # an unaligned low-count tag
    store.upsert_note("Knowledge/fit.md", "fit", "sha-f", ["Personal/Fitness"])
    # an unaligned high-count tag (>= 8) that should propose a new topic
    for i in range(8):
        p = f"Knowledge/mkt-{i}.md"
        store.upsert_note(p, p, f"sha-m{i}", ["Business/Marketing"])
    return store


def test_build_proposal_decisions(tmp_path):
    store = _seed(tmp_path)
    declared = {"Dev/Rust", "Personal/Fitness", "Business/Marketing"}
    proposal = build_migration_proposal(store, declared)
    by_tag = {d.tag: d for d in proposal.dispositions}
    assert by_tag["Dev/Rust"].decision == "map:rust-learning"
    assert by_tag["Dev/Rust"].area == "dev"
    assert by_tag["Dev/Rust"].count == 4
    assert by_tag["Dev/Rust"].overlap == pytest.approx(1.0)
    assert by_tag["Personal/Fitness"].decision == "area"
    assert by_tag["Business/Marketing"].decision == "topic:business-marketing"
    topic_area = {t.slug: t for t in proposal.topic_areas}
    assert topic_area["rust-learning"].proposed_area == "dev"
    store.close()


def test_round_trip(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(
        store, {"Dev/Rust", "Personal/Fitness", "Business/Marketing"}
    )
    text = render_migration_proposal(proposal)
    parsed = parse_migration_proposal(text)
    assert [(t.slug, t.proposed_area) for t in parsed.topic_areas] == [
        (t.slug, t.proposed_area) for t in proposal.topic_areas
    ]
    assert [(d.tag, d.count, d.area, d.decision) for d in parsed.dispositions] == [
        (d.tag, d.count, d.area, d.decision) for d in proposal.dispositions
    ]


def test_parse_rejects_bad_decision(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "map:rust-learning", "yolo:whatever"
    )
    with pytest.raises(ValueError, match="Dev/Rust"):
        parse_migration_proposal(text)
    store.close()


def test_parse_rejects_unknown_area(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace("| dev |", "| dve |", 1)
    with pytest.raises(ValueError):
        parse_migration_proposal(text)
    store.close()


def test_tag_with_unknown_category_is_skipped_with_note(tmp_path):
    """A two-level tag whose category isn't in CATEGORY_TO_AREA (shouldn't exist
    live, but defensive) is excluded from dispositions rather than crashing."""
    store = _seed(tmp_path)
    store.upsert_note("Knowledge/weird.md", "w", "sha-w", ["Weird/Thing"])
    proposal = build_migration_proposal(store, {"Dev/Rust", "Weird/Thing"})
    assert "Weird/Thing" not in {d.tag for d in proposal.dispositions}
    store.close()


# --- rejection-guard regressions (finding I1) ---------------------------------
# This artifact drives a mass retag; each guard below is a safety gate. These
# tests pin the exact rejection paths against refactor regressions. Each builds a
# valid proposal, corrupts ONE cell, and asserts the ValueError names the row.


def test_parse_rejects_typod_map_target(tmp_path):
    """THE typo guard: a map target that is a near-miss of a real topic slug
    (valid grammar, but absent from the doc's topic list) is rejected."""
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "map:rust-learning", "map:rust-learnin"
    )
    with pytest.raises(ValueError, match=r"Dev/Rust.*map target"):
        parse_migration_proposal(text)
    store.close()


def test_parse_rejects_map_target_absent_from_doc(tmp_path):
    """A grammatically valid map target naming a topic not listed in the doc's
    ## Topic → area section is rejected (doc-scoped validation)."""
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "map:rust-learning", "map:database-design"
    )
    with pytest.raises(ValueError, match=r"Dev/Rust.*map target"):
        parse_migration_proposal(text)
    store.close()


def test_parse_rejects_non_integer_count(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace("| 4 |", "| four |")
    with pytest.raises(ValueError, match=r"Dev/Rust.*non-integer"):
        parse_migration_proposal(text)
    store.close()


def test_parse_rejects_unknown_area_in_disposition_row(tmp_path):
    """Distinct from test_parse_rejects_unknown_area (which corrupts the first
    ``| dev |`` — the topic→area row): this corrupts the disposition row's area
    cell, exercising the disposition-path guard."""
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace("4 | dev |", "4 | dve |")
    with pytest.raises(ValueError, match=r"Dev/Rust.*unknown area"):
        parse_migration_proposal(text)
    store.close()


def test_parse_rejects_disposition_row_with_too_few_cells(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "| rust-learning (1.00) | map:rust-learning |", "| map:rust-learning |"
    )
    with pytest.raises(ValueError, match=r"Dev/Rust.*malformed disposition"):
        parse_migration_proposal(text)
    store.close()


def test_parse_rejects_topic_row_with_too_few_cells(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "| dev | 4/4 member notes tagged Dev/* |", "| dev |"
    )
    with pytest.raises(ValueError, match=r"rust-learning.*malformed topic"):
        parse_migration_proposal(text)
    store.close()


# --- slug-grammar guards: parser accept-set must be a subset of the store's ---
# The store's SLUG_PATTERN is ^[a-z0-9][a-z0-9-]*$: leading char alnum (no
# leading hyphen), trailing hyphen allowed, empty rejected. The parser must not
# accept a slug the store would reject — else the cutover mints a dangling tag
# and a false topics_created count on a human typo. These pin parser ⊆ store.


def test_parse_rejects_leading_hyphen_topic_slug(tmp_path):
    """A leading-hyphen slug (store rejects it) must be rejected AT PARSE TIME,
    naming the row — not swallowed by the cutover's already-exists guard."""
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "map:rust-learning", "topic:-foo"
    )
    with pytest.raises(ValueError, match=r"Dev/Rust.*invalid decision"):
        parse_migration_proposal(text)
    store.close()


def test_parse_rejects_leading_hyphen_map_slug(tmp_path):
    """Same guard on the map: side — a leading-hyphen target fails the grammar
    (before the known-topic check), naming the row."""
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "map:rust-learning", "map:-foo"
    )
    with pytest.raises(ValueError, match=r"Dev/Rust.*invalid decision"):
        parse_migration_proposal(text)
    store.close()


def test_parse_accepts_trailing_hyphen_slug(tmp_path):
    """No over-tightening: the store accepts a trailing hyphen (``foo-`` matches
    SLUG_PATTERN), so the parser must too — keeping parser accept-set == store's
    for single segments (consistent, no dangling possible)."""
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "map:rust-learning", "topic:foo-"
    )
    parsed = parse_migration_proposal(text)
    decision = {d.tag: d.decision for d in parsed.dispositions}["Dev/Rust"]
    assert decision == "topic:foo-"
    store.close()


def test_parse_accepts_valid_single_segment_slugs(tmp_path):
    """No over-tightening: the common valid forms still parse — ``map:<known>``
    (unchanged) and a single-char ``topic:a``."""
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal)
    assert {d.tag: d.decision for d in parse_migration_proposal(text).dispositions}[
        "Dev/Rust"
    ] == "map:rust-learning"
    text_a = text.replace("map:rust-learning", "topic:a")
    assert {d.tag: d.decision for d in parse_migration_proposal(text_a).dispositions}[
        "Dev/Rust"
    ] == "topic:a"
    store.close()


def test_parse_rejects_duplicate_section(tmp_path):
    """A duplicated ## Tag dispositions section would silently merge its rows
    into the cutover (over-inclusion); the parser rejects it outright. The extra
    row is itself valid, so only the duplicate-section guard can raise here."""
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal)
    extra = (
        "\n## Tag dispositions\n\n"
        "| tag | count | area | best topic (jaccard) | decision |\n"
        "|---|---|---|---|---|\n"
        "| Sneaky/Extra | 1 | dev | — | area |\n"
    )
    with pytest.raises(ValueError, match="duplicate section"):
        parse_migration_proposal(text + extra)
    store.close()
