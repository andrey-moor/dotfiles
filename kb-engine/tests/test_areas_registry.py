import numpy as np

from kb_engine.store import Store
from kb_engine.topics.areas_registry import (
    CATEGORY_TO_AREA,
    SEEDED_AREAS,
    seed_areas,
)


def test_seeded_areas_are_the_nine_spec_areas():
    assert [a.slug for a in SEEDED_AREAS] == [
        "ai", "dev", "infra", "arch", "gamedev",
        "business", "career", "home", "personal",
    ]
    assert all(a.label for a in SEEDED_AREAS)
    assert all(a.description for a in SEEDED_AREAS)
    assert all(a.topic_slugs == () for a in SEEDED_AREAS)


def test_category_map_covers_live_categories():
    assert CATEGORY_TO_AREA == {
        "AI": "ai", "Dev": "dev", "Infra": "infra", "Arch": "arch",
        "GameDev": "gamedev", "Business": "business", "Career": "career",
        "Home": "home", "Personal": "personal",
    }
    assert set(CATEGORY_TO_AREA.values()) == {a.slug for a in SEEDED_AREAS}


def test_seed_areas_idempotent_and_composed_membership(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    n = seed_areas(store)
    assert n == 9
    assert seed_areas(store) == 9  # idempotent re-run
    store.add_manual_topic("rust-learning", "Rust", "d", np.ones(4, np.float32))
    store.set_topic_area("rust-learning", "dev")
    areas = {a.slug: a for a in store.load_areas()}
    assert len(areas) == 9
    assert areas["dev"].topic_slugs == ("rust-learning",)
    assert areas["ai"].topic_slugs == ()
    assert areas["dev"].description
    store.close()
