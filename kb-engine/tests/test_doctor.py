import sqlite3
import time
from pathlib import Path

import pytest

from kb_engine.config import Config
from kb_engine.doctor import (
    _check_db,
    _check_secrets,
    check_digest_fresh,
    check_launchd,
    run_checks,
)


def test_digest_fresh_ok(tmp_path):
    d = tmp_path / "_system"
    d.mkdir()
    f = d / "kb-digest.md"
    f.write_text("# KB Digest\n\n## Status\n\n- Last run: x · tier: daily · ✅ ok\n")
    c = check_digest_fresh(tmp_path, now=time.time())
    assert c.ok and c.severity == "hard"


def test_digest_stale_or_failed(tmp_path):
    d = tmp_path / "_system"
    d.mkdir()
    f = d / "kb-digest.md"
    f.write_text("# KB Digest\n\n## Status\n\n- Last run: x · ⚠️ FAILED\n")
    assert not check_digest_fresh(tmp_path, now=time.time()).ok  # FAILED marker
    f.write_text("# KB Digest\n")
    old = time.time() - 9 * 86400
    import os

    os.utime(f, (old, old))
    assert not check_digest_fresh(tmp_path, now=time.time()).ok  # stale


def test_digest_plain_failed_in_step_detail_is_ok(tmp_path):
    d = tmp_path / "_system"
    d.mkdir()
    f = d / "kb-digest.md"
    f.write_text(
        "# KB Digest\n\n## Status\n\n"
        "- Last run: x · tier: daily · ✅ ok\n"
        "- import-mail: upstream FAILED to serve 1 url (step kept going)\n"
    )
    c = check_digest_fresh(tmp_path, now=time.time())
    assert c.ok  # only the Status marker "⚠️ FAILED" trips the check


def test_check_db_closes_connection_when_pragma_raises(tmp_path, monkeypatch):
    garbage = tmp_path / "kb.db"
    garbage.write_text("this is not a sqlite database")
    captured = []
    real_connect = sqlite3.connect

    def capturing_connect(path):
        conn = real_connect(path)
        captured.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", capturing_connect)
    check = _check_db(garbage)
    assert check.ok is False and check.severity == "hard"
    # The handle must be released even though the PRAGMA raised.
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        captured[0].execute("SELECT 1")


def test_launchd_check_parses_agent_names():
    out = "1\t0\torg.nix-community.home.kb-engine-pipeline-daily\n"
    assert not check_launchd(out).ok  # weekly missing
    out += "2\t0\torg.nix-community.home.kb-engine-pipeline-weekly\n"
    assert check_launchd(out).ok


def test_run_checks_reports_missing_vault(tmp_path):
    cfg = Config(vault_path=tmp_path / "nope", db_path=tmp_path / "kb.db")
    checks = {c.name: c for c in run_checks(cfg)}
    assert checks["vault"].ok is False and checks["vault"].severity == "hard"


def _write_secrets(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    d = tmp_path / ".config" / "kb-engine"
    d.mkdir(parents=True)
    f = d / "secrets.env"
    f.write_text("FASTMAIL_API_TOKEN=\nANTHROPIC_API_KEY=\n")
    f.chmod(mode)
    return f


def test_check_secrets_missing_file_fails_hard(tmp_path, monkeypatch):
    # Phase 3 made secrets mandatory: a missing file is now a hard failure.
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    c = _check_secrets()
    assert c.name == "secrets" and c.ok is False and c.severity == "hard"


def test_check_secrets_wrong_mode_fails_hard(tmp_path, monkeypatch):
    _write_secrets(tmp_path, monkeypatch, 0o644)
    c = _check_secrets()
    assert c.ok is False and c.severity == "hard"


def test_check_secrets_present_and_0600_passes(tmp_path, monkeypatch):
    # Empty values still pass — the check is existence + 0600 mode, not contents.
    _write_secrets(tmp_path, monkeypatch, 0o600)
    c = _check_secrets()
    assert c.ok is True and c.severity == "hard"
