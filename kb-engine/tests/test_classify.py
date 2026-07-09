import json

import numpy as np

from kb_engine.llm import FakeLLM
from kb_engine.models import Area
from kb_engine.store import Store
from kb_engine.topics.areas_registry import SEEDED_AREAS, seed_areas
from kb_engine.topics.classify import (
    AreaCandidate,
    annotate_queue_reason,
    area_centroids,
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
