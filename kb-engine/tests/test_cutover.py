import numpy as np
import pytest

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics._math import cosine
from kb_engine.topics.areas_registry import seed_areas
from kb_engine.topics.cutover import apply_cutover
from kb_engine.topics.migration import MigrationProposal, TagDisposition, TopicArea
from kb_engine.vault import load_post


def _store(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    seed_areas(store)
    return store


def _index(store, rel, tags, vector=None):
    store.upsert_note(rel, rel, "sha-" + rel, tags)
    if vector is not None:
        store.replace_chunks(rel, [(0, "text", vector)])


def _write(vault, rel, tags, extra=""):
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "[" + ", ".join(f'"{t}"' for t in tags) + "]"
    path.write_text(
        f"---\ntitle: {path.stem}\ntags: {body}\nsummary: s\n{extra}---\nbody text\n"
    )
    return path


def _disp(tag, decision, area, count=2):
    return TagDisposition(
        tag=tag, count=count, area=area, best_topic=None, overlap=0.0, decision=decision
    )


def _proposal(dispositions=(), topic_areas=()):
    return MigrationProposal(
        topic_areas=tuple(topic_areas), dispositions=tuple(dispositions)
    )


def _tags_of(vault, rel):
    return load_post((vault / rel).read_text()).get("tags")


def test_map_disposition_drops_tag_adds_topic_and_area(tmp_path):
    store = _store(tmp_path)
    store.add_manual_topic("rust-learning", "Rust", "d", np.ones(4, np.float32))
    rel = "Knowledge/rust.md"
    _index(store, rel, ["Dev/Rust", "Reference"])
    store.set_members("rust-learning", [TopicMember(rel, 0.9, "auto", True)])
    _write(tmp_path, rel, ["Dev/Rust", "Reference"])
    proposal = _proposal(
        dispositions=[_disp("Dev/Rust", "map:rust-learning", "dev")],
        topic_areas=[TopicArea("rust-learning", "dev", "ev")],
    )

    result = apply_cutover(store, tmp_path, proposal, dry_run=False)

    assert result.notes_changed == 1
    assert result.tags_dropped == 1
    assert result.topic_tags_added == 1
    assert result.area_tags_added == 1
    tags = _tags_of(tmp_path, rel)
    assert "Dev/Rust" not in tags
    assert "topic/rust-learning" in tags
    assert "area/dev" in tags
    assert "Reference" in tags
    store.close()


def test_topic_disposition_creates_manual_topic_with_members(tmp_path, real_vectors):
    store = _store(tmp_path)
    vecs = real_vectors.by_group("topic:indie-hacking")
    paths = [p for p, _ in vecs]
    for p, v in vecs:
        _index(store, p, ["Business/Marketing"], vector=v)
        _write(tmp_path, p, ["Business/Marketing"])
    proposal = _proposal(
        dispositions=[_disp("Business/Marketing", "topic:business-marketing", "business")]
    )

    result = apply_cutover(store, tmp_path, proposal, dry_run=False)

    assert "business-marketing" in result.topics_created
    created = {t.slug: t for t in store.load_topics()}["business-marketing"]
    assert created.label == "Marketing"
    assert created.kind == "manual"
    assert created.area == "business"
    assert float(np.linalg.norm(created.centroid)) == pytest.approx(1.0, abs=1e-5)
    mean = np.mean([v for _, v in vecs], axis=0)
    expected = (mean / np.linalg.norm(mean)).astype(np.float32)
    members = {m.note_path: m for m in store.topic_members("business-marketing")}
    assert set(members) == set(paths)
    for p, v in vecs:
        assert members[p].is_primary
        assert members[p].source == "auto"
        assert members[p].score == pytest.approx(cosine(v, expected), abs=1e-4)
    for p in paths:
        tags = _tags_of(tmp_path, p)
        assert "Business/Marketing" not in tags
        assert "topic/business-marketing" in tags
        assert "area/business" in tags
    store.close()


def test_area_disposition_drops_tag_adds_only_area(tmp_path):
    store = _store(tmp_path)
    rel = "Knowledge/fit.md"
    _index(store, rel, ["Personal/Fitness", "Reference"])
    _write(tmp_path, rel, ["Personal/Fitness", "Reference"])
    proposal = _proposal(dispositions=[_disp("Personal/Fitness", "area", "personal")])

    result = apply_cutover(store, tmp_path, proposal, dry_run=False)

    assert result.notes_changed == 1
    assert result.tags_dropped == 1
    assert result.topic_tags_added == 0
    assert result.area_tags_added == 1
    tags = _tags_of(tmp_path, rel)
    assert "Personal/Fitness" not in tags
    assert "area/personal" in tags
    assert not any(t.startswith("topic/") for t in tags)
    assert "Reference" in tags
    store.close()


def test_existing_area_tag_is_preserved(tmp_path):
    store = _store(tmp_path)
    store.add_manual_topic("rust-learning", "Rust", "d", np.ones(4, np.float32))
    rel = "Knowledge/rust.md"
    _index(store, rel, ["Dev/Rust", "area/personal"])
    store.set_members("rust-learning", [TopicMember(rel, 0.9, "auto", True)])
    _write(tmp_path, rel, ["Dev/Rust", "area/personal"])
    proposal = _proposal(
        dispositions=[_disp("Dev/Rust", "map:rust-learning", "dev")],
        topic_areas=[TopicArea("rust-learning", "dev", "ev")],
    )

    result = apply_cutover(store, tmp_path, proposal, dry_run=False)

    assert result.area_tags_added == 0
    tags = _tags_of(tmp_path, rel)
    assert "area/personal" in tags
    assert "area/dev" not in tags
    assert "topic/rust-learning" in tags
    assert "Dev/Rust" not in tags
    store.close()


def test_dry_run_writes_nothing_but_matches_apply(tmp_path, real_vectors):
    store = _store(tmp_path)
    vecs = real_vectors.by_group("topic:indie-hacking")
    for p, v in vecs:
        _index(store, p, ["Business/Marketing"], vector=v)
        _write(tmp_path, p, ["Business/Marketing"])
    rel = "Knowledge/fit.md"
    _index(store, rel, ["Personal/Fitness"])
    _write(tmp_path, rel, ["Personal/Fitness"])
    proposal = _proposal(
        dispositions=[
            _disp("Business/Marketing", "topic:business-marketing", "business"),
            _disp("Personal/Fitness", "area", "personal"),
        ]
    )
    files = list(tmp_path.rglob("*.md"))
    before = {f: f.read_bytes() for f in files}
    topics_before = [t.slug for t in store.load_topics()]

    dry = apply_cutover(store, tmp_path, proposal, dry_run=True)

    assert all(f.read_bytes() == before[f] for f in files)
    assert [t.slug for t in store.load_topics()] == topics_before
    assert store.topic_members("business-marketing") == []

    real = apply_cutover(store, tmp_path, proposal, dry_run=False)

    assert dry.notes_changed == real.notes_changed
    assert dry.tags_dropped == real.tags_dropped
    assert dry.topic_tags_added == real.topic_tags_added
    assert dry.area_tags_added == real.area_tags_added
    assert dry.topics_created == real.topics_created
    assert dry.diff_lines == real.diff_lines
    store.close()


def test_idempotent_second_apply_changes_nothing(tmp_path, real_vectors):
    store = _store(tmp_path)
    vecs = real_vectors.by_group("topic:indie-hacking")
    for p, v in vecs:
        _index(store, p, ["Business/Marketing"], vector=v)
        _write(tmp_path, p, ["Business/Marketing"])
    proposal = _proposal(
        dispositions=[_disp("Business/Marketing", "topic:business-marketing", "business")]
    )

    first = apply_cutover(store, tmp_path, proposal, dry_run=False)
    assert first.notes_changed == 2
    assert "business-marketing" in first.topics_created

    second = apply_cutover(store, tmp_path, proposal, dry_run=False)
    assert second.notes_changed == 0
    assert second.tags_dropped == 0
    assert second.topic_tags_added == 0
    assert second.area_tags_added == 0
    assert second.topics_created == ()
    store.close()


def test_facet_and_junk_tags_preserved(tmp_path):
    store = _store(tmp_path)
    store.add_manual_topic("rust-learning", "Rust", "d", np.ones(4, np.float32))
    rel = "Knowledge/rust.md"
    tags = ["Dev/Rust", "Reference", "wip", "type/til"]
    _index(store, rel, tags)
    store.set_members("rust-learning", [TopicMember(rel, 0.9, "auto", True)])
    _write(tmp_path, rel, tags)
    proposal = _proposal(
        dispositions=[_disp("Dev/Rust", "map:rust-learning", "dev")],
        topic_areas=[TopicArea("rust-learning", "dev", "ev")],
    )

    apply_cutover(store, tmp_path, proposal, dry_run=False)

    new = _tags_of(tmp_path, rel)
    assert "Reference" in new and "wip" in new and "type/til" in new
    assert "Dev/Rust" not in new
    assert new.index("Reference") < new.index("topic/rust-learning")
    store.close()


def test_content_unavailable_note_migrates(tmp_path):
    store = _store(tmp_path)
    rel = "Knowledge/fit.md"
    _index(store, rel, ["Personal/Fitness"])
    _write(tmp_path, rel, ["Personal/Fitness"], extra="content: unavailable\n")
    proposal = _proposal(dispositions=[_disp("Personal/Fitness", "area", "personal")])

    result = apply_cutover(store, tmp_path, proposal, dry_run=False)

    assert result.notes_changed == 1
    post = load_post((tmp_path / rel).read_text())
    assert post.get("content") == "unavailable"
    assert "area/personal" in post.get("tags")
    assert "Personal/Fitness" not in post.get("tags")
    store.close()


def test_topic_disposition_without_vectors_skips_creation_still_migrates(tmp_path):
    store = _store(tmp_path)
    rel = "Knowledge/mkt.md"
    _index(store, rel, ["Business/Marketing"])  # indexed, but NO vector
    _write(tmp_path, rel, ["Business/Marketing"])
    proposal = _proposal(
        dispositions=[_disp("Business/Marketing", "topic:business-marketing", "business")]
    )

    result = apply_cutover(store, tmp_path, proposal, dry_run=False)

    assert "business-marketing" not in result.topics_created
    assert any("business-marketing" in line for line in result.diff_lines)
    assert {t.slug for t in store.load_topics()} == set()
    assert result.notes_changed == 1
    tags = _tags_of(tmp_path, rel)
    assert "Business/Marketing" not in tags
    assert "topic/business-marketing" in tags
    assert "area/business" in tags
    store.close()


def test_undecided_topic_area_row_is_skipped(tmp_path):
    store = _store(tmp_path)
    store.add_manual_topic("rust-learning", "Rust", "d", np.ones(4, np.float32))
    proposal = _proposal(topic_areas=[TopicArea("rust-learning", "", "no evidence")])

    result = apply_cutover(store, tmp_path, proposal, dry_run=False)

    assert store.load_topics()[0].area is None
    assert not any("topic-area" in line for line in result.diff_lines)
    store.close()
