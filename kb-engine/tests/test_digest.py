import numpy as np

from kb_engine.importing.digest import build_digest, count_proposals
from kb_engine.models import Area, Topic, TopicMember
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
    a = build_digest(store, vault_path=tmp_path, inbox_count=3, unfiled=[])
    b = build_digest(store, vault_path=tmp_path, inbox_count=3, unfiled=[])
    assert a == b
    # no obvious date stamp leaked into the body
    assert "2026-" not in a


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
