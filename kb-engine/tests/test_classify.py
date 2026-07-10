import json

import frontmatter
import numpy as np

from kb_engine.config import Config
from kb_engine.llm import FakeLLM
from kb_engine.models import Area
from kb_engine.store import Store
from kb_engine.topics.areas_registry import SEEDED_AREAS, seed_areas
from kb_engine.topics.classify import (
    AreaAssignStats,
    AreaCandidate,
    annotate_queue_reason,
    area_centroids,
    assign_areas,
    classify_area,
)


def _areas():
    return list(SEEDED_AREAS)


def test_llm_path_valid_json():
    llm = FakeLLM(reply='{"area": "dev", "confidence": 0.9}')
    got = classify_area("Rust ownership notes", None, _areas(), {}, llm)
    assert got == AreaCandidate("dev", 0.9, "llm")
    system, user = llm.calls[0]
    assert "ONLY a JSON object" in system
    assert "Rust ownership notes" in user
    assert "gamedev" in system  # slug vocabulary is in the prompt


def test_llm_garbage_falls_back_to_embedding(real_vectors):
    llm = FakeLLM(reply="I cannot classify this note.")
    members = real_vectors.by_group("topic:")[:2]
    centroid = np.mean([v for _, v in members], axis=0)
    centroid = centroid / np.linalg.norm(centroid)
    got = classify_area(
        "whatever", members[0][1], _areas(), {"ai": centroid}, llm
    )
    assert got is not None
    assert got.source == "embedding"
    assert got.slug == "ai"
    assert 0.0 < got.confidence <= 1.0


def test_llm_unknown_slug_falls_back():
    llm = FakeLLM(reply='{"area": "nonsense", "confidence": 0.99}')
    got = classify_area("x", None, _areas(), {}, llm)
    assert got is None  # no vector either -> nothing


def test_no_llm_no_vector_returns_none():
    assert classify_area("x", None, _areas(), {}, None) is None


def test_area_centroids_unit_mean(tmp_path, real_vectors):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    seed_areas(store)
    members = real_vectors.by_group("topic:")[:2]
    for i, (path, vec) in enumerate(members):
        slug = f"t{i}"
        store.add_manual_topic(slug, slug, "d", vec)
        store.set_topic_area(slug, "ai")
    cents = area_centroids(store)
    assert set(cents) == {"ai"}
    expected = np.mean([v for _, v in members], axis=0)
    expected = expected / np.linalg.norm(expected)
    assert np.allclose(cents["ai"], expected, atol=1e-6)
    assert abs(float(np.linalg.norm(cents["ai"])) - 1.0) < 1e-5
    store.close()


def test_annotate_queue_reason():
    assert annotate_queue_reason("borderline", "rust-learning", 0.85) == (
        "borderline; llm: rust-learning (0.85)"
    )


# --- assign_areas (weekly mop-up over topicless, area-less notes) -------------


def _area_store(tmp_path, real_vectors):
    """Store seeded with an 'ai' area centroid built from AI-topic vectors.

    The anchor topics carry no notes, so the only note rows are the mop-up
    targets a test adds explicitly.
    """
    store = Store(tmp_path / "t.db")
    store.init_schema()
    seed_areas(store)
    ai_rows = (
        real_vectors.by_group("topic:ai-agents")
        + real_vectors.by_group("topic:prompt-engineering")
    )
    for i, (_path, vec) in enumerate(ai_rows):
        slug = f"aitopic{i}"
        store.add_manual_topic(slug, slug, "d", vec)
        store.set_topic_area(slug, "ai")
    return store, ai_rows


def _topicless_note(store, tmp_path, relpath, vector=None, tags=None):
    """Register a topicless note in the store and write its file to disk."""
    store.upsert_note(relpath, relpath, f"sha-{relpath}", tags or [])
    if vector is not None:
        store.replace_chunks(relpath, [(0, relpath, vector)])
    path = tmp_path / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    tag_line = f"\ntags: [{', '.join(tags)}]" if tags else ""
    path.write_text(f"---\ntitle: {relpath}{tag_line}\n---\nbody")
    return path


def test_assign_areas_embedding_assigns_near_note(tmp_path, real_vectors):
    # No LLM → embedding path. A topicless note near the 'ai' centroid gets
    # area/ai + area_provenance: auto written via house I/O.
    store, ai_rows = _area_store(tmp_path, real_vectors)
    _topicless_note(store, tmp_path, "Knowledge/near.md", vector=ai_rows[0][1])
    cfg = Config(vault_path=tmp_path, db_path=tmp_path / "t.db")

    stats = assign_areas(cfg, store, None)

    assert isinstance(stats, AreaAssignStats)
    assert stats.assigned == 1
    assert stats.assigned_paths == (("Knowledge/near.md", "ai"),)
    fm = frontmatter.load(tmp_path / "Knowledge" / "near.md")
    assert "area/ai" in fm["tags"]
    assert fm["area_provenance"] == "auto"
    store.close()


def test_assign_areas_skips_low_confidence(tmp_path, real_vectors):
    # A cooking vector sits far (~0.17 cos) from the 'ai' centroid → below 0.55.
    store, _ = _area_store(tmp_path, real_vectors)
    far_vec = real_vectors.by_group("topic:cooking-coffee")[0][1]
    _topicless_note(store, tmp_path, "Knowledge/far.md", vector=far_vec)
    cfg = Config(vault_path=tmp_path, db_path=tmp_path / "t.db")

    stats = assign_areas(cfg, store, None)

    assert stats.assigned == 0
    assert stats.skipped_low_confidence == 1
    fm = frontmatter.load(tmp_path / "Knowledge" / "far.md")
    assert not any(str(t).startswith("area/") for t in (fm.get("tags") or []))
    store.close()


def test_assign_areas_no_vector_is_no_signal(tmp_path, real_vectors):
    # A note with no stored vector can't be embedding-classified (no LLM either).
    store, _ = _area_store(tmp_path, real_vectors)
    _topicless_note(store, tmp_path, "Knowledge/blank.md", vector=None)
    cfg = Config(vault_path=tmp_path, db_path=tmp_path / "t.db")

    stats = assign_areas(cfg, store, None)

    assert stats.no_signal == 1
    assert stats.assigned == 0
    store.close()


def test_assign_areas_skips_already_area_tagged(tmp_path, real_vectors):
    # A note that already carries an area/* tag is not a mop-up target — even
    # though its vector is near the 'ai' centroid, it is left untouched.
    store, ai_rows = _area_store(tmp_path, real_vectors)
    _topicless_note(
        store, tmp_path, "Knowledge/tagged.md",
        vector=ai_rows[0][1], tags=["area/personal"],
    )
    cfg = Config(vault_path=tmp_path, db_path=tmp_path / "t.db")

    stats = assign_areas(cfg, store, None)

    assert stats.assigned == 0
    fm = frontmatter.load(tmp_path / "Knowledge" / "tagged.md")
    assert "area/ai" not in fm["tags"]
    assert "area/personal" in fm["tags"]
    store.close()


def test_assign_areas_respects_limit(tmp_path, real_vectors):
    # Three near-centroid targets, limit 2 → only the first two (sorted) assigned.
    store, ai_rows = _area_store(tmp_path, real_vectors)
    for i in range(3):
        _topicless_note(store, tmp_path, f"Knowledge/n{i}.md", vector=ai_rows[0][1])
    cfg = Config(vault_path=tmp_path, db_path=tmp_path / "t.db")

    stats = assign_areas(cfg, store, None, limit=2)

    assert stats.assigned == 2
    assert len(stats.assigned_paths) == 2
    assert [p for p, _ in stats.assigned_paths] == ["Knowledge/n0.md", "Knowledge/n1.md"]
    store.close()
