import numpy as np
import pytest

from kb_engine.models import Area, Topic
from kb_engine.store import Store
from kb_engine.topics.areas import build_areas


def _t(slug, vec):
    return Topic(
        slug=slug,
        label=slug,
        keywords=(slug,),
        centroid=np.array(vec, np.float32),
        kind="discovered",
        status="proposed",
    )


def test_build_areas_groups_near_centroids():
    pytest.importorskip("sklearn")  # AgglomerativeClustering — only in the [topics] extra
    topics = [_t("rust1", [1, 0, 0]), _t("rust2", [0.95, 0.05, 0]), _t("llm", [0, 0, 1])]
    areas = build_areas(topics, distance_threshold=0.3)
    # the two rust topics share an area; llm is its own
    by_topic = {ts: a.slug for a in areas for ts in a.topic_slugs}
    assert by_topic["rust1"] == by_topic["rust2"] != by_topic["llm"]


def test_build_areas_single_topic_is_its_own_area():
    areas = build_areas([_t("solo", [1, 0, 0])], distance_threshold=0.3)
    assert len(areas) == 1 and areas[0].topic_slugs == ("solo",)


def test_build_areas_empty():
    assert build_areas([], distance_threshold=0.3) == []


def _t_kw(slug, vec, keywords):
    return Topic(
        slug=slug,
        label=slug,
        keywords=keywords,
        centroid=np.array(vec, np.float32),
        kind="discovered",
        status="proposed",
    )


def test_build_areas_dedupes_colliding_slugs():
    pytest.importorskip("sklearn")  # AgglomerativeClustering — only in the [topics] extra
    # Two far-apart clusters whose top keyword is identical must get distinct
    # area slugs (second disambiguated with a "-2" suffix).
    topics = [
        _t_kw("rust-a", [1, 0, 0], ("rust",)),
        _t_kw("rust-b", [0, 1, 0], ("rust",)),
    ]
    areas = build_areas(topics, distance_threshold=0.3)
    slugs = [a.slug for a in areas]
    assert len(areas) == 2
    assert len(set(slugs)) == 2 and any(s.endswith("-2") for s in slugs)


def test_build_areas_falls_back_to_indexed_slug_without_keywords():
    pytest.importorskip("sklearn")  # AgglomerativeClustering — only in the [topics] extra
    # Topics with no keywords can't derive a slug, so the area uses "area-{i}".
    topics = [
        _t_kw("x", [1, 0, 0], ()),
        _t_kw("y", [0, 1, 0], ()),
    ]
    areas = build_areas(topics, distance_threshold=0.3)
    assert {a.slug for a in areas} == {"area-0", "area-1"}


def _topic(slug):
    return Topic(
        slug=slug,
        label=slug,
        keywords=(),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )


def test_save_and_load_areas(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.save_topics([_topic("a"), _topic("b")], {"a": [], "b": []})
    s.save_areas([Area(slug="ai", label="AI", topic_slugs=("a", "b"))])
    areas = s.load_areas()
    assert areas[0].slug == "ai" and set(areas[0].topic_slugs) == {"a", "b"}


def test_save_areas_replaces_previous(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.save_topics([_topic("a")], {"a": []})
    s.save_areas([Area(slug="x", label="X", topic_slugs=("a",))])
    s.save_areas([Area(slug="y", label="Y", topic_slugs=("a",))])
    assert {a.slug for a in s.load_areas()} == {"y"}
