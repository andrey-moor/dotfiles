import numpy as np
from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store


def test_topics_add_creates_manual_topic(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    db = tmp_path / "t.db"
    args = ["--vault", str(tmp_path), "--db", str(db)]
    r = CliRunner().invoke(
        main,
        args
        + [
            "topics",
            "add",
            "my-topic",
            "--label",
            "My Topic",
            "--description",
            "about rust filesystems",
        ],
    )
    assert r.exit_code == 0
    topics = {t.slug: t for t in Store(db).load_topics()}
    assert topics["my-topic"].kind == "manual" and topics["my-topic"].status == "active"
    assert topics["my-topic"].centroid.shape[0] > 0  # embedded the description


def test_manual_topic_survives_rediscover(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    db = tmp_path / "t.db"
    args = ["--vault", str(tmp_path), "--db", str(db)]
    CliRunner().invoke(
        main,
        args + ["topics", "add", "manual-one", "--label", "Manual", "--description", "x"],
    )
    # A subsequent discover (save_topics of a discovered topic) must NOT delete
    # the manual topic — only kind='discovered' rows are replaced.
    store = Store(db)
    discovered = Topic(
        slug="disc-one",
        label="Disc",
        keywords=("disc",),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    store.save_topics([discovered], {"disc-one": []})
    slugs = {t.slug: t.kind for t in store.load_topics()}
    assert slugs == {"manual-one": "manual", "disc-one": "discovered"}


def test_topics_add_rejects_duplicate_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    db = tmp_path / "t.db"
    args = ["--vault", str(tmp_path), "--db", str(db)]
    base = ["topics", "add", "dup", "--label", "Dup", "--description", "x"]
    r1 = CliRunner().invoke(main, args + base)
    assert r1.exit_code == 0
    r2 = CliRunner().invoke(main, args + base)
    assert r2.exit_code != 0  # duplicate slug rejected


def test_add_manual_topic_store_rejects_duplicate(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.add_manual_topic("solo", "Solo", "desc", np.ones(4, np.float32))
    try:
        s.add_manual_topic("solo", "Solo2", "desc2", np.ones(4, np.float32))
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_topics_add_rejects_traversal_slug_and_creates_no_topic(tmp_path, monkeypatch):
    # A slug like "../evil" must be rejected at the CLI boundary (non-zero exit,
    # clear message) and must NOT create a topic — it could otherwise escape
    # _system/topics/ when rendered.
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    db = tmp_path / "t.db"
    args = ["--vault", str(tmp_path), "--db", str(db)]
    r = CliRunner().invoke(
        main,
        args + ["topics", "add", "../evil", "--label", "Evil", "--description", "x"],
    )
    assert r.exit_code != 0
    assert "slug" in r.output.lower()
    s = Store(db)
    s.init_schema()
    assert s.load_topics() == []  # no topic created


def test_add_manual_topic_store_rejects_invalid_slug(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    for bad in ("../escape", "Foo", "has space", "-leading", "under_score", ""):
        try:
            s.add_manual_topic(bad, "Label", "desc", np.ones(4, np.float32))
            raised = False
        except ValueError:
            raised = True
        assert raised, f"expected ValueError for slug {bad!r}"
    assert s.load_topics() == []  # nothing persisted


def test_topics_list_reports_kind_and_size(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    db = tmp_path / "t.db"
    s = Store(db)
    s.init_schema()
    discovered = Topic(
        slug="disc",
        label="Disc",
        keywords=("disc",),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics(
        [discovered],
        {"disc": [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]},
    )
    s.add_manual_topic("man", "Man", "desc", np.ones(4, np.float32))
    s.close()
    import json

    args = ["--vault", str(tmp_path), "--db", str(db)]
    r = CliRunner().invoke(main, args + ["topics", "list", "--json"])
    assert r.exit_code == 0
    by_slug = {row["slug"]: row for row in json.loads(r.output)["topics"]}
    assert by_slug["man"]["kind"] == "manual" and by_slug["man"]["size"] == 0
    assert by_slug["disc"]["kind"] == "discovered" and by_slug["disc"]["size"] == 1
