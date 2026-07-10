import numpy as np
import frontmatter

from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store
from kb_engine.topics.apply import ApplyResult, _apply_to_note, apply_topic_tags


def _note(vault, relpath, text):
    path = vault / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _store_with_active_topic(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=["Dev/Rust"])
    s.add_manual_topic(
        "rust-macros", "Rust Macros", "rust", np.array([1, 0, 0], np.float32)
    )
    s.set_members(
        "rust-macros",
        [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto", is_primary=True)],
    )
    return s


def test_apply_adds_topic_tag_to_member_notes(tmp_path):
    s = _store_with_active_topic(tmp_path)
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\ntags: [Dev/Rust]\n---\nbody")
    res = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    assert isinstance(res, ApplyResult)
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert "topic/rust-macros" in fm["tags"]
    # original tag + body preserved
    assert "Dev/Rust" in fm["tags"]
    assert fm.content.strip() == "body"
    assert res.n_changed == 1


def test_apply_is_idempotent(tmp_path):
    s = _store_with_active_topic(tmp_path)
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\ntags: [Dev/Rust]\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    res2 = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert fm["tags"].count("topic/rust-macros") == 1
    # nothing changed on the second pass
    assert res2.n_changed == 0


def test_apply_adds_tags_key_when_absent(tmp_path):
    s = _store_with_active_topic(tmp_path)
    # note has no tags key at all
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert fm["tags"] == ["topic/rust-macros"]


def test_apply_skips_proposed_topics_by_default(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.save_topics(
        [
            Topic(
                slug="prop",
                label="Prop",
                keywords=("prop",),
                centroid=np.array([1, 0, 0], np.float32),
                kind="discovered",
                status="proposed",
            )
        ],
        {"prop": [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]},
    )
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\n---\nbody")
    res = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    # proposed topic must NOT be applied under the default active-only gate
    assert "tags" not in fm.metadata or "topic/prop" not in (fm.get("tags") or [])
    assert res.n_changed == 0


def test_apply_can_target_proposed_when_requested(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.save_topics(
        [
            Topic(
                slug="prop",
                label="Prop",
                keywords=("prop",),
                centroid=np.array([1, 0, 0], np.float32),
                kind="discovered",
                status="proposed",
            )
        ],
        {"prop": [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]},
    )
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("proposed",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert "topic/prop" in fm["tags"]


def test_apply_skips_missing_note_files(tmp_path):
    s = _store_with_active_topic(tmp_path)  # member Knowledge/a.md never written
    res = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    assert res.n_changed == 0
    assert "Knowledge/a.md" in res.skipped_missing


def test_apply_handles_scalar_tags_value(tmp_path):
    # A note whose `tags` is a scalar (e.g. `tags: 42`) must not crash apply —
    # the scalar is treated as a single existing tag and the topic tag is added.
    s = _store_with_active_topic(tmp_path)
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\ntags: 42\n---\nbody")
    res = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert "topic/rust-macros" in fm["tags"]
    assert "42" in fm["tags"]  # the scalar preserved as a string tag
    assert res.n_changed == 1


def test_apply_skips_note_path_outside_vault(tmp_path):
    # A member note_path that escapes the vault ("../outside.md") must be skipped:
    # never write frontmatter outside the vault, and report it as skipped.
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("---\ntitle: Outside\n---\nsecret")
    s = Store(vault / "t.db")
    s.init_schema()
    s.upsert_note(path="../outside.md", title="Outside", sha256="h", tags=[])
    s.add_manual_topic("rust", "Rust", "rust", np.array([1, 0, 0], np.float32))
    s.set_members(
        "rust", [TopicMember(note_path="../outside.md", score=0.9, source="auto")]
    )
    res = apply_topic_tags(s, vault_path=vault, only_status=("active",))
    # the outside file is untouched (no topic tag injected)
    assert outside.read_text() == "---\ntitle: Outside\n---\nsecret"
    assert res.n_changed == 0
    assert "../outside.md" in res.skipped_outside_vault


def test_apply_writes_all_topic_tags_and_primary_topic_field(tmp_path):
    (tmp_path / "Knowledge").mkdir()
    note = tmp_path / "Knowledge" / "n.md"
    note.write_text("---\ntitle: N\ntags: [Dev/Rust]\n---\nbody\n")
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.add_manual_topic("rust", "Rust", "rust", np.ones(8, np.float32))
    store.add_manual_topic("ai", "AI", "ai", np.ones(8, np.float32))
    store.set_members("rust", [TopicMember("Knowledge/n.md", 0.9, "auto", is_primary=True)])
    store.set_members("ai", [TopicMember("Knowledge/n.md", 0.6, "auto", is_primary=False)])
    apply_topic_tags(store, vault_path=tmp_path, only_status=("active",))
    post = frontmatter.load(note)
    assert set(post["tags"]) >= {"Dev/Rust", "topic/rust", "topic/ai"}
    assert post["primary_topic"] == "rust"
    store.close()


def test_apply_sets_primary_topic_even_when_tags_already_present(tmp_path):
    # Note already carries its topic tag but no primary_topic field: apply must
    # still set the field and count the note as changed (tags_added stays 0).
    s = _store_with_active_topic(tmp_path)  # primary member a -> rust-macros
    _note(tmp_path, "Knowledge/a.md",
          "---\ntitle: A\ntags: [Dev/Rust, topic/rust-macros]\n---\nbody")
    res = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert fm["primary_topic"] == "rust-macros"
    assert res.n_changed == 1     # field newly set despite tag already present
    assert res.n_tags_added == 0  # no NEW tags


def test_apply_primary_topic_is_idempotent(tmp_path):
    s = _store_with_active_topic(tmp_path)
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\ntags: [Dev/Rust]\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    res2 = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert fm["primary_topic"] == "rust-macros"
    assert res2.n_changed == 0  # nothing to do on the second pass


def test_apply_preserves_other_frontmatter(tmp_path):
    s = _store_with_active_topic(tmp_path)
    _note(
        tmp_path,
        "Knowledge/a.md",
        "---\ntitle: A\nsource: https://x.test\ntags: [Dev/Rust]\n---\nbody text",
    )
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert fm["title"] == "A"
    assert fm["source"] == "https://x.test"
    assert fm.content.strip() == "body text"


def test_apply_secondary_member_gets_tag_but_no_primary_topic_field(tmp_path):
    # A note that is only a secondary (is_primary=False) member gets the topic tag
    # but must NOT receive a primary_topic field.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.add_manual_topic("ml", "ML", "ml", np.array([1, 0, 0], np.float32))
    s.set_members(
        "ml",
        [TopicMember(note_path="Knowledge/b.md", score=0.7, source="auto", is_primary=False)],
    )
    _note(tmp_path, "Knowledge/b.md", "---\ntitle: B\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "b.md")
    assert "topic/ml" in fm["tags"]
    assert "primary_topic" not in fm.metadata


def test_apply_tolerates_content_frontmatter_key(tmp_path):
    """A member note carrying backfill's `content: unavailable` must still get
    tagged — frontmatter.load() crashes on that key; the house load_post doesn't."""
    note = tmp_path / "Knowledge" / "stub.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntitle: Stub\ncontent: unavailable\ntags: [old]\n---\nbody\n"
    )
    changed, added = _apply_to_note(note, ["mytopic"], None)
    assert (changed, added) == (True, 1)
    text = note.read_text()
    assert "topic/mytopic" in text
    assert "content: unavailable" in text


def test_apply_preserves_frontmatter_key_order(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("---\nzeta: 1\nalpha: 2\ntags: [x]\n---\nbody\n")
    _apply_to_note(note, ["t"], "t")
    text = note.read_text()
    assert text.index("zeta") < text.index("alpha"), "dumps must not sort keys"


def test_apply_leaves_no_tmp_file(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("---\ntitle: N\n---\nbody\n")
    _apply_to_note(note, ["t"], None)
    assert list(tmp_path.glob("*.tmp")) == []


def _store_with_area_topic(tmp_path, area="dev"):
    """Active manual topic 'rust-macros' assigned to a registry area, with
    a primary member note — apply owns its area/<slug> tag."""
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.add_manual_topic(
        "rust-macros", "Rust Macros", "rust", np.array([1, 0, 0], np.float32)
    )
    s.set_topic_area("rust-macros", area)
    s.set_members(
        "rust-macros",
        [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto", is_primary=True)],
    )
    return s


def test_apply_adds_area_tag_from_primary_topic_area(tmp_path):
    # A note whose primary topic carries area "dev" gains exactly one area/dev tag.
    s = _store_with_area_topic(tmp_path, area="dev")
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\ntags: [Dev/Rust]\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert "area/dev" in fm["tags"]
    assert "topic/rust-macros" in fm["tags"]  # topic tag still applied alongside
    assert fm["tags"].count("area/dev") == 1


def test_apply_replaces_stale_area_tag(tmp_path):
    # A pre-existing stale area/ai is the ONE sanctioned removal (scoped to area/*):
    # apply owns the area vocabulary for topicked notes, so it swaps in area/dev.
    s = _store_with_area_topic(tmp_path, area="dev")
    _note(
        tmp_path, "Knowledge/a.md",
        "---\ntitle: A\ntags: [Dev/Rust, area/ai]\n---\nbody",
    )
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert "area/dev" in fm["tags"]
    assert "area/ai" not in fm["tags"]  # stale area/* removed in place
    assert "Dev/Rust" in fm["tags"]  # non-area tags untouched


def test_apply_leaves_area_tag_when_primary_has_no_area(tmp_path):
    # The primary topic has NO area → apply must not touch the note's area/* tags.
    s = _store_with_active_topic(tmp_path)  # rust-macros has no area set
    _note(
        tmp_path, "Knowledge/a.md",
        "---\ntitle: A\ntags: [Dev/Rust, area/ai]\n---\nbody",
    )
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert "area/ai" in fm["tags"]  # untouched — apply only owns area for areaed topics


def test_apply_area_tag_is_idempotent(tmp_path):
    s = _store_with_area_topic(tmp_path, area="dev")
    _note(tmp_path, "Knowledge/a.md", "---\ntitle: A\ntags: [Dev/Rust]\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    res2 = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "a.md")
    assert fm["tags"].count("area/dev") == 1  # not duplicated on re-run
    assert res2.n_changed == 0  # nothing to do on the second pass


def _store_with_secondary_area_topic(tmp_path, area="dev"):
    """Active topic 'ml' assigned to a registry area whose only member note is a
    SECONDARY (is_primary=False) — the note is the primary of no topic, so no
    existing writer (primary path / classifier mop-up) covers it."""
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.add_manual_topic("ml", "ML", "ml", np.array([1, 0, 0], np.float32))
    s.set_topic_area("ml", area)
    s.set_members(
        "ml",
        [TopicMember(note_path="Knowledge/b.md", score=0.7, source="auto", is_primary=False)],
    )
    return s


def test_apply_fills_area_for_secondary_only_note(tmp_path):
    # A note whose ONLY membership is secondary in an areaed topic gains that area
    # (appended). It has no primary anywhere, so no prior writer set an area for it.
    s = _store_with_secondary_area_topic(tmp_path, area="dev")
    _note(tmp_path, "Knowledge/b.md", "---\ntitle: B\ntags: [Dev/Rust]\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "b.md")
    assert "area/dev" in fm["tags"]
    assert fm["tags"].count("area/dev") == 1
    assert "topic/ml" in fm["tags"]  # topic tag still applied alongside the fill
    assert "primary_topic" not in fm.metadata  # secondary-only: no primary field


def test_apply_fill_does_not_replace_existing_area(tmp_path):
    # FILL-ONLY: a secondary-only note that ALREADY carries an area/* keeps it —
    # unlike the primary path, the fill path never swaps an existing area tag.
    s = _store_with_secondary_area_topic(tmp_path, area="dev")
    _note(
        tmp_path, "Knowledge/b.md",
        "---\ntitle: B\ntags: [Dev/Rust, area/ai]\n---\nbody",
    )
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "b.md")
    assert "area/ai" in fm["tags"]  # pre-existing area preserved exactly
    assert "area/dev" not in fm["tags"]  # fill did NOT replace it


def test_apply_fill_excludes_note_with_primary_elsewhere(tmp_path):
    # A note that is secondary in an areaed topic but PRIMARY in another (arealess)
    # topic is governed by the primary path, so the fill must not touch it: the
    # primary carries no area, so the note ends up with NO area tag at all.
    s = _store_with_secondary_area_topic(tmp_path, area="dev")  # b -> ml, secondary
    s.add_manual_topic("core", "Core", "core", np.array([0, 1, 0], np.float32))
    s.set_members(
        "core",
        [TopicMember(note_path="Knowledge/b.md", score=0.9, source="auto", is_primary=True)],
    )
    _note(tmp_path, "Knowledge/b.md", "---\ntitle: B\ntags: [Dev/Rust]\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "b.md")
    assert not any(t.startswith("area/") for t in fm["tags"])  # fill excluded
    assert fm["primary_topic"] == "core"  # primary path governs the note
    assert "topic/ml" in fm["tags"]  # still a secondary member of ml
    assert "topic/core" in fm["tags"]


def test_apply_no_fill_when_secondary_topic_has_no_area(tmp_path):
    # Secondary-only membership but the topic has NO registry area → nothing to
    # fill: the note gets its topic tag but no area/*.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.add_manual_topic("ml", "ML", "ml", np.array([1, 0, 0], np.float32))  # no area
    s.set_members(
        "ml",
        [TopicMember(note_path="Knowledge/b.md", score=0.7, source="auto", is_primary=False)],
    )
    _note(tmp_path, "Knowledge/b.md", "---\ntitle: B\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "b.md")
    assert "topic/ml" in fm["tags"]
    assert not any(t.startswith("area/") for t in fm["tags"])


def test_apply_fill_picks_best_scoring_secondary_area(tmp_path):
    # Two areaed secondary memberships → the higher-scoring topic's area wins,
    # and only one area tag is written.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.add_manual_topic("ml", "ML", "ml", np.array([1, 0, 0], np.float32))
    s.set_topic_area("ml", "research")
    s.add_manual_topic("rust", "Rust", "rust", np.array([0, 1, 0], np.float32))
    s.set_topic_area("rust", "dev")
    s.set_members("ml", [TopicMember("Knowledge/b.md", 0.6, "auto", is_primary=False)])
    s.set_members("rust", [TopicMember("Knowledge/b.md", 0.9, "auto", is_primary=False)])
    _note(tmp_path, "Knowledge/b.md", "---\ntitle: B\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "b.md")
    assert "area/dev" in fm["tags"]  # rust (0.9) beats ml (0.6)
    assert "area/research" not in fm["tags"]
    assert fm["tags"].count("area/dev") == 1


def test_apply_fill_breaks_score_ties_by_slug(tmp_path):
    # Equal scores → the smallest topic slug wins (deterministic selection).
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.add_manual_topic("aaa", "AAA", "a", np.array([1, 0, 0], np.float32))
    s.set_topic_area("aaa", "alpha")
    s.add_manual_topic("bbb", "BBB", "b", np.array([0, 1, 0], np.float32))
    s.set_topic_area("bbb", "beta")
    s.set_members("aaa", [TopicMember("Knowledge/b.md", 0.8, "auto", is_primary=False)])
    s.set_members("bbb", [TopicMember("Knowledge/b.md", 0.8, "auto", is_primary=False)])
    _note(tmp_path, "Knowledge/b.md", "---\ntitle: B\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "b.md")
    assert "area/alpha" in fm["tags"]  # slug 'aaa' < 'bbb' wins the tie
    assert "area/beta" not in fm["tags"]


def test_apply_fill_area_is_idempotent(tmp_path):
    s = _store_with_secondary_area_topic(tmp_path, area="dev")
    _note(tmp_path, "Knowledge/b.md", "---\ntitle: B\ntags: [Dev/Rust]\n---\nbody")
    apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    res2 = apply_topic_tags(s, vault_path=tmp_path, only_status=("active",))
    fm = frontmatter.load(tmp_path / "Knowledge" / "b.md")
    assert fm["tags"].count("area/dev") == 1  # not duplicated on re-run
    assert res2.n_changed == 0  # nothing to do on the second pass


def test_apply_to_note_fill_appends_area_when_absent(tmp_path):
    # Unit: fill_area_slug appends area/<slug> when the note has no area/* tag,
    # and counts no TOPIC tags (fill is area-only).
    note = tmp_path / "n.md"
    note.write_text("---\ntitle: N\ntags: [old]\n---\nbody\n")
    changed, added = _apply_to_note(note, [], None, None, fill_area_slug="dev")
    assert (changed, added) == (True, 0)
    fm = frontmatter.load(note)
    assert "area/dev" in fm["tags"]
    assert "old" in fm["tags"]


def test_apply_to_note_fill_noop_when_area_present(tmp_path):
    # Unit: an existing area/* blocks the fill entirely — no write, no change.
    note = tmp_path / "n.md"
    note.write_text("---\ntitle: N\ntags: [area/ai]\n---\nbody\n")
    changed, added = _apply_to_note(note, [], None, None, fill_area_slug="dev")
    assert (changed, added) == (False, 0)
    assert note.read_text().count("area/") == 1  # untouched
