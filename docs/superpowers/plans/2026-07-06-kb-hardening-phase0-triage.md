# KB Hardening Phase 0 — Triage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the active bleeding — vault under git, DB safe for concurrent access,
sync that survives unreadable files, and a manually-verified truthful digest.

**Architecture:** Three tiny code changes (store pragmas, tolerant vault walk) + git/nix
setup + one supervised live run. No schema or behavior redesign.

**Tech Stack:** Python 3.12 + pytest (via `uv run` from `kb-engine/`), git, nix-darwin
home-manager launchd.

## Global Constraints

See master plan `2026-07-06-kb-hardening-00-master.md` — eval gate does not apply yet
(Phase 1 creates it); TDD, immutability, commit-per-task, quoted vault path all apply.

**Vault:** `/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main`
**Reminder for the user (not a task):** rotate the Fastmail API token now (master plan
checklist).

---

### Task 1: Vault under git + nightly auto-commit

**Files:**
- Create: `<vault>/.gitignore` (vault path above)
- Modify: the nix module that declares `kb-engine-pipeline` (locate in step 3; expected
  under `modules/home/`)

**Interfaces:**
- Produces: a git repo at the vault root; a launchd agent `kb-vault-autocommit` that
  commits vault changes nightly at 21:30. Phase 2's `doctor` and Phase 5's cutover rely
  on this repo existing.

- [ ] **Step 1: Initialize the repo and .gitignore**

```bash
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
cat > "$VAULT/.gitignore" <<'EOF'
.DS_Store
.trash/
.obsidian/workspace*
.obsidian/cache/
*.icloud
EOF
git -C "$VAULT" init
git -C "$VAULT" add -A
git -C "$VAULT" commit -m "chore: initial vault snapshot (pre-hardening-wave)"
```

Expected: commit succeeds; `git -C "$VAULT" log --oneline` shows 1 commit.
(`*.icloud` is ignored so evicted placeholders never enter history.)

- [ ] **Step 2: Verify the repo is clean and functional**

Run: `git -C "$VAULT" status --porcelain | head; git -C "$VAULT" log --oneline -1`
Expected: empty status (or only files changed since step 1); one commit listed.

- [ ] **Step 3: Locate the kb-engine nix module**

Run: `grep -rln "kb-engine" /Users/andreym/Documents/dotfiles/modules/home/`
Expected: one module file (contains the `kb-engine-pipeline` launchd agent). Read it to
learn the local launchd-agent idiom before editing.

- [ ] **Step 4: Add the auto-commit launchd agent to that module**

Add alongside the existing agent, following the module's existing pattern for
`launchd.agents` (adapt attribute nesting to match the file; this is the payload):

```nix
launchd.agents.kb-vault-autocommit = {
  enable = true;
  config = {
    ProgramArguments = [
      "/bin/sh" "-c"
      ''cd "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main" && ${pkgs.git}/bin/git add -A && (${pkgs.git}/bin/git diff --cached --quiet || ${pkgs.git}/bin/git commit -m "auto: $(date +%F)")''
    ];
    StartCalendarInterval = [ { Hour = 21; Minute = 30; } ];
    StandardErrorPath = "/Users/andreym/Library/Logs/kb-vault-autocommit.err";
    StandardOutPath = "/Users/andreym/Library/Logs/kb-vault-autocommit.log";
  };
};
```

- [ ] **Step 5: Apply and verify the agent is loaded**

```bash
cd /Users/andreym/Documents/dotfiles && just switch
launchctl list | grep kb-vault-autocommit
```

Expected: `just switch` succeeds; `launchctl list` shows the agent (exit code `-` or 0,
not a nonzero last-exit).

- [ ] **Step 6: Exercise the agent script once by hand**

```bash
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
touch "$VAULT/_system/.autocommit-probe"
cd "$VAULT" && git add -A && (git diff --cached --quiet || git commit -m "auto: probe")
git -C "$VAULT" log --oneline -1
rm "$VAULT/_system/.autocommit-probe"
git -C "$VAULT" add -A && git -C "$VAULT" commit -m "chore: remove autocommit probe"
```

Expected: probe commit then cleanup commit appear in the log.

- [ ] **Step 7: Commit the dotfiles change**

```bash
cd /Users/andreym/Documents/dotfiles
git add modules/
git commit -m "feat(kb): nightly vault auto-commit launchd agent"
```

---

### Task 2: WAL + busy_timeout on the SQLite store

**Files:**
- Modify: `kb-engine/src/kb_engine/store.py` (connection init — anchor: the existing
  `PRAGMA foreign_keys` statement, currently near line 90)
- Test: `kb-engine/tests/test_store_pragmas.py` (create)

**Interfaces:**
- Produces: every `Store` connection runs in WAL mode with a 5000 ms busy timeout.
  Phase 2's concurrent daily pipeline + future MCP reads rely on this.

- [ ] **Step 1: Write the failing test**

Create `kb-engine/tests/test_store_pragmas.py`:

```python
from kb_engine.store import Store


def test_store_uses_wal_and_busy_timeout(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    journal = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    timeout = store._conn.execute("PRAGMA busy_timeout").fetchone()[0]
    assert journal == "wal"
    assert timeout == 5000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest tests/test_store_pragmas.py -v`
Expected: FAIL — journal is `delete` (or `memory`), timeout is 0.

- [ ] **Step 3: Add the pragmas**

In `store.py`, directly after the existing `PRAGMA foreign_keys=ON` execute in the
connection-setup path, add:

```python
self._conn.execute("PRAGMA journal_mode=WAL")
self._conn.execute("PRAGMA busy_timeout=5000")
```

- [ ] **Step 4: Run the full suite**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest`
Expected: new test PASSES; all existing tests still pass (WAL is transparent to them).

- [ ] **Step 5: Commit**

```bash
cd /Users/andreym/Documents/dotfiles
git add kb-engine/src/kb_engine/store.py kb-engine/tests/test_store_pragmas.py
git commit -m "fix(kb-engine): WAL journal mode + 5s busy timeout on the cache DB"
```

---

### Task 3: Tolerant vault walk (unreadable files skip, never abort)

**Files:**
- Modify: `kb-engine/src/kb_engine/vault.py:65-82` (`iter_notes`)
- Modify: `kb-engine/src/kb_engine/sync.py:22-32` (`_disk_notes`)
- Test: `kb-engine/tests/test_vault_tolerance.py` (create)

**Interfaces:**
- Consumes: `iter_notes(root, base, exclude_dirs)` (existing generator).
- Produces: `iter_notes(root, base=None, exclude_dirs=(), on_error=None)` where
  `on_error: Callable[[Path, OSError], None] | None` — called per unreadable file, file
  skipped. `sync._disk_notes` passes a logger-backed `on_error`. Phase 2 formalizes the
  failure count into `SyncStats`; this task only guarantees "never abort".

- [ ] **Step 1: Write the failing test**

Create `kb-engine/tests/test_vault_tolerance.py`:

```python
import os

from kb_engine.vault import iter_notes


def _write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def test_iter_notes_skips_unreadable_files_and_reports(tmp_path):
    _write(tmp_path / "Knowledge" / "ok.md", "---\ntitle: ok\n---\nbody")
    bad = tmp_path / "Knowledge" / "bad.md"
    _write(bad, "---\ntitle: bad\n---\nbody")
    os.chmod(bad, 0o000)
    failures = []
    try:
        notes = list(
            iter_notes(
                tmp_path / "Knowledge",
                base=tmp_path,
                on_error=lambda path, exc: failures.append(path.name),
            )
        )
    finally:
        os.chmod(bad, 0o644)  # so tmp_path cleanup works
    assert [n.title for n in notes] == ["ok"]
    assert failures == ["bad.md"]


def test_iter_notes_without_handler_still_skips(tmp_path):
    bad = tmp_path / "Knowledge" / "bad.md"
    _write(bad, "x")
    os.chmod(bad, 0o000)
    try:
        assert list(iter_notes(tmp_path / "Knowledge", base=tmp_path)) == []
    finally:
        os.chmod(bad, 0o644)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest tests/test_vault_tolerance.py -v`
Expected: FAIL — `PermissionError` propagates out of `iter_notes` (and `on_error` is an
unexpected keyword).

- [ ] **Step 3: Implement the tolerant walk**

In `vault.py`, replace the `iter_notes` yield with a guarded version:

```python
def iter_notes(
    root: Path,
    base: Path | None = None,
    exclude_dirs: tuple[str, ...] = (),
    on_error: Callable[[Path, OSError], None] | None = None,
) -> Iterator[Note]:
    """Yield notes for every ``*.md`` file under ``root``, sorted by path.

    Unreadable files (iCloud eviction, permissions) are skipped, reported via
    ``on_error`` when given — a single bad file must never abort a sync.
    """
    anchor = root if base is None else base
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        if exclude_dirs and path.relative_to(root).parts[0] in exclude_dirs:
            continue
        try:
            note = read_note(path, base=anchor)
        except OSError as exc:
            if on_error is not None:
                on_error(path, exc)
            continue
        yield note
```

Add `from typing import Callable, Iterator` to the imports (Iterator is already there).

In `sync.py` `_disk_notes`, pass a logging handler:

```python
import logging

logger = logging.getLogger(__name__)


def _log_unreadable(path, exc) -> None:
    logger.warning("skipping unreadable note %s: %s", path, exc)


def _disk_notes(cfg: Config) -> dict[str, Note]:
    """Vault-relative notes under Knowledge/, excluding the inbox."""
    knowledge_dir = cfg.knowledge_dir
    if not knowledge_dir.is_dir():
        return {}
    return {
        note.path: note
        for note in iter_notes(
            knowledge_dir,
            base=cfg.vault_path,
            exclude_dirs=EXCLUDED_DIRS,
            on_error=_log_unreadable,
        )
    }
```

**Known Phase-0 limitation (accepted, fixed in Phase 2):** a skipped file that already
exists in the DB will be counted as deleted by `sync()` on that run and re-added on the
next healthy run. Phase 2's eviction-awareness removes this churn; Phase 0 only
guarantees the run completes.

- [ ] **Step 4: Run the full suite**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest`
Expected: both new tests PASS; existing suite green.

- [ ] **Step 5: Commit**

```bash
cd /Users/andreym/Documents/dotfiles
git add kb-engine/src/kb_engine/vault.py kb-engine/src/kb_engine/sync.py kb-engine/tests/test_vault_tolerance.py
git commit -m "fix(kb-engine): sync walk skips unreadable files instead of aborting"
```

---

### Task 4: Supervised live run — unfreeze the digest

**Files:** none created; live verification against the real vault + DB.

**Interfaces:**
- Consumes: Tasks 2–3 landed.
- Produces: a current, truthful `_system/kb-digest.md`; evidence for the phase-exit
  report.

- [ ] **Step 1: Snapshot current (stale) digest numbers**

Run: `head -12 "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main/_system/kb-digest.md"`
Expected (pre-fix): `Inbox backlog: 0`, `Topic proposals awaiting review: 0`.

- [ ] **Step 2: Run the pipeline manually (real model — slow first call is normal)**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run kb-engine --vault "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main" pipeline`
Expected: completes without traceback. If files were skipped, warnings list them —
record the count. (If it still crashes on something other than a per-file `OSError`,
stop and report — do not improvise fixes outside this plan.)

- [ ] **Step 3: Verify the digest now tells the truth**

Run: `head -20 "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main/_system/kb-digest.md"`
Expected: inbox backlog ≈ 12 (whatever is really in `Knowledge/inbox/`), topic
proposals ≈ 28 (matches `SELECT count(*) FROM topics WHERE kind='discovered' AND
status='proposed'`). Cross-check:

```bash
ls "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main/Knowledge/inbox/"*.md | wc -l
sqlite3 "file:$HOME/.local/state/kb-engine/kb-engine.db?mode=ro" "SELECT count(*) FROM topics WHERE kind='discovered' AND status='proposed';"
```

- [ ] **Step 4: Commit the vault state (digest refresh) via the vault repo**

```bash
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
git -C "$VAULT" add -A && git -C "$VAULT" commit -m "chore: digest unfrozen after tolerant-sync fix"
```

- [ ] **Step 5: Report phase exit**

Summarize to the user: digest before/after numbers, skipped-file count, launchd agent
status (`launchctl list | grep kb`), and the reminder to rotate the Fastmail token if
not yet done.
