import json

from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
from kb_engine.importing.digest import write_digest
from kb_engine.models import TopicMember
from kb_engine.pipeline import PipelineResult, run_pipeline, unfiled_notes
from kb_engine.store import Store
from kb_engine.sync import sync
from kb_engine.topics.clustering import FakeClusterer

_WEEKLY_STEPS = ["import-mail", "enrich", "backfill", "sync", "apply-topics", "discover", "eval"]


def _vault(tmp_path):
    """A vault with two Knowledge notes and one inbox stub — all three are
    synced now that the inbox is indexed (Phase-3 change)."""
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


def test_unfiled_excludes_inbox_but_keeps_topicless_notes(tmp_path):
    # unfiled = filed but topicless; synced inbox stubs must NOT count as
    # unfiled — the digest already tracks them via the separate inbox backlog.
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    try:
        sync(cfg, store, FakeEmbedder(dim=cfg.embed_dim))  # indexes inbox/x.md too
        unfiled = unfiled_notes(store)
        digest_text = write_digest(cfg, store).read_text()
    finally:
        store.close()

    assert "Knowledge/a.md" in unfiled  # filed but topicless → listed
    assert "Knowledge/inbox/x.md" not in unfiled
    assert "[[Knowledge/a.md]]" in digest_text  # digest unfiled list mirrors it
    assert "Knowledge/inbox/x.md" not in digest_text


def test_pipeline_runs_steps_and_summarizes(tmp_path, monkeypatch):
    # All three notes (incl. inbox) clustered into one topic; default weekly tier.
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)  # import-mail skips
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    cfg = Config(vault_path=_vault(tmp_path), db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    embedder = FakeEmbedder(dim=cfg.embed_dim)
    clusterer = FakeClusterer(labels=[0, 0, 0])
    try:
        res = run_pipeline(cfg, store, embedder, clusterer)
    finally:
        store.close()

    assert isinstance(res, PipelineResult)
    assert res.tier == "weekly"
    assert res.ok is True  # skips (mail/eval) count as ok, no step raised
    assert [o.name for o in res.outcomes] == _WEEKLY_STEPS
    by_name = {o.name: o for o in res.outcomes}
    assert "3 added" in by_name["sync"].detail  # all three (incl. inbox) embedded
    assert "skipped: no FASTMAIL_API_TOKEN" == by_name["import-mail"].detail
    assert by_name["apply-topics"].detail.startswith("0 changed")  # no active topics
    assert "1 new topic(s)" in by_name["discover"].detail  # one proposal from the cluster
    assert "skipped: no probes.yaml" == by_name["eval"].detail
    assert res.digest_path is not None and res.digest_path.name == "kb-digest.md"
    assert (cfg.vault_path / "_system" / "kb-digest.md").exists()


def test_pipeline_only_applies_active_topics_no_mutation(tmp_path, monkeypatch):
    # Discovered proposals stay `proposed`, so no topic/ tag is written to notes.
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
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


def test_pipeline_applies_active_manual_topic(tmp_path, monkeypatch):
    # An active manual topic with a member note IS applied (the only mutation path).
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
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

    by_name = {o.name: o for o in res.outcomes}
    assert by_name["apply-topics"].ok
    assert by_name["apply-topics"].detail.startswith("1 changed")
    assert "topic/rust" in (cfg.vault_path / "Knowledge" / "a.md").read_text()


def test_pipeline_empty_vault(tmp_path, monkeypatch):
    # No Knowledge dir at all: every step is a clean no-op, digest still written.
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    cfg = Config(vault_path=tmp_path, db_path=tmp_path / "t.db")
    store = Store(cfg.db_path)
    try:
        res = run_pipeline(cfg, store, FakeEmbedder(dim=cfg.embed_dim), FakeClusterer(labels=[]))
    finally:
        store.close()

    assert res.ok is True
    assert [o.name for o in res.outcomes] == _WEEKLY_STEPS
    by_name = {o.name: o for o in res.outcomes}
    assert by_name["sync"].detail.startswith("0 added")
    assert (cfg.vault_path / "_system" / "kb-digest.md").exists()


def test_pipeline_daily_tier_cli_skips_topic_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = CliRunner().invoke(
        main, ["--vault", str(v), "--db", str(db), "pipeline", "--tier", "daily", "--json"]
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["tier"] == "daily"
    assert [o["name"] for o in out["outcomes"]] == ["import-mail", "enrich", "sync"]


def test_pipeline_cli_json(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0")
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = CliRunner().invoke(
        main, ["--vault", str(v), "--db", str(db), "pipeline", "--json"]
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert {"tier", "ok", "outcomes", "counts", "digest_path"} <= out.keys()
    assert out["tier"] == "weekly"  # default tier
    assert out["ok"] is True
    assert [o["name"] for o in out["outcomes"]] == _WEEKLY_STEPS
    # counts feed the launchd runner's review-queue notification.
    assert set(out["counts"]) == {"inbox", "proposals", "unfiled"}
    assert all(isinstance(n, int) for n in out["counts"].values())
    assert out["counts"]["inbox"] == 1  # the fixture's single inbox stub
    assert out["counts"]["proposals"] == 1  # the 0,0 cluster's proposed topic
    assert out["digest_path"].endswith("_system/kb-digest.md")
    assert (v / "_system" / "kb-digest.md").exists()


def test_pipeline_cli_human_output(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0")
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)  # enrich skips, no network
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = CliRunner().invoke(main, ["--vault", str(v), "--db", str(db), "pipeline"])
    assert r.exit_code == 0, r.output
    assert "pipeline" in r.output.lower()  # the trailing summary line
    assert "✅ sync —" in r.output  # one marked line per step outcome
