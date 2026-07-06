# KB Hardening Phase 2 — Pipeline Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The silent-outage class dies: stat-prefiltered eviction-aware sync, a run
record, a digest that always regenerates with a status header, daily/weekly tiers,
`doctor`, and a dead-man's switch in the kb skill.

**Architecture:** `vault.py` gains a stat-only walk + eviction detection; `sync.py` is
restructured around them (read only what changed); `pipeline.py` wraps steps and always
writes the digest; `store.py` gains `runs`; new `doctor.py`; two Nix launchd agents.

**Tech Stack:** Python 3.12, click, sqlite3, pytest, nix-darwin home-manager launchd.

## Global Constraints

See master plan. Eval gate active: run `kb-engine eval` at phase exit — recall must stay
1.00. Existing tests that assert old `SyncStats`/`PipelineResult` shapes or a
timestamp-free digest are expected casualties: update them as part of the task that
breaks them, never by weakening the new behavior.

---

### Task 1: Run record (`runs` table + `status` surfacing)

**Files:**
- Modify: `kb-engine/src/kb_engine/store.py`
- Modify: `kb-engine/src/kb_engine/cli.py` (`status` command)
- Test: `kb-engine/tests/test_runs.py`

**Interfaces:**
- Produces (consumed by Tasks 3, 5 and Phase 3's backfill):
  - `Store.start_run(command: str, tier: str | None = None) -> int`
  - `Store.finish_run(run_id: int, ok: bool, counts: dict | None = None, errors: list[str] | None = None) -> None`
  - `Store.last_run(command: str | None = None) -> dict | None` — dict keys: `command`,
    `tier`, `started_at`, `finished_at`, `ok` (bool | None), `counts` (dict), `errors`
    (list). Timestamps are UTC ISO-8601 from `datetime('now')`.

- [ ] **Step 1: Write the failing tests**

Create `kb-engine/tests/test_runs.py`:

```python
from kb_engine.store import Store


def test_run_lifecycle_roundtrip(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    run_id = store.start_run("pipeline", tier="daily")
    assert store.last_run()["finished_at"] is None
    store.finish_run(run_id, ok=True, counts={"added": 3}, errors=[])
    last = store.last_run("pipeline")
    assert last["ok"] is True
    assert last["counts"] == {"added": 3}
    assert last["tier"] == "daily"
    assert last["finished_at"] is not None


def test_last_run_returns_none_when_empty(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    assert store.last_run() is None


def test_failed_run_records_errors(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    run_id = store.start_run("pipeline")
    store.finish_run(run_id, ok=False, errors=["sync: OSError: boom"])
    assert store.last_run()["ok"] is False
    assert store.last_run()["errors"] == ["sync: OSError: boom"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest tests/test_runs.py -v`
Expected: FAIL — no `start_run`.

- [ ] **Step 3: Implement**

In `store.py` `init_schema()` add:

```sql
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command TEXT NOT NULL,
    tier TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    ok INTEGER,
    counts TEXT,
    errors TEXT
)
```

Add methods (use the file's `with self._conn:` idiom; `import json` already present or add):

```python
def start_run(self, command: str, tier: str | None = None) -> int:
    with self._conn:
        cur = self._conn.execute(
            "INSERT INTO runs (command, tier, started_at) VALUES (?, ?, datetime('now'))",
            (command, tier),
        )
    return int(cur.lastrowid)

def finish_run(
    self,
    run_id: int,
    ok: bool,
    counts: dict | None = None,
    errors: list[str] | None = None,
) -> None:
    with self._conn:
        self._conn.execute(
            "UPDATE runs SET finished_at = datetime('now'), ok = ?, counts = ?, errors = ? WHERE id = ?",
            (int(ok), json.dumps(counts or {}), json.dumps(errors or []), run_id),
        )

def last_run(self, command: str | None = None) -> dict | None:
    sql = "SELECT command, tier, started_at, finished_at, ok, counts, errors FROM runs"
    params: tuple = ()
    if command is not None:
        sql += " WHERE command = ?"
        params = (command,)
    sql += " ORDER BY id DESC LIMIT 1"
    row = self._conn.execute(sql, params).fetchone()
    if row is None:
        return None
    return {
        "command": row[0],
        "tier": row[1],
        "started_at": row[2],
        "finished_at": row[3],
        "ok": None if row[4] is None else bool(row[4]),
        "counts": json.loads(row[5]) if row[5] else {},
        "errors": json.loads(row[6]) if row[6] else [],
    }
```

In the `status` command, after the existing stats output, add:

```python
last = store.last_run("pipeline")
if last is None:
    click.echo("last pipeline run: never")
else:
    state = "running" if last["finished_at"] is None else ("ok" if last["ok"] else "FAILED")
    click.echo(f"last pipeline run: {last['started_at']}Z ({last['tier'] or '-'}) — {state}")
```

(Extend the `--json` branch of `status` with a `"last_run"` key carrying the dict.)

- [ ] **Step 4: Run the full suite** — `uv run pytest`, green (update any `status`
  golden output in `tests/test_cli.py` if it asserts exact lines).

- [ ] **Step 5: Commit**

```bash
git add kb-engine/src/kb_engine/store.py kb-engine/src/kb_engine/cli.py kb-engine/tests/test_runs.py
git commit -m "feat(kb-engine): run record table + last-run in status"
```

---

### Task 2: Stat-prefiltered, eviction-aware sync

**Files:**
- Modify: `kb-engine/src/kb_engine/vault.py` (add `NoteStat`, `iter_note_stats`,
  `evicted_note_paths`; keep `iter_notes` from Phase 0 — other callers still use it)
- Modify: `kb-engine/src/kb_engine/store.py` (notes gain `mtime REAL`, `size INTEGER`
  via `_ensure_column`; `all_note_stats`, `set_note_stat`)
- Modify: `kb-engine/src/kb_engine/sync.py` (restructured `sync`, extended `SyncStats`)
- Test: `kb-engine/tests/test_sync_prefilter.py`; update `tests/test_sync.py`
  expectations where the new fields change equality assertions

**Interfaces:**
- Produces:
  - `vault.NoteStat(path: str, abs_path: Path, mtime: float, size: int)` (frozen)
  - `vault.iter_note_stats(root, base=None, exclude_dirs=()) -> Iterator[NoteStat]` —
    stat-only, never reads file contents; stat errors skip the file
  - `vault.evicted_note_paths(root, base=None, exclude_dirs=()) -> frozenset[str]` —
    maps `.<name>.md.icloud` placeholders to their vault-relative `.md` paths
  - `Store.all_note_stats() -> dict[str, tuple[str, float | None, int | None]]`
    (path → (sha256, mtime, size)); `Store.set_note_stat(path, mtime, size) -> None`
  - `SyncStats(added, changed, deleted, unchanged=0, evicted=0, failures=())` — old
    3-arg construction still valid (new fields default)
- Behavior contract: unchanged (mtime+size match) ⇒ file is **not read**; stat-changed
  but sha-equal ⇒ no re-embed, stat refreshed; evicted or unreadable ⇒ **never deleted**
  from the DB.

- [ ] **Step 1: Write the failing tests**

Create `kb-engine/tests/test_sync_prefilter.py`:

```python
import os

from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
from kb_engine.store import Store
from kb_engine.sync import sync
from kb_engine.vault import evicted_note_paths


class CountingEmbedder(FakeEmbedder):
    def __init__(self):
        super().__init__()
        self.passage_calls = 0

    def embed_passages(self, texts):
        self.passage_calls += len(texts)
        return super().embed_passages(texts)


def _vault(tmp_path):
    (tmp_path / "Knowledge").mkdir(parents=True)
    return Config(vault_path=tmp_path, db_path=tmp_path / "kb.db")


def _note(cfg, name, text="---\ntitle: t\nsummary: s\n---\nbody"):
    p = cfg.vault_path / "Knowledge" / name
    p.write_text(text)
    return p


def test_unchanged_notes_are_not_reread_or_reembedded(tmp_path):
    cfg = _vault(tmp_path)
    _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    first_calls = emb.passage_calls
    stats = sync(cfg, store, emb)  # nothing touched
    assert emb.passage_calls == first_calls
    assert stats.unchanged == 1 and stats.added == 0 and stats.changed == 0


def test_touched_but_identical_content_does_not_reembed(tmp_path):
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    first_calls = emb.passage_calls
    os.utime(p, (os.path.getatime(p), os.path.getmtime(p) + 10))
    stats = sync(cfg, store, emb)
    assert emb.passage_calls == first_calls  # sha short-circuit
    assert stats.changed == 0


def test_changed_content_reembeds(tmp_path):
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    p.write_text("---\ntitle: t\nsummary: NEW\n---\nnew body")
    stats = sync(cfg, store, emb)
    assert stats.changed == 1


def test_evicted_placeholder_is_not_deleted(tmp_path):
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    p.unlink()
    (cfg.vault_path / "Knowledge" / ".a.md.icloud").write_bytes(b"stub")
    stats = sync(cfg, store, emb)
    assert stats.deleted == 0
    assert stats.evicted == 1
    assert "Knowledge/a.md" in store.all_note_stats()


def test_evicted_note_paths_maps_placeholder_names(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir(parents=True)
    (k / ".some note.md.icloud").write_bytes(b"")
    (k / "other.txt.icloud").write_bytes(b"")  # not a note — ignored
    assert evicted_note_paths(k, base=tmp_path) == frozenset({"Knowledge/some note.md"})


def test_unreadable_existing_note_is_kept_and_reported(tmp_path):
    cfg = _vault(tmp_path)
    p = _note(cfg, "a.md")
    store = Store(cfg.db_path)
    emb = CountingEmbedder()
    sync(cfg, store, emb)
    p.write_text("---\ntitle: t\nsummary: changed\n---\nx")  # force a read attempt
    os.chmod(p, 0o000)
    try:
        stats = sync(cfg, store, emb)
    finally:
        os.chmod(p, 0o644)
    assert stats.deleted == 0
    assert stats.failures == ("a.md",)
    assert "Knowledge/a.md" in store.all_note_stats()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sync_prefilter.py -v`
Expected: FAIL — no `evicted_note_paths`, `SyncStats` lacks fields, etc.

- [ ] **Step 3: Implement `vault.py` additions**

```python
@dataclass(frozen=True)
class NoteStat:
    path: str       # vault-relative posix path
    abs_path: Path
    mtime: float
    size: int


def iter_note_stats(
    root: Path, base: Path | None = None, exclude_dirs: tuple[str, ...] = ()
) -> Iterator[NoteStat]:
    """Stat-only walk — never reads file contents (iCloud-safe)."""
    anchor = root if base is None else base
    for path in sorted(root.rglob("*.md")):
        if not path.is_file():
            continue
        if exclude_dirs and path.relative_to(root).parts[0] in exclude_dirs:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        yield NoteStat(
            path=path.relative_to(anchor).as_posix(),
            abs_path=path,
            mtime=st.st_mtime,
            size=st.st_size,
        )


def evicted_note_paths(
    root: Path, base: Path | None = None, exclude_dirs: tuple[str, ...] = ()
) -> frozenset[str]:
    """Vault-relative .md paths currently evicted by iCloud (.<name>.md.icloud)."""
    anchor = root if base is None else base
    out: set[str] = set()
    for path in root.rglob("*.icloud"):
        name = path.name
        if not (name.startswith(".") and name.endswith(".icloud")):
            continue
        original = name[1 : -len(".icloud")]
        if not original.endswith(".md"):
            continue
        rel_parts = path.relative_to(root).parts
        if exclude_dirs and rel_parts[0] in exclude_dirs:
            continue
        out.add((path.parent / original).relative_to(anchor).as_posix())
    return frozenset(out)
```

Add `from dataclasses import dataclass` to vault.py imports.

- [ ] **Step 4: Implement store additions**

In `init_schema()` alongside the existing `_ensure_column` calls:

```python
self._ensure_column("notes", "mtime", "REAL")
self._ensure_column("notes", "size", "INTEGER")
```

(Match the actual `_ensure_column` signature in the file.) Add methods:

```python
def all_note_stats(self) -> dict[str, tuple[str, float | None, int | None]]:
    rows = self._conn.execute("SELECT path, sha256, mtime, size FROM notes").fetchall()
    return {r[0]: (r[1], r[2], r[3]) for r in rows}

def set_note_stat(self, path: str, mtime: float, size: int) -> None:
    with self._conn:
        self._conn.execute(
            "UPDATE notes SET mtime = ?, size = ? WHERE path = ?", (mtime, size, path)
        )
```

- [ ] **Step 5: Restructure `sync()`**

Replace `_disk_notes` usage with the stat-based flow (keep `_index_note`, `_url_msgid`
as-is; `read_note` imported from `kb_engine.vault`):

```python
@dataclass(frozen=True)
class SyncStats:
    added: int
    changed: int
    deleted: int
    unchanged: int = 0
    evicted: int = 0
    failures: tuple[str, ...] = ()


def sync(cfg: Config, store: Store, embedder: Embedder) -> SyncStats:
    """Incremental files-as-truth sync: stat-prefiltered, eviction-aware, tolerant."""
    store.init_schema()
    knowledge_dir = cfg.knowledge_dir
    if not knowledge_dir.is_dir():
        return SyncStats(added=0, changed=0, deleted=0)

    disk = {
        s.path: s
        for s in iter_note_stats(knowledge_dir, base=cfg.vault_path, exclude_dirs=EXCLUDED_DIRS)
    }
    evicted = evicted_note_paths(knowledge_dir, base=cfg.vault_path, exclude_dirs=EXCLUDED_DIRS)
    db_stats = store.all_note_stats()

    added = changed = unchanged = 0
    failures: list[str] = []
    for path, stat in disk.items():
        known = db_stats.get(path)
        if known is not None and known[1] == stat.mtime and known[2] == stat.size:
            unchanged += 1
            continue  # not even read — the iCloud-safety win
        try:
            note = read_note(stat.abs_path, base=cfg.vault_path)
        except OSError as exc:
            logger.warning("skipping unreadable note %s: %s", stat.abs_path, exc)
            failures.append(stat.abs_path.name)
            continue
        if known is None:
            _index_note(store, note, embedder)
            added += 1
        elif known[0] != note.sha256:
            _index_note(store, note, embedder)
            changed += 1
        else:
            unchanged += 1
        store.set_note_stat(path, stat.mtime, stat.size)

    deleted = 0
    for path in db_stats:
        if path not in disk and path not in evicted:
            store.delete_note(path)
            deleted += 1

    return SyncStats(
        added=added,
        changed=changed,
        deleted=deleted,
        unchanged=unchanged,
        evicted=len(evicted & set(db_stats)),
        failures=tuple(failures),
    )
```

Note the deliberate behavior change: unchanged notes no longer get per-run
`set_note_metadata` writes (url/message_id can't change without the sha changing — the
old refresh was a one-time backfill). If `tests/test_sync.py` has a backfill test
relying on it, keep `set_note_metadata` only for the path where the stat changed but the
sha matched.

- [ ] **Step 6: Run the full suite; update stale expectations**

Run: `uv run pytest`
Expected: new tests PASS; fix any `test_sync.py` / `test_cli.py` assertions that
compare full `SyncStats` equality (add the new fields) — never delete the assertions.

- [ ] **Step 7: Commit**

```bash
git add kb-engine/src/kb_engine/vault.py kb-engine/src/kb_engine/store.py kb-engine/src/kb_engine/sync.py kb-engine/tests/
git commit -m "feat(kb-engine): stat-prefiltered, eviction-aware, tolerant sync"
```

---

### Task 3: Pipeline step-wrapping, always-written digest, tiers

**Files:**
- Modify: `kb-engine/src/kb_engine/pipeline.py`
- Modify: `kb-engine/src/kb_engine/importing/digest.py` (status header)
- Modify: `kb-engine/src/kb_engine/cli.py` (`pipeline --tier`, print outcomes)
- Test: `kb-engine/tests/test_pipeline_hardening.py`; update `tests/test_pipeline.py`
  and `tests/test_digest.py` for the new shapes/header

**Interfaces:**
- Produces:
  - `StepOutcome(name: str, ok: bool, detail: str)` (frozen)
  - `PipelineResult(tier: str, ok: bool, outcomes: tuple[StepOutcome, ...], digest_path: Path | None)`
    — **replaces** the old field set; CLI output updated accordingly
  - `run_pipeline(cfg, store, embedder, clusterer, tier: str = "weekly") -> PipelineResult`
  - `build_digest(..., status: DigestStatus | None = None)` where
    `DigestStatus(started_at: str, tier: str, ok: bool, outcomes: tuple[StepOutcome, ...])`
    renders a leading `## Status` section
- Behavior contract: **the digest is written even when steps fail** (in `finally`); a
  run row is always recorded; step order: daily = sync → import-mail → digest; weekly =
  sync → import-mail → apply-topics → discover → eval → digest. import-mail skips with a
  report line when `FASTMAIL_API_TOKEN` is unset (reuse the CLI command's existing
  label/default parameters). eval skips with a report line when
  `_system/probes.yaml` is absent.

- [ ] **Step 1: Write the failing tests**

Create `kb-engine/tests/test_pipeline_hardening.py`:

```python
import kb_engine.pipeline as pipeline_mod
from kb_engine.topics.clustering import FakeClusterer  # returns the label array it is given
from kb_engine.config import Config
from kb_engine.embeddings import FakeEmbedder
from kb_engine.pipeline import run_pipeline
from kb_engine.store import Store


def _cfg(tmp_path):
    (tmp_path / "Knowledge").mkdir(parents=True)
    (tmp_path / "_system").mkdir()
    return Config(vault_path=tmp_path, db_path=tmp_path / "kb.db")


def test_failed_sync_still_writes_digest_with_failed_status(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path)

    def boom(*a, **k):
        raise OSError("EDEADLK simulated")

    monkeypatch.setattr(pipeline_mod, "sync", boom)
    result = run_pipeline(cfg, store, FakeEmbedder(), FakeClusterer([]), tier="daily")
    assert result.ok is False
    digest = (tmp_path / "_system" / "kb-digest.md").read_text()
    assert "FAILED" in digest and "sync" in digest
    assert store.last_run("pipeline")["ok"] is False


def test_daily_tier_skips_topic_steps(tmp_path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path)
    result = run_pipeline(cfg, store, FakeEmbedder(), FakeClusterer([]), tier="daily")
    names = [o.name for o in result.outcomes]
    assert "sync" in names and "apply-topics" not in names and "discover" not in names


def test_weekly_tier_runs_topic_steps_and_records_run(tmp_path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path)
    result = run_pipeline(cfg, store, FakeEmbedder(), FakeClusterer([]), tier="weekly")
    names = [o.name for o in result.outcomes]
    assert ["sync", "import-mail", "apply-topics", "discover", "eval"] == names
    assert store.last_run("pipeline")["tier"] == "weekly"
    digest = (tmp_path / "_system" / "kb-digest.md").read_text()
    assert digest.startswith("# KB Digest")
    assert "## Status" in digest and "Last run:" in digest
```

(`FakeClusterer` lives in `kb_engine/topics/clustering.py` and returns the label array
passed to its constructor verbatim — an empty list is fine for these tests, which never
reach clustering.)

- [ ] **Step 2: Run tests to verify they fail** — `uv run pytest tests/test_pipeline_hardening.py -v`

- [ ] **Step 3: Implement `pipeline.py`**

```python
"""Deterministic maintenance pipeline: tiered steps, tolerant, digest-always."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from kb_engine.config import Config
from kb_engine.embeddings import Embedder
from kb_engine.importing.digest import DigestStatus, write_digest
from kb_engine.store import Store
from kb_engine.sync import sync
# keep the module's existing imports for apply_topic_tags / sticky_discover / mail import


@dataclass(frozen=True)
class StepOutcome:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PipelineResult:
    tier: str
    ok: bool
    outcomes: tuple[StepOutcome, ...]
    digest_path: Path | None


def _run_step(name: str, fn: Callable[[], str], outcomes: list[StepOutcome]) -> None:
    try:
        outcomes.append(StepOutcome(name, True, fn()))
    except Exception as exc:  # noqa: BLE001 — one step must never kill the run
        outcomes.append(StepOutcome(name, False, f"{type(exc).__name__}: {exc}"))


def run_pipeline(
    cfg: Config,
    store: Store,
    embedder: Embedder,
    clusterer,
    tier: str = "weekly",
) -> PipelineResult:
    store.init_schema()
    run_id = store.start_run("pipeline", tier=tier)
    outcomes: list[StepOutcome] = []

    _run_step("sync", lambda: _sync_step(cfg, store, embedder), outcomes)
    _run_step("import-mail", lambda: _import_mail_step(cfg, store), outcomes)
    if tier == "weekly":
        _run_step("apply-topics", lambda: _apply_step(cfg, store), outcomes)
        _run_step("discover", lambda: _discover_step(cfg, store, clusterer), outcomes)
        _run_step("eval", lambda: _eval_step(cfg, store, embedder), outcomes)

    ok = all(o.ok for o in outcomes)
    digest_path: Path | None = None
    try:
        status = DigestStatus(tier=tier, ok=ok, outcomes=tuple(outcomes))
        digest_path = write_digest(cfg, store, status=status)
    finally:
        store.finish_run(
            run_id,
            ok=ok and digest_path is not None,
            counts={o.name: o.detail for o in outcomes},
            errors=[f"{o.name}: {o.detail}" for o in outcomes if not o.ok],
        )
    return PipelineResult(tier=tier, ok=ok, outcomes=tuple(outcomes), digest_path=digest_path)
```

Step helpers (each returns a one-line human detail string):

```python
def _sync_step(cfg: Config, store: Store, embedder: Embedder) -> str:
    s = sync(cfg, store, embedder)
    return (
        f"{s.added} added · {s.changed} changed · {s.deleted} deleted · "
        f"{s.unchanged} unchanged · {s.evicted} evicted · {len(s.failures)} unreadable"
    )


def _import_mail_step(cfg: Config, store: Store) -> str:
    import os

    token = os.environ.get("FASTMAIL_API_TOKEN")
    if not token:
        return "skipped: no FASTMAIL_API_TOKEN"
    # call the same function the import-mail CLI command calls, with its defaults
    written = _import_mail(cfg, store, token)  # thin wrapper extracted from cli.py
    return f"{written} newsletter note(s) written"


def _eval_step(cfg: Config, store: Store, embedder: Embedder) -> str:
    from kb_engine.evaluation import evaluate, load_probes
    from kb_engine.search import hybrid_search

    probes_path = cfg.vault_path / "_system" / "probes.yaml"
    if not probes_path.is_file():
        return "skipped: no probes.yaml"
    probes = load_probes(probes_path)
    ranked = [
        [p for p, _ in hybrid_search(store, embedder, probe.query, limit=5)]
        for probe in probes
    ]
    report = evaluate(ranked, probes, k=5)
    hits = sum(1 for o in report.outcomes if o.hit_rank is not None)
    return f"recall@5 {report.recall:.2f} ({hits}/{len(report.outcomes)}) · MRR {report.mrr:.2f}"
```

`_apply_step` / `_discover_step` wrap the module's existing apply/sticky-discover calls
unchanged, returning their current count summaries as the detail string. Extract the
mail-import body from the CLI command into an importable helper so both CLI and pipeline
call one function (DRY) — keep the CLI command's flags as the single source of defaults.

- [ ] **Step 4: Implement the digest status header**

In `importing/digest.py` add:

```python
@dataclass(frozen=True)
class DigestStatus:
    tier: str
    ok: bool
    outcomes: tuple  # tuple[StepOutcome, ...] — typed loosely to avoid an import cycle
```

`build_digest(...)` gains `status: DigestStatus | None = None`; when given, the digest
starts with:

```markdown
# KB Digest

## Status

- Last run: {utc-now ISO, minutes precision}Z · tier: {tier} · {"✅ ok" if ok else "⚠️ FAILED"}
{one line per outcome: "- {name}: {detail}"}
```

Compute the timestamp with `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")` at
render time. `write_digest(cfg, store, status=None)` is the file-writing wrapper the
pipeline calls (create it here if `build_digest` currently only returns text — it writes
to `cfg.vault_path / "_system" / "kb-digest.md"` and returns the path). Update
`tests/test_digest.py`: the "no timestamps" idempotency assertion now applies to the
body *below* the Status section (split on `"## Summary"` and compare that part).

- [ ] **Step 5: CLI `--tier`**

The `pipeline` command gains `@click.option("--tier", type=click.Choice(["daily", "weekly"]), default="weekly", show_default=True)`
and passes it through; human output prints one line per `StepOutcome` (`✅/⚠️ name — detail`).
Update `tests/test_pipeline.py` / `tests/test_cli.py` for the new `PipelineResult` shape.

- [ ] **Step 6: Run the full suite** — `uv run pytest`, green.

- [ ] **Step 7: Commit**

```bash
git add kb-engine/src/kb_engine/pipeline.py kb-engine/src/kb_engine/importing/digest.py kb-engine/src/kb_engine/cli.py kb-engine/tests/
git commit -m "feat(kb-engine): tolerant tiered pipeline with always-written status digest"
```

---

### Task 4: Two launchd tiers (Nix)

**Files:**
- Modify: the kb-engine nix module (located in Phase 0 Task 1 Step 3)

**Interfaces:**
- Produces: launchd agents `kb-engine-pipeline-daily` (08:00, `pipeline --tier daily`)
  and `kb-engine-pipeline-weekly` (Mon 09:00, `pipeline --tier weekly`), replacing the
  single weekly agent. Both keep stdout/stderr logs under `~/Library/Logs/`.

- [ ] **Step 1: Edit the module** — duplicate the existing agent definition into the
  two tiers above, appending the `--tier` argument to the wrapped command; rename log
  files to `kb-engine-pipeline-daily.{log,err}` / `-weekly.{log,err}`; remove the old
  agent attribute.

- [ ] **Step 2: Apply and verify**

```bash
cd /Users/andreym/Documents/dotfiles && just switch
launchctl list | grep kb-engine
```

Expected: both agents listed; the old `org.nix-community.home.kb-engine-pipeline` gone
(home-manager unloads it on switch — if it lingers, `launchctl bootout gui/$(id -u)/org.nix-community.home.kb-engine-pipeline`).

- [ ] **Step 3: Kick the daily tier once by hand**

Run: `launchctl kickstart -k gui/$(id -u)/org.nix-community.home.kb-engine-pipeline-daily`
Then: `sleep 120 && tail -3 ~/Library/Logs/kb-engine-pipeline-daily.log && launchctl list | grep kb-engine`
Expected: log shows step lines; last-exit 0; digest Status header updated (check the
vault file).

- [ ] **Step 4: Commit**

```bash
git add modules/ && git commit -m "feat(kb): daily + weekly pipeline launchd tiers"
```

---

### Task 5: `kb-engine doctor`

**Files:**
- Create: `kb-engine/src/kb_engine/doctor.py`
- Modify: `kb-engine/src/kb_engine/cli.py` (new command)
- Test: `kb-engine/tests/test_doctor.py`

**Interfaces:**
- Produces: `run_checks(cfg: Config, now: float | None = None) -> tuple[Check, ...]`
  with `Check(name: str, ok: bool, severity: str, detail: str)` (severity `"hard"` |
  `"warn"`); CLI `doctor [--json]` exits 1 iff any hard check fails. Checks:
  `vault` (dir exists — hard), `db` (file exists + `PRAGMA integrity_check` == ok —
  hard), `digest-fresh` (exists, mtime ≤ 8 days, Status section not FAILED — hard),
  `secrets` (`~/.config/kb-engine/secrets.env` exists with 0600 — warn until Phase 3
  flips it), `launchd` (both agents in `launchctl list` output — warn),
  `vault-git` (HEAD commit ≤ 48 h old — warn), `model-cache` (HF cache dir contains a
  `jina` snapshot — warn).

- [ ] **Step 1: Write the failing tests** (pure checks only; subprocess-backed checks
  take their raw input as a parameter so tests stay hermetic)

Create `kb-engine/tests/test_doctor.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_doctor.py -v`

- [ ] **Step 3: Implement `doctor.py`**

```python
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
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
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
```

CLI command: prints `✅/⚠️/❌ name — detail` per check (❌ = failed hard), `--json` dumps
the tuple as dicts, exit code `1` iff any failed hard check.

- [ ] **Step 4: Full suite + live doctor run**

```bash
uv run pytest
uv run kb-engine --vault "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main" doctor
```

Expected: tests green; live output shows hard checks ✅ (secrets still warn — Phase 3).

- [ ] **Step 5: Commit**

```bash
git add kb-engine/src/kb_engine/doctor.py kb-engine/src/kb_engine/cli.py kb-engine/tests/test_doctor.py
git commit -m "feat(kb-engine): doctor health checks"
```

---

### Task 6: Skill preflight + phase exit

**Files:**
- Modify: kb `SKILL.md` (chezmoi source if managed there, else `~/.claude/skills/kb/SKILL.md`)

- [ ] **Step 1: Add the preflight section to SKILL.md** (near the top, after the intro):

```markdown
## Preflight (every /kb:* invocation)

Before any KB operation, check the digest status file:
`_system/kb-digest.md` in the vault. If its `## Status` section says FAILED, or the
file is older than 8 days (stat its mtime), STOP and tell the user first:
"⚠️ The KB pipeline last ran <when> with status <status> — run `kb-engine doctor` /
check `~/Library/Logs/kb-engine-pipeline-*.err` before trusting results."
Then proceed with the requested operation, flagging that results may be stale.
```

- [ ] **Step 2: Apply (chezmoi) and verify** — as in Phase 1 Task 4 Step 3.

- [ ] **Step 3: Phase exit checklist**

```bash
cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
uv run kb-engine --vault "$VAULT" eval          # expect recall@5 1.00 (8/8)
uv run kb-engine --vault "$VAULT" doctor        # hard checks green
head -12 "$VAULT/_system/kb-digest.md"          # Status header present
```

- [ ] **Step 4: Report to user** — include the reminder from the master checklist:
  disable "Optimize Mac Storage" (System Settings → Apple ID → iCloud → Drive).

- [ ] **Step 5: Commit any remaining changes; vault commit for digest/status artifacts**
