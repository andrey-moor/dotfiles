import json

from click.testing import CliRunner

from kb_engine.cli import main


def _mk_vault(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir(parents=True)
    (k / "a.md").write_text("---\ntitle: Alpha note\nsummary: about alpha\n---\nalpha body")
    sysdir = tmp_path / "_system"
    sysdir.mkdir()
    (sysdir / "probes.yaml").write_text(
        '- query: "alpha"\n  expect:\n    - "Knowledge/a.md"\n'
    )
    return tmp_path


def test_eval_json_shape(tmp_path, monkeypatch):
    vault = _mk_vault(tmp_path)
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    runner = CliRunner()
    db = tmp_path / "kb.db"
    sync = runner.invoke(main, ["--vault", str(vault), "--db", str(db), "sync"])
    assert sync.exit_code == 0, sync.output
    result = runner.invoke(main, ["--vault", str(vault), "--db", str(db), "eval", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["k"] == 5
    assert set(payload) == {"k", "recall", "mrr", "probes"}
    assert payload["probes"][0]["query"] == "alpha"


def test_eval_missing_probes_file_errors_cleanly(tmp_path, monkeypatch):
    vault = tmp_path
    (vault / "Knowledge").mkdir()
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--vault", str(vault), "--db", str(tmp_path / "kb.db"), "eval"]
    )
    assert result.exit_code != 0
    assert "probes.yaml" in result.output
