import numpy as np
import frontmatter

from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store
from kb_engine.topics.apply import ApplyResult, apply_topic_tags


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
