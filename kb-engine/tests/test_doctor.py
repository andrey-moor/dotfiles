import time

from kb_engine.config import Config
from kb_engine.doctor import check_digest_fresh, check_launchd, run_checks


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


def test_launchd_check_parses_agent_names():
    out = "1\t0\torg.nix-community.home.kb-engine-pipeline-daily\n"
    assert not check_launchd(out).ok  # weekly missing
    out += "2\t0\torg.nix-community.home.kb-engine-pipeline-weekly\n"
    assert check_launchd(out).ok


def test_run_checks_reports_missing_vault(tmp_path):
    cfg = Config(vault_path=tmp_path / "nope", db_path=tmp_path / "kb.db")
    checks = {c.name: c for c in run_checks(cfg)}
    assert checks["vault"].ok is False and checks["vault"].severity == "hard"
