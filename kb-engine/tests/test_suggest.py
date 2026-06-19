import json

import numpy as np
from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store
from kb_engine.topics.clustering import FakeClusterer
from kb_engine.topics.suggest import suggest_from_residual


def test_suggest_clusters_only_topicless_notes():
    note_vectors = {
        "Knowledge/a.md": np.ones(8, np.float32),
        "Knowledge/b.md": np.ones(8, np.float32),
        "Knowledge/c.md": np.zeros(8, np.float32),
    }
    in_topic = {"Knowledge/a.md"}  # already filed → excluded from the residual
    result = suggest_from_residual(
        note_vectors,
        in_topic,
        clusterer=FakeClusterer(labels=[0, 0]),  # residual (b, c) → one cluster
        texts_by_path={"Knowledge/b.md": "rust macros", "Knowledge/c.md": "rust async"},
    )
    member_paths = {m.note_path for ms in result.members_by_slug.values() for m in ms}
    assert "Knowledge/a.md" not in member_paths  # filed note excluded
    assert member_paths == {"Knowledge/b.md", "Knowledge/c.md"}
    assert result.n_topics == 1


def test_suggest_empty_residual_returns_empty():
    note_vectors = {"Knowledge/a.md": np.ones(8, np.float32)}
    result = suggest_from_residual(
        note_vectors, {"Knowledge/a.md"}, clusterer=FakeClusterer(labels=[]),
        texts_by_path={},
    )
    assert result.n_topics == 0 and result.topics == ()
    assert result.members_by_slug == {} and result.n_unfiled == 0


def _seed_suggest_store(db):
    store = Store(db)
    store.init_schema()
    # one filed note (member of an active manual topic), two unfiled notes
    store.add_manual_topic("filed", "Filed", "filed", np.array([1, 0, 0, 0], np.float32))
    store.upsert_note(path="Knowledge/filed.md", title="F", sha256="h", tags=[])
    store.replace_chunks("Knowledge/filed.md", [(0, "f", np.array([1, 0, 0, 0], np.float32))])
    store.set_members("filed", [TopicMember("Knowledge/filed.md", 0.9, "auto", is_primary=True)])
    for path in ("Knowledge/u1.md", "Knowledge/u2.md"):
        store.upsert_note(path=path, title="U", sha256="h", tags=[], summary="rust async runtime")
        store.replace_chunks(path, [(0, path, np.array([0, 1, 0, 0], np.float32))])
    store.close()


def test_topics_suggest_dry_run_does_not_persist(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    _seed_suggest_store(db)
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0")  # the 2 residual notes → one cluster
    r = CliRunner().invoke(main, ["--vault", str(tmp_path), "--db", str(db),
                                  "topics", "suggest", "--json"])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["n_topics"] == 1 and out["applied"] is False
    # dry-run persists nothing: only the manual topic remains
    s = Store(db)
    try:
        assert [t.slug for t in s.load_topics()] == ["filed"]
    finally:
        s.close()


def test_topics_suggest_apply_persists_proposed(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    _seed_suggest_store(db)
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0")
    r = CliRunner().invoke(main, ["--vault", str(tmp_path), "--db", str(db),
                                  "topics", "suggest", "--apply", "--json"])
    assert r.exit_code == 0, r.output
    s = Store(db)
    try:
        topics = s.load_topics()
        slugs = {t.slug for t in topics}
        assert "filed" in slugs and len(slugs) == 2  # manual + 1 new discovered proposal
        new = [t for t in topics if t.kind == "discovered"]
        assert len(new) == 1 and new[0].status == "proposed"
    finally:
        s.close()


def test_topics_suggest_apply_replaces_prior_discovered(tmp_path, monkeypatch):
    # --apply uses save_topics, which replaces existing discovered proposals.
    # This documents that intentional footgun: a prior proposal is not kept.
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    prior = Topic(slug="prior", label="Prior", keywords=("x",),
                  centroid=np.zeros(4, np.float32), kind="discovered", status="proposed")
    store.save_topics([prior], {"prior": []})
    for path in ("Knowledge/u1.md", "Knowledge/u2.md"):
        store.upsert_note(path=path, title="U", sha256="h", tags=[], summary="rust async")
        store.replace_chunks(path, [(0, path, np.array([0, 1, 0, 0], np.float32))])
    store.close()
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0")
    r = CliRunner().invoke(main, ["--vault", str(tmp_path), "--db", str(db),
                                  "topics", "suggest", "--apply", "--json"])
    assert r.exit_code == 0, r.output
    s = Store(db)
    try:
        slugs = {t.slug for t in s.load_topics()}
        assert "prior" not in slugs  # replaced, not accumulated
        assert len(slugs) == 1       # only the newly discovered cluster
    finally:
        s.close()
