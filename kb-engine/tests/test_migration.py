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
