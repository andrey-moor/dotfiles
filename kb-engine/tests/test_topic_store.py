import numpy as np
import pytest

from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store


def test_loaded_topic_centroid_is_immutable(tmp_path):
    # frozen=True does not protect the ndarray's contents; centroids decoded from
    # the store must be read-only so a caller can't mutate shared state.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.add_manual_topic("rust", "Rust", "rust", np.array([1, 0, 0], np.float32))
    loaded = s.load_topics()[0]
    with pytest.raises(ValueError):
        loaded.centroid[0] = 9.0


def test_added_manual_topic_centroid_does_not_alias_caller_array(tmp_path):
    # Mutating the caller's array after add_manual_topic must not change what was
    # stored (the decoded centroid is independent and frozen).
    s = Store(tmp_path / "t.db")
    s.init_schema()
    vec = np.array([1.0, 0.0, 0.0], np.float32)
    s.add_manual_topic("rust", "Rust", "rust", vec)
    vec[0] = 5.0
    loaded = s.load_topics()[0]
    assert loaded.centroid[0] == 1.0


def test_note_vectors_mean_pools_chunks(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.replace_chunks(
        "Knowledge/a.md",
        [
            (0, "x", np.array([1, 0, 0, 0], np.float32)),
            (1, "y", np.array([0, 1, 0, 0], np.float32)),
        ],
    )
    nv = dict((p, v) for p, v in s.note_vectors())
    assert nv["Knowledge/a.md"].shape == (4,)
    assert np.allclose(nv["Knowledge/a.md"], [0.5, 0.5, 0, 0])


def test_note_texts_joins_title_and_first_chunk(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="Rust", sha256="h", tags=[])
    s.replace_chunks(
        "Knowledge/a.md",
        [
            (0, "borrow checker", np.zeros(4, np.float32)),
            (1, "lifetimes", np.zeros(4, np.float32)),
        ],
    )
    # Note with no chunks contributes its title only.
    s.upsert_note(path="Knowledge/b.md", title="Empty", sha256="h", tags=[])
    texts = s.note_texts()
    assert texts["Knowledge/a.md"] == "Rust borrow checker"  # title + first chunk only
    assert texts["Knowledge/b.md"] == "Empty"


def test_save_and_load_topics(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    t = Topic(
        slug="ai-agents",
        label="AI Agents",
        keywords=("agent", "tool"),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics(
        [t],
        {"ai-agents": [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]},
    )
    loaded = s.load_topics()
    assert loaded[0].slug == "ai-agents" and loaded[0].centroid.shape == (4,)
    mem = s.topic_members("ai-agents")
    assert mem[0].note_path == "Knowledge/a.md" and abs(mem[0].score - 0.9) < 1e-6


def test_save_topics_renames_discovered_colliding_with_manual(tmp_path):
    # A retained manual topic "rust" plus an incoming discovered topic that also
    # slugifies to "rust" must NOT raise UNIQUE: the discovered one is suffixed
    # to "rust-2", its members re-keyed, and the manual "rust" left untouched.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.add_manual_topic("rust", "Rust", "rust", np.array([1, 0, 0], np.float32))
    s.set_members(
        "rust", [TopicMember(note_path="Knowledge/manual.md", score=0.9, source="seed")]
    )
    discovered = Topic(
        slug="rust",
        label="Rust Discovered",
        keywords=("rust",),
        centroid=np.array([0, 1, 0], np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics(
        [discovered],
        {"rust": [TopicMember(note_path="Knowledge/disc.md", score=0.8, source="auto")]},
    )
    by_slug = {t.slug: t for t in s.load_topics()}
    # manual "rust" untouched
    assert by_slug["rust"].kind == "manual"
    assert {m.note_path for m in s.topic_members("rust")} == {"Knowledge/manual.md"}
    # discovered stored under a suffixed slug, with its members re-keyed
    assert "rust-2" in by_slug and by_slug["rust-2"].kind == "discovered"
    assert {m.note_path for m in s.topic_members("rust-2")} == {"Knowledge/disc.md"}


def test_save_topics_collision_rename_is_deterministic(tmp_path):
    # Re-running discovery with the same colliding incoming topic produces the
    # same renamed slug every time (deterministic; no accumulation).
    def run() -> set[str]:
        s = Store(tmp_path / f"t-{run.n}.db")
        run.n += 1
        s.init_schema()
        s.add_manual_topic("rust", "Rust", "rust", np.array([1, 0, 0], np.float32))
        discovered = Topic(
            slug="rust",
            label="Rust D",
            keywords=("rust",),
            centroid=np.array([0, 1, 0], np.float32),
            kind="discovered",
            status="proposed",
        )
        s.save_topics([discovered], {"rust": []})
        return {t.slug for t in s.load_topics()}

    run.n = 0
    first = run()
    second = run()
    assert first == second == {"rust", "rust-2"}  # stable, manual + suffixed


def test_save_topics_replaces_previous_discovered(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    t1 = Topic(
        slug="old",
        label="Old",
        keywords=(),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics([t1], {"old": []})
    t2 = Topic(
        slug="new",
        label="New",
        keywords=(),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics([t2], {"new": []})  # discover re-run
    slugs = {t.slug for t in s.load_topics()}
    assert slugs == {"new"}  # stale discovered topics cleared
