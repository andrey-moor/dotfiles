# KB Hardening Phase 1 — Measure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The safety net before anything changes retrieval — a probe suite +
`kb-engine eval`, local search telemetry, and `/kb:search` wired to hybrid search.

**Architecture:** New `evaluation.py` module (pure metrics + YAML probe loader), an
`events` table in the store, one new CLI command, and a rewrite of the `/kb:search`
command doc. Probes live in the vault (`_system/probes.yaml`, private, git-tracked as of
Phase 0).

**Tech Stack:** Python 3.12, PyYAML (already a transitive dep via python-frontmatter),
click, pytest.

## Global Constraints

See master plan. After this phase, **every subsequent task in the wave must keep
`kb-engine eval` at recall ≥ baseline (1.0, 8/8)**.

---

### Task 1: Probe suite + evaluation module

**Files:**
- Create: `<vault>/_system/probes.yaml`
- Create: `kb-engine/src/kb_engine/evaluation.py`
- Test: `kb-engine/tests/test_evaluation.py`

**Interfaces:**
- Produces (used by Task 2's CLI command):
  - `load_probes(path: Path) -> tuple[Probe, ...]` (raises `ProbeError` on bad file)
  - `Probe(query: str, expect: tuple[str, ...])` — `expect` is any-of vault-relative paths
  - `evaluate(per_probe_ranked: list[list[str]], probes: tuple[Probe, ...], k: int) -> EvalReport`
  - `EvalReport(outcomes: tuple[ProbeOutcome, ...], k: int)` with properties
    `recall: float`, `mrr: float`; `ProbeOutcome(query: str, hit_rank: int | None)`

- [ ] **Step 1: Write the failing tests**

Create `kb-engine/tests/test_evaluation.py`:

```python
import pytest

from kb_engine.evaluation import (
    EvalReport,
    Probe,
    ProbeError,
    ProbeOutcome,
    evaluate,
    load_probes,
    rank_of_first_hit,
)


def test_load_probes_parses_query_and_expect(tmp_path):
    f = tmp_path / "probes.yaml"
    f.write_text(
        '- query: "find x"\n  expect:\n    - "Knowledge/a.md"\n    - "Knowledge/b.md"\n'
    )
    probes = load_probes(f)
    assert probes == (Probe(query="find x", expect=("Knowledge/a.md", "Knowledge/b.md")),)


def test_load_probes_rejects_missing_fields(tmp_path):
    f = tmp_path / "probes.yaml"
    f.write_text('- query: "no expect"\n')
    with pytest.raises(ProbeError):
        load_probes(f)


def test_rank_of_first_hit_is_one_based_and_any_of():
    assert rank_of_first_hit(["x", "b", "a"], expect=("a", "b")) == 2
    assert rank_of_first_hit(["x", "y"], expect=("a",)) is None


def test_evaluate_recall_and_mrr():
    probes = (Probe("q1", ("a",)), Probe("q2", ("b",)), Probe("q3", ("c",)))
    ranked = [["a", "x"], ["x", "b"], ["x", "y"]]  # ranks: 1, 2, miss
    report = evaluate(ranked, probes, k=5)
    assert report.outcomes == (
        ProbeOutcome("q1", 1),
        ProbeOutcome("q2", 2),
        ProbeOutcome("q3", None),
    )
    assert report.recall == pytest.approx(2 / 3)
    assert report.mrr == pytest.approx((1 + 0.5 + 0) / 3)


def test_evaluate_respects_k_cutoff():
    probes = (Probe("q", ("deep",)),)
    report = evaluate([["a", "b", "c", "d", "e", "deep"]], probes, k=5)
    assert report.outcomes[0].hit_rank is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest tests/test_evaluation.py -v`
Expected: FAIL — `ModuleNotFoundError: kb_engine.evaluation`.

- [ ] **Step 3: Implement `evaluation.py`**

Create `kb-engine/src/kb_engine/evaluation.py`:

```python
"""Retrieval evaluation: vault-resident probes, recall@k and MRR metrics."""

from dataclasses import dataclass
from pathlib import Path

import yaml


class ProbeError(ValueError):
    """probes.yaml is missing, malformed, or incomplete."""


@dataclass(frozen=True)
class Probe:
    query: str
    expect: tuple[str, ...]  # any-of vault-relative note paths


@dataclass(frozen=True)
class ProbeOutcome:
    query: str
    hit_rank: int | None  # 1-based rank of the first expected hit; None = miss


@dataclass(frozen=True)
class EvalReport:
    outcomes: tuple[ProbeOutcome, ...]
    k: int

    @property
    def recall(self) -> float:
        if not self.outcomes:
            return 0.0
        hits = sum(1 for o in self.outcomes if o.hit_rank is not None)
        return hits / len(self.outcomes)

    @property
    def mrr(self) -> float:
        if not self.outcomes:
            return 0.0
        total = sum(1 / o.hit_rank for o in self.outcomes if o.hit_rank is not None)
        return total / len(self.outcomes)


def load_probes(path: Path) -> tuple[Probe, ...]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, list) or not data:
        raise ProbeError(f"{path}: expected a non-empty list of probes")
    probes: list[Probe] = []
    for i, item in enumerate(data):
        query = item.get("query") if isinstance(item, dict) else None
        expect = item.get("expect") if isinstance(item, dict) else None
        if not query or not isinstance(expect, list) or not expect:
            raise ProbeError(f"{path}: probe {i} needs 'query' and a non-empty 'expect' list")
        probes.append(Probe(query=str(query), expect=tuple(str(e) for e in expect)))
    return tuple(probes)


def rank_of_first_hit(ranked_paths: list[str], expect: tuple[str, ...]) -> int | None:
    expected = set(expect)
    for rank, path in enumerate(ranked_paths, start=1):
        if path in expected:
            return rank
    return None


def evaluate(
    per_probe_ranked: list[list[str]], probes: tuple[Probe, ...], k: int
) -> EvalReport:
    outcomes = tuple(
        ProbeOutcome(query=p.query, hit_rank=rank_of_first_hit(ranked[:k], p.expect))
        for p, ranked in zip(probes, per_probe_ranked, strict=True)
    )
    return EvalReport(outcomes=outcomes, k=k)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest tests/test_evaluation.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Seed the vault probe file (verified against the live index 2026-07-06)**

Create `<vault>/_system/probes.yaml` with exactly:

```yaml
# Retrieval probes — memory-phrased queries with any-of expected notes.
# Grow this file: every real-world "couldn't find it" becomes a new probe.
- query: "how to give an AI assistant long-term memory"
  expect:
    - "Knowledge/Thread by @karpathy.md"
    - "Knowledge/claude-mem-persistent-memory.md"
    - "Knowledge/effective-context-engineering-for-ai-agents-anthropic.md"
- query: "personal knowledge management second brain zettelkasten"
  expect:
    - "Knowledge/My Claude Code Now Has Its Own Second Brain in Obsidian.md"
    - "Knowledge/karpathy-llm-knowledge-bases.md"
    - "Knowledge/commonplace-folder-obsidian-claude.md"
- query: "what did I save about building a knowledge base with an LLM"
  expect:
    - "Knowledge/karpathy-llm-knowledge-bases.md"
    - "Knowledge/llm-wiki.md"
- query: "token-level embeddings late interaction reranking"
  expect:
    - "Knowledge/colbert-embeddings-vector-search.md"
- query: "agents remembering context across sessions"
  expect:
    - "Knowledge/effective-context-engineering-for-ai-agents-anthropic.md"
    - "Knowledge/claude-mem-persistent-memory.md"
    - "Knowledge/claude-obsidian-memory-stack.md"
- query: "obsidian claude code workflow"
  expect:
    - "Knowledge/claude-obsidian-memory-stack.md"
    - "Knowledge/obsidian-claude-code-run-my-life.md"
    - "Knowledge/obsidian-claude-code-full-course.md"
- query: "waterproof winter boots"
  expect:
    - "Knowledge/bad-weather-boots-kamik-1898-usa-us-kamik-1898-qc-ca.md"
    - "Knowledge/danner-danner-reckoning.md"
- query: "MaxSim operation"
  expect:
    - "Knowledge/colbert-embeddings-vector-search.md"
```

- [ ] **Step 6: Commit**

```bash
cd /Users/andreym/Documents/dotfiles
git add kb-engine/src/kb_engine/evaluation.py kb-engine/tests/test_evaluation.py
git commit -m "feat(kb-engine): evaluation module — probe loader, recall@k, MRR"
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
git -C "$VAULT" add _system/probes.yaml && git -C "$VAULT" commit -m "feat: retrieval probe suite (8 seed probes)"
```

---

### Task 2: `kb-engine eval` CLI command + live baseline

**Files:**
- Modify: `kb-engine/src/kb_engine/cli.py` (new command; mirror the existing `search`
  command's Config/store/embedder setup and teardown exactly — same `pass_obj`, same
  `_build_embedder`, same try/finally store handling)
- Test: `kb-engine/tests/test_cli_eval.py`

**Interfaces:**
- Consumes: Task 1's `load_probes`, `evaluate`; existing `hybrid_search(store, embedder,
  query, limit)`; existing `_build_embedder` / `KB_FAKE_EMBED=1` test hook.
- Produces: `kb-engine eval [--k 5] [--json]` — human line
  `recall@5 1.00 (8/8) · MRR 0.94` + per-probe pass/fail lines; `--json` emits
  `{"k": 5, "recall": 1.0, "mrr": ..., "probes": [{"query": ..., "hit_rank": ...}]}`.
  Exit code 0 always (regression *policy* is enforced by the executor comparing to
  baseline, not by exit code).

- [ ] **Step 1: Write the failing CLI test**

Create `kb-engine/tests/test_cli_eval.py` (mirror the fixture idioms already used in
`tests/test_cli.py` — CliRunner, tmp vault, `KB_FAKE_EMBED=1`):

```python
import json

from click.testing import CliRunner

from kb_engine.cli import cli


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
    sync = runner.invoke(cli, ["--vault", str(vault), "--db", str(db), "sync"])
    assert sync.exit_code == 0, sync.output
    result = runner.invoke(cli, ["--vault", str(vault), "--db", str(db), "eval", "--json"])
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
        cli, ["--vault", str(vault), "--db", str(tmp_path / "kb.db"), "eval"]
    )
    assert result.exit_code != 0
    assert "probes.yaml" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest tests/test_cli_eval.py -v`
Expected: FAIL — `Error: No such command 'eval'`.

- [ ] **Step 3: Implement the command**

Add to `cli.py` (adapt decorator/idiom names to the file's existing pattern — the
`search` command is the template):

```python
@cli.command("eval")
@click.option("--k", default=5, show_default=True, help="Rank cutoff for recall/MRR.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_obj
def eval_cmd(cfg: Config, k: int, as_json: bool) -> None:
    """Run retrieval probes from _system/probes.yaml; report recall@k and MRR."""
    probes_path = cfg.vault_path / "_system" / "probes.yaml"
    if not probes_path.is_file():
        raise click.UsageError(f"no probes file at {probes_path}")
    try:
        probes = load_probes(probes_path)
    except ProbeError as exc:
        raise click.UsageError(str(exc)) from exc
    store = Store(cfg.db_path)
    store.init_schema()
    embedder = _build_embedder(cfg)
    try:
        ranked = [
            [path for path, _score in hybrid_search(store, embedder, p.query, limit=k)]
            for p in probes
        ]
    finally:
        store.close()
    report = evaluate(ranked, probes, k=k)
    if as_json:
        click.echo(json.dumps({
            "k": report.k,
            "recall": report.recall,
            "mrr": report.mrr,
            "probes": [
                {"query": o.query, "hit_rank": o.hit_rank} for o in report.outcomes
            ],
        }))
        return
    hits = sum(1 for o in report.outcomes if o.hit_rank is not None)
    click.echo(f"recall@{report.k} {report.recall:.2f} ({hits}/{len(report.outcomes)}) · MRR {report.mrr:.2f}")
    for o in report.outcomes:
        mark = f"#{o.hit_rank}" if o.hit_rank else "MISS"
        click.echo(f"  [{mark:>4}] {o.query}")
```

(If `Store` has no `close()` in this codebase, use exactly whatever teardown the
existing `search` command uses — do not invent a new one.)

- [ ] **Step 4: Run the full suite**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest`
Expected: new tests PASS; suite green.

- [ ] **Step 5: Record the live baseline (real model, real vault — slow is fine)**

```bash
cd /Users/andreym/Documents/dotfiles/kb-engine
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
uv run kb-engine --vault "$VAULT" eval --json > "$VAULT/_system/eval-baseline.json"
uv run kb-engine --vault "$VAULT" eval
git -C "$VAULT" add _system/eval-baseline.json && git -C "$VAULT" commit -m "chore: eval baseline"
```

Expected: `recall@5 1.00 (8/8)` (verified by hand on 2026-07-06). If any probe misses,
STOP — do not edit probes to pass; report which one and why.

- [ ] **Step 6: Commit**

```bash
cd /Users/andreym/Documents/dotfiles
git add kb-engine/src/kb_engine/cli.py kb-engine/tests/test_cli_eval.py
git commit -m "feat(kb-engine): eval command — recall@k / MRR over vault probes"
```

---

### Task 3: Search telemetry (`events` table)

**Files:**
- Modify: `kb-engine/src/kb_engine/store.py` (schema + one method)
- Modify: `kb-engine/src/kb_engine/cli.py` (search command logs one event)
- Test: `kb-engine/tests/test_events.py`

**Interfaces:**
- Produces: `Store.record_event(kind: str, query: str | None = None, top_path: str |
  None = None, hit_rank: int | None = None) -> None` and
  `Store.count_events(kind: str | None = None) -> int`. Phase 6's resurfacing and the
  digest health line consume this table. Telemetry is cache-local by design (not
  files-as-truth — observability, per master constraints).

- [ ] **Step 1: Write the failing tests**

Create `kb-engine/tests/test_events.py`:

```python
from click.testing import CliRunner

from kb_engine.cli import cli
from kb_engine.store import Store


def test_record_and_count_events(tmp_path):
    store = Store(tmp_path / "kb.db")
    store.init_schema()
    store.record_event("search", query="q", top_path="Knowledge/a.md", hit_rank=1)
    store.record_event("open", top_path="Knowledge/a.md")
    assert store.count_events() == 2
    assert store.count_events(kind="search") == 1


def test_search_command_logs_an_event(tmp_path, monkeypatch):
    k = tmp_path / "Knowledge"
    k.mkdir(parents=True)
    (k / "a.md").write_text("---\ntitle: Alpha\nsummary: alpha\n---\nalpha")
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    runner = CliRunner()
    db = tmp_path / "kb.db"
    assert runner.invoke(cli, ["--vault", str(tmp_path), "--db", str(db), "sync"]).exit_code == 0
    assert runner.invoke(cli, ["--vault", str(tmp_path), "--db", str(db), "search", "alpha"]).exit_code == 0
    store = Store(db)
    store.init_schema()
    assert store.count_events(kind="search") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest tests/test_events.py -v`
Expected: FAIL — `Store` has no attribute `record_event`.

- [ ] **Step 3: Implement**

In `store.py` `init_schema()` add to the schema DDL:

```sql
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    query TEXT,
    top_path TEXT,
    hit_rank INTEGER
)
```

Add methods (match the file's existing transaction idiom, e.g. `with self._conn:`):

```python
def record_event(
    self,
    kind: str,
    query: str | None = None,
    top_path: str | None = None,
    hit_rank: int | None = None,
) -> None:
    with self._conn:
        self._conn.execute(
            "INSERT INTO events (ts, kind, query, top_path, hit_rank) "
            "VALUES (datetime('now'), ?, ?, ?, ?)",
            (kind, query, top_path, hit_rank),
        )

def count_events(self, kind: str | None = None) -> int:
    if kind is None:
        row = self._conn.execute("SELECT count(*) FROM events").fetchone()
    else:
        row = self._conn.execute(
            "SELECT count(*) FROM events WHERE kind = ?", (kind,)
        ).fetchone()
    return int(row[0])
```

In the `search` command in `cli.py`, after results are computed (before printing):

```python
store.record_event(
    "search",
    query=query,
    top_path=hits[0][0] if hits else None,
    hit_rank=1 if hits else None,
)
```

(`hits` = whatever local name the command uses for the ranked result list.)

Also add a tiny command so the kb skill can log note-opens:

```python
@cli.command("log-event")
@click.option("--kind", type=click.Choice(["open", "capture"]), required=True)
@click.option("--path", "note_path", required=True, help="Vault-relative note path.")
@click.pass_obj
def log_event(cfg: Config, kind: str, note_path: str) -> None:
    """Record a local telemetry event (used by the kb skill)."""
    store = Store(cfg.db_path)
    store.init_schema()
    try:
        store.record_event(kind, top_path=note_path)
    finally:
        store.close()  # or the codebase's existing teardown idiom
    click.echo("ok")
```

Extend `test_events.py` with:

```python
def test_log_event_command_records_open(tmp_path):
    runner = CliRunner()
    db = tmp_path / "kb.db"
    (tmp_path / "Knowledge").mkdir(parents=True)
    result = runner.invoke(
        cli,
        ["--vault", str(tmp_path), "--db", str(db), "log-event", "--kind", "open", "--path", "Knowledge/a.md"],
    )
    assert result.exit_code == 0, result.output
    store = Store(db)
    store.init_schema()
    assert store.count_events(kind="open") == 1
```

- [ ] **Step 4: Run the full suite**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest`
Expected: green.

- [ ] **Step 5: Commit**

```bash
cd /Users/andreym/Documents/dotfiles
git add kb-engine/src/kb_engine/store.py kb-engine/src/kb_engine/cli.py kb-engine/tests/test_events.py
git commit -m "feat(kb-engine): local search telemetry (events table)"
```

---

### Task 4: Wire `/kb:search` to the engine + probe-on-miss habit

**Files:**
- Modify: `/kb:search` command doc. Locate the source first:
  `ls /Users/andreym/Documents/dotfiles/chezmoi/private_dot_claude/commands/kb/ 2>/dev/null`
  — if `search.md` is there, edit the chezmoi source then run `just chezmoi-apply`;
  otherwise edit `~/.claude/commands/kb/search.md` directly.
- Modify: `~/.claude/skills/kb/SKILL.md` (same chezmoi-vs-live location rule).

**Interfaces:**
- Consumes: `kb-engine search --json` (existing), `kb-engine eval` probes file (Task 1).
- Produces: the default search verb runs hybrid search; misses become probes.

- [ ] **Step 1: Replace the body of `search.md`**

Keep the existing frontmatter/description block of the file; replace the procedure with:

```markdown
## Procedure

1. Parse the query and optional `--limit N` (default 10).
2. **Tag queries** (`tag:X`): use the Obsidian MCP tag search as before — the engine
   does not index tag filters yet.
3. **Everything else — engine first (hybrid semantic + keyword):**

   ```bash
   kb-engine --vault "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main" search "<query>" --json
   ```

   Take the top `N` hits. For each, read the note's frontmatter (title, source, tags,
   summary, why) via the Obsidian MCP and present: title — one-line summary — tags —
   path. Mark `[wiki]` / `[derived]` notes.
4. **Fallback:** if the engine call fails (missing binary, stale DB), fall back to the
   Obsidian MCP full-text search and say so explicitly in the reply ("engine
   unavailable — keyword-only results").
5. When the user opens or acts on a result, log it (fire-and-forget; ignore errors):
   `kb-engine --vault "<vault>" log-event --kind open --path "<note path>"`
6. **Probe-on-miss:** if the user indicates the thing they wanted was NOT in the
   results ("not it", "couldn't find"), once they locate the right note, append a probe
   to `_system/probes.yaml` (query = their original phrasing, expect = the found path)
   and tell them the suite grew.
7. Offer post-search actions: open, archive, retag (unchanged).
```

- [ ] **Step 2: Update SKILL.md routing**

In the kb SKILL.md search trigger section (trigger 3, "find notes about X"), state that
search runs through the engine's hybrid search per the updated `/kb:search` procedure,
and add the probe-on-miss rule as a one-line instruction. Keep the rest of the skill
unchanged.

- [ ] **Step 3: Apply and verify**

```bash
cd /Users/andreym/Documents/dotfiles
just chezmoi-diff   # if chezmoi-managed: inspect, then
just chezmoi-apply
grep -n "kb-engine" ~/.claude/commands/kb/search.md
```

Expected: the live `~/.claude/commands/kb/search.md` contains the engine invocation
(≥ 1 match).

- [ ] **Step 4: Live smoke test**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run kb-engine --vault "/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main" search "zettelkasten second brain" --json | head -5`
Expected: JSON hits including PKM notes (e.g. `karpathy-llm-knowledge-bases.md`).

- [ ] **Step 5: Commit**

```bash
cd /Users/andreym/Documents/dotfiles
git add -A chezmoi/ 2>/dev/null; git commit -m "feat(kb): /kb:search routes through engine hybrid search + probe-on-miss" || echo "commit in ~/.claude only (not chezmoi-managed) — record in phase notes"
```

---

### Phase exit

- [ ] Full suite green: `cd kb-engine && uv run pytest`
- [ ] Live: `kb-engine eval` = recall@5 1.00 (8/8); baseline JSON committed in vault
- [ ] `/kb:search` demonstrably calls the engine
- [ ] Report to user: baseline numbers + telemetry now accumulating
