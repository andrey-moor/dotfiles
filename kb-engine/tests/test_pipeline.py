import json

from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
from kb_engine.models import TopicMember
from kb_engine.pipeline import PipelineResult, run_pipeline
from kb_engine.store import Store
from kb_engine.topics.clustering import FakeClusterer


def _vault(tmp_path):
    """A vault with two Knowledge notes (synced) and one inbox stub."""
    k = tmp_path / "Knowledge"
    k.mkdir()
    (k / "a.md").write_text("---\ntitle: Rust A\n---\nrust macros and borrow checker")
    (k / "b.md").write_text("---\ntitle: Rust B\n---\nrust async tokio runtime")
    inbox = k / "inbox"
    inbox.mkdir()
    (inbox / "x.md").write_text(
        "---\ntitle: X\nurl: https://e.com/x\nstatus: inbox\n---\n## Notes"
    )
    return tmp_path


def test_pipeline_runs_steps_and_summarizes(tmp_path):
    # Two notes both clustered into one topic (labels 0,0); inbox has one stub.
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    embedder = FakeEmbedder(dim=cfg.embed_dim)
    clusterer = FakeClusterer(labels=[0, 0])
    try:
        res = run_pipeline(cfg, store, embedder, clusterer)
    finally:
        store.close()

    assert isinstance(res, PipelineResult)
    assert res.synced == 2  # both notes embedded
    assert res.applied == 0  # no active topics yet -> no note mutation
    assert res.proposals == 1  # one discovered proposal from the cluster
    assert (cfg.vault_path / "_system" / "kb-digest.md").exists()
    assert res.digest_path == "_system/kb-digest.md"


def test_pipeline_only_applies_active_topics_no_mutation(tmp_path):
    # Discovered proposals stay `proposed`, so no topic/ tag is written to notes.
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    try:
        run_pipeline(cfg, store, FakeEmbedder(dim=cfg.embed_dim), FakeClusterer(labels=[0, 0]))
    finally:
        store.close()

    body_a = (cfg.vault_path / "Knowledge" / "a.md").read_text()
    body_b = (cfg.vault_path / "Knowledge" / "b.md").read_text()
    assert "topic/" not in body_a
    assert "topic/" not in body_b


def test_pipeline_applies_active_manual_topic(tmp_path):
    # An active manual topic with a member note IS applied (the only mutation path).
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    embedder = FakeEmbedder(dim=cfg.embed_dim)
    store.init_schema()
    # Anchor with an embedding of matching dim (as the `topics add` CLI does).
    store.add_manual_topic("rust", "Rust", "rust", embedder.embed_query("rust"))
    store.set_members(
        "rust", [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]
    )
    try:
        res = run_pipeline(cfg, store, embedder, FakeClusterer(labels=[0]))
    finally:
        store.close()

    assert res.applied >= 1
    assert "topic/rust" in (cfg.vault_path / "Knowledge" / "a.md").read_text()


def test_pipeline_empty_vault(tmp_path):
    # No Knowledge dir at all: nothing synced/applied/proposed, digest still written.
    cfg = Config(vault_path=tmp_path, db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    try:
        res = run_pipeline(cfg, store, FakeEmbedder(dim=cfg.embed_dim), FakeClusterer(labels=[]))
    finally:
        store.close()

    assert res.synced == 0
    assert res.applied == 0
    assert res.proposals == 0
    assert res.unfiled == 0
    assert (cfg.vault_path / "_system" / "kb-digest.md").exists()


def test_pipeline_cli_json(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0")
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = CliRunner().invoke(
        main, ["--vault", str(v), "--db", str(db), "pipeline", "--json"]
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert {"synced", "applied", "proposals", "unfiled", "digest_path"} <= out.keys()
    assert out["synced"] == 2
    assert out["applied"] == 0  # no active topics -> no mutation
    assert out["digest_path"] == "_system/kb-digest.md"
    assert (v / "_system" / "kb-digest.md").exists()


def test_pipeline_cli_human_output(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0")
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = CliRunner().invoke(main, ["--vault", str(v), "--db", str(db), "pipeline"])
    assert r.exit_code == 0, r.output
    assert "pipeline" in r.output.lower()
