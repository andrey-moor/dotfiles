import numpy as np

from kb_engine.models import Area, Topic
from kb_engine.store import Store


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
