import numpy as np

from kb_engine.importing.digest import DigestStatus, build_digest, count_proposals
from kb_engine.models import Area, QueueEntry, Topic, TopicMember
from kb_engine.pipeline import StepOutcome
from kb_engine.store import Store


def _seeded_store(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    for path in ("Knowledge/a.md", "Knowledge/b.md"):
        s.upsert_note(path=path, title=path, sha256="h", tags=[])
    proposed = Topic(
        slug="rust",
        label="Rust",
        keywords=("rust", "macros"),
        centroid=np.array([1, 0, 0], np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics(
        [proposed],
        {"rust": [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]},
    )
    s.add_manual_topic("llm", "LLM", "llm", np.array([0, 1, 0], np.float32))
    s.save_areas([Area(slug="ai", label="AI", topic_slugs=("rust", "llm"))])
    return s


def test_build_digest_reports_state(tmp_path):
    store = _seeded_store(tmp_path)
    text = build_digest(
        store, vault_path=tmp_path, inbox_count=5, unfiled=["Knowledge/x.md"]
    )
    assert "Inbox" in text and "5" in text
    assert "proposed" in text.lower()
    # 2 topics (1 proposed + 1 manual), 1 area, 1 unfiled
    assert "2" in text  # topics count
    assert "Knowledge/x.md" in text  # unfiled listed in the checklist


def test_build_digest_is_idempotent_no_timestamps(tmp_path):
    store = _seeded_store(tmp_path)
    status = DigestStatus(
        tier="weekly", ok=True, outcomes=(StepOutcome("sync", True, "0 added"),)
    )
    a = build_digest(store, vault_path=tmp_path, inbox_count=3, unfiled=[], status=status)
    b = build_digest(store, vault_path=tmp_path, inbox_count=3, unfiled=[], status=status)
    # The Status header carries a render-time timestamp; the body below
    # ## Summary stays deterministic — that is the idempotency contract now.
    body_a = a.split("## Summary", 1)[1]
    body_b = b.split("## Summary", 1)[1]
    assert body_a == body_b
    # no obvious date stamp leaked into the deterministic body
    assert "2026-" not in body_a


def test_build_digest_status_header_renders_failed_run(tmp_path):
    store = _seeded_store(tmp_path)
    status = DigestStatus(
        tier="daily",
        ok=False,
        outcomes=(
            StepOutcome("sync", False, "OSError: boom"),
            StepOutcome("import-mail", True, "skipped: no FASTMAIL_API_TOKEN"),
        ),
    )
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[], status=status)
    assert text.startswith("# KB Digest")
    assert "## Status" in text
    assert "tier: daily" in text and "FAILED" in text
    assert "- sync: OSError: boom" in text
    assert "- import-mail: skipped: no FASTMAIL_API_TOKEN" in text
    # the Status section precedes the deterministic Summary body
    assert text.index("## Status") < text.index("## Summary")


def test_build_digest_without_status_has_no_status_header(tmp_path):
    # The standalone `digest` command passes no status: no header, no timestamp.
    store = _seeded_store(tmp_path)
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "## Status" not in text
    assert text.startswith("# KB Digest\n\n## Summary")


def test_build_digest_empty_state(tmp_path):
    s = Store(tmp_path / "empty.db")
    s.init_schema()
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "Inbox" in text
    assert isinstance(text, str) and text.strip()


def test_count_proposals_counts_discovered_and_proposed(tmp_path):
    store = _seeded_store(tmp_path)
    # 1 proposed discovered topic; the manual one is active, not counted
    assert count_proposals(store.load_topics()) == 1


def test_build_digest_truncates_long_unfiled_list(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    unfiled = [f"Knowledge/n{i:03}.md" for i in range(30)]
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=unfiled)
    assert "…and 5 more" in text
    # only the first 25 are listed inline
    assert text.count("[[Knowledge/n") == 25


def test_digest_renders_borderline_queue(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.replace_review_queue([
        QueueEntry("Knowledge/a.md", (("rust-learning", 0.52), ("rust-tooling", 0.47)),
                   "borderline"),
        QueueEntry("Knowledge/b.md", (("ui-design", 0.49),), "borderline"),
    ])
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "## Borderline queue" in text
    assert "- [ ] Decide 2 borderline assignment(s)" in text
    a = text.index("Knowledge/a.md")
    b = text.index("Knowledge/b.md")
    assert a < b  # best top-candidate first
    assert "rust-learning (0.52)" in text
    store.close()


def test_digest_no_queue_section_when_empty(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "Borderline queue" not in text
    store.close()


def test_digest_reports_notes_with_area_coverage(tmp_path):
    # One of two notes carries an area/* tag → coverage line reads 1/2.
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=["area/ai"])
    store.upsert_note(path="Knowledge/b.md", title="B", sha256="h", tags=[])
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "- Notes with area: 1/2" in text
    store.close()
