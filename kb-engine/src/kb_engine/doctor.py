"""Health checks: the KB must never look healthier than it is."""

import os
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from kb_engine.config import Config

DIGEST_MAX_AGE_S = 8 * 86400
GIT_MAX_AGE_S = 48 * 3600
AGENTS = (
    "org.nix-community.home.kb-engine-pipeline-daily",
    "org.nix-community.home.kb-engine-pipeline-weekly",
)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    severity: str  # "hard" | "warn"
    detail: str


def check_digest_fresh(vault_path: Path, now: float) -> Check:
    digest = vault_path / "_system" / "kb-digest.md"
    if not digest.is_file():
        return Check("digest-fresh", False, "hard", "kb-digest.md missing")
    age = now - digest.stat().st_mtime
    if age > DIGEST_MAX_AGE_S:
        return Check("digest-fresh", False, "hard", f"digest is {age / 86400:.1f} days old")
    head = digest.read_text()[:600]
    if "FAILED" in head:
        return Check("digest-fresh", False, "hard", "last pipeline run FAILED")
    return Check("digest-fresh", True, "hard", "fresh and ok")


def check_launchd(launchctl_output: str) -> Check:
    missing = [a for a in AGENTS if a not in launchctl_output]
    if missing:
        return Check("launchd", False, "warn", f"not loaded: {', '.join(missing)}")
    return Check("launchd", True, "warn", "both tiers loaded")


def _check_db(db_path: Path) -> Check:
    if not db_path.is_file():
        return Check("db", False, "hard", f"missing: {db_path}")
    try:
        # NOT mode=ro: the DB is in WAL mode (Phase 0) and read-only URI opens
        # fail with SQLITE_CANTOPEN(14) when the -wal/-shm sidecars need creating.
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA query_only=ON")
        row = conn.execute("PRAGMA integrity_check").fetchone()
        conn.close()
    except sqlite3.Error as exc:
        return Check("db", False, "hard", str(exc))
    return Check("db", row[0] == "ok", "hard", str(row[0]))


def _check_secrets() -> Check:
    p = Path.home() / ".config" / "kb-engine" / "secrets.env"
    if not p.is_file():
        return Check("secrets", False, "warn", f"missing: {p} (required from Phase 3)")
    mode = p.stat().st_mode & 0o777
    return Check("secrets", mode == 0o600, "warn", f"mode {oct(mode)}")


def _check_vault_git(vault_path: Path, now: float) -> Check:
    try:
        out = subprocess.run(
            ["git", "-C", str(vault_path), "log", "-1", "--format=%ct"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        age = now - int(out)
    except Exception as exc:  # noqa: BLE001 — advisory check
        return Check("vault-git", False, "warn", f"unavailable: {exc}")
    return Check("vault-git", age <= GIT_MAX_AGE_S, "warn", f"last commit {age / 3600:.0f}h ago")


def _check_model_cache() -> Check:
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    hit = hub.is_dir() and any("jina" in p.name for p in hub.iterdir())
    return Check("model-cache", bool(hit), "warn", str(hub))


def run_checks(cfg: Config, now: float | None = None) -> tuple[Check, ...]:
    now = time.time() if now is None else now
    checks = [
        Check("vault", cfg.vault_path.is_dir(), "hard", str(cfg.vault_path)),
        _check_db(cfg.db_path),
        check_digest_fresh(cfg.vault_path, now),
        _check_secrets(),
        _check_vault_git(cfg.vault_path, now),
        _check_model_cache(),
    ]
    try:
        out = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=10
        ).stdout
        checks.append(check_launchd(out))
    except Exception as exc:  # noqa: BLE001 — advisory check
        checks.append(Check("launchd", False, "warn", f"unavailable: {exc}"))
    return tuple(checks)
