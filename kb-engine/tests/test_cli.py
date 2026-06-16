import json

from click.testing import CliRunner

from kb_engine.cli import main


def _vault(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir()
    (k / "mem.md").write_text(
        "---\ntitle: Memory\ntags: [AI]\n---\nlong term memory for agents"
    )
    return tmp_path


def _invoke(args, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    return CliRunner().invoke(main, args)


def test_sync_then_search_json(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = _invoke(["--vault", str(v), "--db", str(db), "sync", "--json"], monkeypatch)
    assert r.exit_code == 0
    assert json.loads(r.output)["added"] == 1

    r2 = _invoke(
        ["--vault", str(v), "--db", str(db), "search", "memory", "--json"], monkeypatch
    )
    assert r2.exit_code == 0
    hits = json.loads(r2.output)["hits"]
    assert hits and hits[0]["note_path"] == "Knowledge/mem.md"
    assert hits[0]["title"] == "Memory"


def test_search_resolves_titles_human_output(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    _invoke(["--vault", str(v), "--db", str(db), "sync"], monkeypatch)
    r = _invoke(
        ["--vault", str(v), "--db", str(db), "search", "memory"], monkeypatch
    )
    assert r.exit_code == 0
    assert "Memory" in r.output


def test_status_json_reports_counts(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    _invoke(["--vault", str(v), "--db", str(db), "sync"], monkeypatch)
    r = _invoke(["--vault", str(v), "--db", str(db), "status", "--json"], monkeypatch)
    assert r.exit_code == 0
    status = json.loads(r.output)
    assert status["notes"] == 1
    assert status["chunks"] >= 1
    assert status["db_path"] == str(db)


def test_rebuild_json(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    _invoke(["--vault", str(v), "--db", str(db), "sync"], monkeypatch)
    r = _invoke(["--vault", str(v), "--db", str(db), "rebuild", "--json"], monkeypatch)
    assert r.exit_code == 0
    assert json.loads(r.output)["added"] == 1


def test_sync_human_output(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = _invoke(["--vault", str(v), "--db", str(db), "sync"], monkeypatch)
    assert r.exit_code == 0
    assert "added" in r.output.lower()


def test_search_on_unsynced_db_returns_empty_without_crash(tmp_path, monkeypatch):
    # Searching before ever syncing must not raise sqlite "no such table: chunks";
    # the command initializes the schema first and returns zero hits cleanly.
    v = _vault(tmp_path)
    db = tmp_path / "fresh.db"  # never synced
    r = _invoke(
        ["--vault", str(v), "--db", str(db), "search", "memory", "--json"], monkeypatch
    )
    assert r.exit_code == 0
    assert r.exception is None
    assert json.loads(r.output) == {"hits": []}
