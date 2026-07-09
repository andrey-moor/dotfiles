# KB Hardening Phase 4 — Topic Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the topic layer trustworthy — near-dup sweep + search suppression,
member-centroid re-anchoring, per-topic thresholds derived from live geometry, real
primary/secondary assignment with a persisted borderline `review_queue`, all tested
against real jina-v3 vectors.

**Architecture:** Evolves `kb-engine/` in place. New modules `dedup.py`,
`topics/anchoring.py`, `topics/thresholds.py`, `topics/weekly.py`; `topics/sticky.py`
retires. Three new `topics` table columns + one new `review_queue` table (migrated via
the existing `_ensure_column` / `CREATE TABLE IF NOT EXISTS` pattern — the cache stays
disposable). The weekly pipeline tier reorders to: sync → **topics pass** →
apply-topics → eval.

**Tech Stack:** Python 3.12, click, sqlite3, numpy, pytest, uv; python-frontmatter via
`vault.load_post`/`write_post_atomic` house I/O; launchd via nix (one small nudge-parse
edit).

## Global Constraints

Every task implicitly includes these (from the spec / master plan):

- **Eval gate:** `kb-engine eval` recall@5 must not regress at any task or phase
  boundary. Baseline: 8/8 probes (recall@5 1.00; reference MRR 0.67 post-backfill).
- **TDD:** every code task is test-first; suite green before each commit
  (`cd kb-engine && uv run pytest`). Current suite: 394 tests green.
- **No LLM/API calls in unit tests:** use `FakeEmbedder`, `FakeClusterer`, `FakeLLM`;
  real-model checks stay behind `KB_RUN_INTEGRATION=1`.
- **Engine works without secrets:** absent keys ⇒ steps skip with a report line.
- **Files-as-truth:** vault artifacts regenerable; SQLite cache disposable (telemetry
  `events`/`runs`/`review_queue` are observability/workflow state, not knowledge —
  a queue rebuild costs one weekly run).
- **Nothing lost:** no capture/note deleted by automation; merges archive with
  `duplicate_of:`; unfiled remains reachable. `apply` only ever ADDS tags.
- **Vault writers use the house I/O:** `vault.load_post(text)` + 
  `vault.write_post_atomic(path, post)` — `frontmatter.load/loads` crashes on notes
  with a `content:` frontmatter key (91 topic members have `content: unavailable`).
- **Frozen dataclasses / immutability**; functions ≤ 50 lines. Files ≤ 800 lines —
  known exception: `cli.py` is already 1,306 lines; the master plan schedules its
  split in Phase 6 (T6.4), and this phase's new commands follow the existing
  one-file CLI pattern until then.
- **Vault path:** `/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main`
  (always quote — contains spaces). **DB:** `~/.local/state/kb-engine/kb-engine.db`.
  Ad-hoc DB inspection: `sqlite3 "file:...?immutable=1"` (WAL breaks `mode=ro`).
- **Commit per task**, conventional commits, no attribution footer.
- **Doc twins:** command docs exist twice — live `~/.claude/commands/kb/*.md` and
  chezmoi source `chezmoi/private_dot_claude/commands/kb/*.md`. Edit both; they must
  end byte-identical (verify with `diff`).

## Plan-time live data (2026-07-09, post-Phase-3 re-embed; 597 notes)

Gathered read-only from the production DB — the numbers the spec said to derive at
plan time:

- **Geometry:** 597 notes = 597 chunks (exactly one vector per note, all unit-norm).
  Note-level "mean-pooled" vectors are therefore the raw unit chunk vectors.
- **Topics:** 24 `manual/active` (all with 6–43 members), 36 `discovered/proposed`.
  All 967 `topic_members` rows are `source='auto', is_primary=1`.
- **Near-dups (note-vector cosine):** 48 pairs ≥ 0.95, **36 pairs ≥ 0.97**, 9 ≥ 0.99.
  Nearly all are literal re-clips (same tweet captured twice, `-2` filename suffix).
- **Per-topic member-sim p25** (vs current label anchors): 0.399 (saas-startups) …
  0.715 (obsidian-claude). The spec formula `high = max(0.45, p25)`,
  `secondary = high − 0.08` produces sane per-topic values on live geometry — the
  0.45 floor binds for 4 loose topics; no formula tuning needed.
- **Re-anchoring preview:** all 24 manual topics have ≥ 3 members;
  cos(label-anchor, member-mean-anchor) ranges 0.928–0.998; re-anchored p25 rises for
  most topics (e.g. career-ai 0.616→0.738).
- **Coverage preview:** nearest-active-topic score ≥ 0.45 for 387 notes, ≥ 0.55
  (today's global sticky bar) for 243. Per-topic thresholds will grow coverage.
- **Live bug found while planning:** `topics/apply.py` still reads notes with
  `frontmatter.load(path)` → `TypeError: Post.__init__() got multiple values for
  argument 'content'` on any note carrying `content: unavailable` (91 of 507 current
  members). The weekly `apply-topics` step fails on first contact. Task 1 fixes this
  before anything else touches the topic layer.

## File structure

| File | Change |
|---|---|
| `kb-engine/src/kb_engine/topics/apply.py` | fix: house I/O (`load_post`/`write_post_atomic`) |
| `kb-engine/scripts/generate_real_vectors.py` | new: one-time fixture generator (reads live DB) |
| `kb-engine/tests/fixtures/real_vectors.npy` + `.json` | new: committed real-vector fixtures |
| `kb-engine/tests/conftest.py` | new content: `real_vectors` fixture loader |
| `kb-engine/src/kb_engine/dedup.py` | new: `near_duplicates` report |
| `kb-engine/src/kb_engine/search.py` | modify: near-dup suppression in `hybrid_search` |
| `kb-engine/src/kb_engine/store.py` | modify: `note_vectors_for`, anchor/threshold columns + setters, `review_queue` table + methods, `replace_auto_members`, `user_primary_paths`, `clear_auto_primaries` |
| `kb-engine/src/kb_engine/models.py` | modify: `Topic` gains `anchor_source`, `threshold_high`, `threshold_secondary`; new `QueueEntry` |
| `kb-engine/src/kb_engine/topics/anchoring.py` | new: member-centroid re-anchoring |
| `kb-engine/src/kb_engine/topics/thresholds.py` | new: per-topic threshold derivation |
| `kb-engine/src/kb_engine/topics/assignment.py` | modify: per-topic thresholds, multi-candidate borderline; owns `DEFAULT_ASSIGN_*` constants |
| `kb-engine/src/kb_engine/topics/weekly.py` | new: weekly topic pass orchestration |
| `kb-engine/src/kb_engine/topics/sticky.py` | **delete** (with `tests/test_sticky.py`) |
| `kb-engine/src/kb_engine/pipeline.py` | modify: weekly tier rewire |
| `kb-engine/src/kb_engine/importing/digest.py` | modify: borderline-queue section |
| `kb-engine/src/kb_engine/cli.py` | modify: `dedup-report`, `topics reanchor`, `topics thresholds`, `topics confirm`; `assign` per-topic; drop `discover --sticky` |
| `modules/home/dev/kb-engine.nix` | modify: nudge count includes `queue` |
| `~/.claude/commands/kb/review.md` (+ chezmoi twin) | modify: merge flow + queue workflow |

Task order note: fixtures (Task 2) precede all geometry-sensitive tests; Task 1 is
first because it fixes a live crasher in the module this whole phase builds on.

---

### Task 1: `apply.py` house-I/O fix (live crasher)

**Files:**
- Modify: `kb-engine/src/kb_engine/topics/apply.py`
- Test: `kb-engine/tests/test_apply.py`

**Interfaces:**
- Consumes: `vault.load_post(text: str) -> frontmatter.Post`,
  `vault.write_post_atomic(path: Path, post: frontmatter.Post) -> None` (existing).
- Produces: `apply_topic_tags` behavior unchanged, but tolerant of `content:`
  frontmatter, atomic, and key-order-preserving.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_apply.py`, matching
  its existing fixtures/style — read the file first):

```python
def test_apply_tolerates_content_frontmatter_key(tmp_path):
    """A member note carrying backfill's `content: unavailable` must still get
    tagged — frontmatter.load() crashes on that key; the house load_post doesn't."""
    note = tmp_path / "Knowledge" / "stub.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntitle: Stub\ncontent: unavailable\ntags: [old]\n---\nbody\n"
    )
    changed, added = _apply_to_note(note, ["mytopic"], None)
    assert (changed, added) == (True, 1)
    text = note.read_text()
    assert "topic/mytopic" in text
    assert "content: unavailable" in text


def test_apply_preserves_frontmatter_key_order(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("---\nzeta: 1\nalpha: 2\ntags: [x]\n---\nbody\n")
    _apply_to_note(note, ["t"], "t")
    text = note.read_text()
    assert text.index("zeta") < text.index("alpha"), "dumps must not sort keys"


def test_apply_leaves_no_tmp_file(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("---\ntitle: N\n---\nbody\n")
    _apply_to_note(note, ["t"], None)
    assert list(tmp_path.glob("*.tmp")) == []
```

(Import `_apply_to_note` at the top of the test file:
`from kb_engine.topics.apply import _apply_to_note` — the module-level helper is the
unit under test; `apply_topic_tags` integration coverage already exists.)

- [ ] **Step 2: Run to verify failure**

Run: `cd kb-engine && uv run pytest tests/test_apply.py -v`
Expected: `test_apply_tolerates_content_frontmatter_key` FAILS with
`TypeError: Post.__init__() got multiple values for argument 'content'`;
the key-order test fails on sorted output.

- [ ] **Step 3: Fix `_apply_to_note`** — replace the read and write lines only:

```python
from kb_engine.vault import load_post, write_post_atomic
```

and in `_apply_to_note`, replace `post = frontmatter.load(note_path)` with:

```python
    post = load_post(note_path.read_text())
```

and replace `note_path.write_text(frontmatter.dumps(post) + "\n")` with:

```python
    write_post_atomic(note_path, post)
```

Drop the now-unused `import frontmatter` from apply.py.
(Note: `write_post_atomic` does not append a trailing newline the old code added;
`frontmatter.dumps` output ends without one. No test pins the trailing newline and
Obsidian doesn't care — do not add a compensating `+ "\n"` hack.)

- [ ] **Step 4: Run the full suite**

Run: `cd kb-engine && uv run pytest`
Expected: all green (394 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add kb-engine/src/kb_engine/topics/apply.py kb-engine/tests/test_apply.py
git commit -m "fix(kb-engine): apply tolerates content: frontmatter; atomic ordered writes"
```

---

### Task 2: Real-vector fixtures

**Files:**
- Create: `kb-engine/scripts/generate_real_vectors.py`
- Create: `kb-engine/tests/fixtures/real_vectors.npy`, `kb-engine/tests/fixtures/real_vectors.json` (generated, committed)
- Modify: `kb-engine/tests/conftest.py` (currently empty)
- Test: `kb-engine/tests/test_real_vector_fixtures.py`

**Interfaces:**
- Produces: pytest fixture `real_vectors` → `RealVectors` with
  `.matrix: np.ndarray (N,1024 float32)`, `.entries: list[dict]`
  (each `{"path": str, "group": str, "text": str}`, index-aligned with `matrix`),
  and helper `.by_group(prefix: str) -> list[tuple[str, np.ndarray]]`
  returning `(path, vector)` pairs whose group starts with `prefix`.
  Groups: `topic:<slug>` (2 top members from each of the 24 manual topics),
  `neardup:<i>` (both sides of the 5 most-similar pairs, i = 0..4),
  `unfiled` (4 notes in no topic).
- Later tasks (3–8) consume this fixture for all geometry-sensitive tests.

**Design note (recorded deviation):** the skeleton says "script embeds ~50 real
notes' texts"; this plan **copies the stored vectors** from the live DB instead.
They ARE jina-v3 embeddings of exactly those texts (task-typed, unit-norm), so this
is strictly more faithful (no model-version drift between fixture and production)
and the generator needs no torch. The texts are still recorded in the JSON so the
fixture can be re-embedded later if ever needed.

- [ ] **Step 1: Write the generator** — `kb-engine/scripts/generate_real_vectors.py`
  (create the `scripts/` directory):

```python
"""One-time generator: copy ~58 real note vectors from the live DB into
tests/fixtures/real_vectors.{npy,json}.

Run from kb-engine/:  uv run python scripts/generate_real_vectors.py
Requires the live populated DB (post-Phase-3 re-embed). Deterministic given
the DB state. Re-run only deliberately — tests key off group labels, not paths.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np

DB = Path.home() / ".local" / "state" / "kb-engine" / "kb-engine.db"
OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
MEMBERS_PER_TOPIC = 2
NEARDUP_PAIRS = 5
UNFILED_COUNT = 4


def main() -> None:
    conn = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    vec: dict[str, np.ndarray] = {}
    text: dict[str, str] = {}
    for path, t, blob in conn.execute("SELECT note_path, text, vector FROM chunks"):
        vec[path] = np.frombuffer(blob, np.float32)
        text[path] = t

    selected: dict[str, str] = {}  # path -> group (first assignment wins)

    manual = [r[0] for r in conn.execute(
        "SELECT slug FROM topics WHERE kind='manual' AND status='active' ORDER BY slug"
    )]
    for slug in manual:
        rows = conn.execute(
            "SELECT note_path FROM topic_members WHERE topic_slug=? "
            "ORDER BY score DESC, note_path LIMIT ?",
            (slug, MEMBERS_PER_TOPIC + 2),
        ).fetchall()
        picked = 0
        for (p,) in rows:
            if picked >= MEMBERS_PER_TOPIC:
                break
            if p in vec and p not in selected:
                selected[p] = f"topic:{slug}"
                picked += 1

    paths = sorted(vec)
    mat = np.vstack([vec[p] for p in paths])
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    sim = (mat / norms) @ (mat / norms).T
    iu = np.triu_indices(len(paths), k=1)
    order = np.argsort(sim[iu])[::-1]
    pair_i = 0
    for idx in order:
        if pair_i >= NEARDUP_PAIRS:
            break
        a, b = paths[iu[0][idx]], paths[iu[1][idx]]
        if a in selected or b in selected:
            continue
        selected[a] = f"neardup:{pair_i}"
        selected[b] = f"neardup:{pair_i}"
        pair_i += 1

    in_topic = {r[0] for r in conn.execute("SELECT DISTINCT note_path FROM topic_members")}
    unfiled = 0
    for p in paths:
        if unfiled >= UNFILED_COUNT:
            break
        if p not in in_topic and p not in selected:
            selected[p] = "unfiled"
            unfiled += 1
    conn.close()

    ordered = sorted(selected)
    matrix = np.vstack([vec[p] for p in ordered]).astype(np.float32)
    entries = [{"path": p, "group": selected[p], "text": text[p]} for p in ordered]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUT_DIR / "real_vectors.npy", matrix)
    (OUT_DIR / "real_vectors.json").write_text(json.dumps(entries, indent=1))
    print(f"wrote {len(ordered)} vectors: "
          f"{sum(1 for g in selected.values() if g.startswith('topic:'))} topic members, "
          f"{2 * pair_i} near-dup, {unfiled} unfiled")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generator** (this machine has the live DB):

Run: `cd kb-engine && uv run python scripts/generate_real_vectors.py`
Expected: `wrote ~58 vectors: 48 topic members, 10 near-dup, 4 unfiled`
(exact count may vary slightly if a top member lacks a vector; ≥ 52 total).

- [ ] **Step 3: Write the conftest fixture** — `kb-engine/tests/conftest.py`:

```python
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class RealVectors:
    """~58 real jina-v3 note vectors copied from the live KB (see scripts/
    generate_real_vectors.py). Tests select by GROUP label, never by path."""

    matrix: np.ndarray
    entries: tuple

    def by_group(self, prefix: str) -> list[tuple[str, np.ndarray]]:
        return [
            (e["path"], self.matrix[i])
            for i, e in enumerate(self.entries)
            if e["group"].startswith(prefix)
        ]


@pytest.fixture(scope="session")
def real_vectors() -> RealVectors:
    matrix = np.load(_FIXTURE_DIR / "real_vectors.npy")
    entries = json.loads((_FIXTURE_DIR / "real_vectors.json").read_text())
    return RealVectors(matrix=matrix, entries=tuple(entries))
```

- [ ] **Step 4: Write the sanity tests** — `kb-engine/tests/test_real_vector_fixtures.py`:

```python
import numpy as np


def test_fixture_shape_and_norms(real_vectors):
    n, dim = real_vectors.matrix.shape
    assert n >= 40
    assert dim == 1024
    assert real_vectors.matrix.dtype == np.float32
    norms = np.linalg.norm(real_vectors.matrix, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_fixture_groups_present(real_vectors):
    groups = {e["group"] for e in real_vectors.entries}
    assert sum(1 for g in groups if g.startswith("topic:")) >= 8
    assert {f"neardup:{i}" for i in range(5)} <= groups
    assert "unfiled" in groups


def test_neardup_pairs_are_actually_near(real_vectors):
    for i in range(5):
        pair = real_vectors.by_group(f"neardup:{i}")
        assert len(pair) == 2
        (_, a), (_, b) = pair
        assert float(a @ b) > 0.97


def test_topic_groups_are_geometrically_distinct(real_vectors):
    """Members sit closer to their own group's centroid than to a foreign one
    for at least most groups — the property threshold tests depend on."""
    groups: dict[str, list[np.ndarray]] = {}
    for e, row in zip(real_vectors.entries, real_vectors.matrix):
        if e["group"].startswith("topic:"):
            groups.setdefault(e["group"], []).append(row)
    cents = {g: np.mean(v, axis=0) / np.linalg.norm(np.mean(v, axis=0))
             for g, v in groups.items()}
    own_wins = 0
    total = 0
    for g, vecs in groups.items():
        for v in vecs:
            own = float(v @ cents[g])
            best_other = max(float(v @ c) for og, c in cents.items() if og != g)
            total += 1
            if own > best_other:
                own_wins += 1
    assert own_wins / total > 0.6
```

- [ ] **Step 5: Run the new tests, then the full suite**

Run: `cd kb-engine && uv run pytest tests/test_real_vector_fixtures.py -v && uv run pytest`
Expected: all green.

- [ ] **Step 6: Commit** (fixtures are committed binary+json — that's the point):

```bash
git add kb-engine/scripts/generate_real_vectors.py kb-engine/tests/fixtures/real_vectors.npy \
  kb-engine/tests/fixtures/real_vectors.json kb-engine/tests/conftest.py \
  kb-engine/tests/test_real_vector_fixtures.py
git commit -m "test(kb-engine): real jina-v3 vector fixtures + generator for geometry tests"
```

---

### Task 3: Near-dup report + search-time suppression + merge-flow doc

**Files:**
- Create: `kb-engine/src/kb_engine/dedup.py`
- Modify: `kb-engine/src/kb_engine/store.py` (add `note_vectors_for`)
- Modify: `kb-engine/src/kb_engine/search.py` (suppression in `hybrid_search`)
- Modify: `kb-engine/src/kb_engine/cli.py` (new top-level `dedup-report` command)
- Modify: `~/.claude/commands/kb/review.md` AND
  `chezmoi/private_dot_claude/commands/kb/review.md` (merge-flow section)
- Test: `kb-engine/tests/test_dedup.py`, `kb-engine/tests/test_search.py` (append),
  `kb-engine/tests/test_store.py` (append), `kb-engine/tests/test_cli.py` (append)

**Interfaces:**
- Produces: `Store.note_vectors_for(paths: list[str]) -> dict[str, np.ndarray]`
  (mean-pooled per note, missing paths absent from result);
  `dedup.near_duplicates(store: Store, threshold: float = 0.95) -> list[DupPair]`
  with `DupPair(a: str, b: str, cosine: float)` sorted cosine desc then (a, b);
  `search.SUPPRESS_THRESHOLD = 0.97`; `hybrid_search` drops any result whose
  note-vector cosine to an already-kept higher-ranked result exceeds 0.97
  (suppression runs after the scope filter and BEFORE the final `[:limit]` cut, so
  suppressed slots backfill from deeper candidates).

- [ ] **Step 1: Failing store test** (append to `tests/test_store.py`, using its
  existing tmp-store helpers — read the file first):

```python
def test_note_vectors_for_returns_only_requested(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.upsert_note("a.md", "A", "sha-a", [])
    store.upsert_note("b.md", "B", "sha-b", [])
    va = np.array([1.0, 0.0, 0.0], np.float32)
    vb = np.array([0.0, 1.0, 0.0], np.float32)
    store.replace_chunks("a.md", [(0, "a text", va)])
    store.replace_chunks("b.md", [(0, "b text", vb)])
    got = store.note_vectors_for(["a.md", "missing.md"])
    assert set(got) == {"a.md"}
    assert np.allclose(got["a.md"], va)
    store.close()
```

- [ ] **Step 2: Implement `note_vectors_for`** (in `store.py`, near `note_vectors`):

```python
    def note_vectors_for(self, paths: list[str]) -> dict[str, np.ndarray]:
        """Mean-pooled note vectors for just ``paths`` (missing paths omitted)."""
        out: dict[str, list[np.ndarray]] = {}
        marks = ",".join("?" for _ in paths)
        if not paths:
            return {}
        for note_path, blob in self._conn.execute(
            f"SELECT note_path, vector FROM chunks WHERE note_path IN ({marks})",
            list(paths),
        ):
            out.setdefault(note_path, []).append(_from_blob(blob))
        return {
            p: np.mean(vs, axis=0).astype(np.float32) for p, vs in out.items()
        }
```

Run: `uv run pytest tests/test_store.py -v` → green.

- [ ] **Step 3: Failing dedup tests** — `tests/test_dedup.py`:

```python
import numpy as np

from kb_engine.dedup import DupPair, near_duplicates
from kb_engine.store import Store


def _store_with(tmp_path, pairs):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    for path, vec in pairs:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, np.asarray(vec, np.float32))])
    return store


def test_near_duplicates_finds_fixture_twins(tmp_path, real_vectors):
    twins = real_vectors.by_group("neardup:0")
    far = real_vectors.by_group("unfiled")[:1]
    store = _store_with(tmp_path, twins + far)
    pairs = near_duplicates(store, threshold=0.95)
    assert len(pairs) == 1
    assert pairs[0].cosine > 0.97
    assert {pairs[0].a, pairs[0].b} == {p for p, _ in twins}
    store.close()


def test_near_duplicates_sorted_and_threshold_respected(tmp_path, real_vectors):
    d0 = real_vectors.by_group("neardup:0")
    d1 = real_vectors.by_group("neardup:1")
    store = _store_with(tmp_path, d0 + d1)
    pairs = near_duplicates(store, threshold=0.95)
    same_pair = [p for p in pairs if p.cosine > 0.97]
    assert len(same_pair) >= 2  # both fixture twin-pairs found
    assert pairs == sorted(pairs, key=lambda p: (-p.cosine, p.a, p.b))
    store.close()


def test_near_duplicates_empty_store(tmp_path):
    store = _store_with(tmp_path, [])
    assert near_duplicates(store) == []
    store.close()
```

Run: `uv run pytest tests/test_dedup.py -v` → FAIL (module missing).

- [ ] **Step 4: Implement `dedup.py`**:

```python
"""Near-duplicate detection over note gist vectors.

A one-shot report for the human merge flow (/kb:review): pairs of notes whose
note-vector cosine exceeds a threshold. Merging is a decision — this module
never mutates anything.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.store import Store

DEFAULT_DEDUP_THRESHOLD = 0.95


@dataclass(frozen=True)
class DupPair:
    a: str
    b: str
    cosine: float


def near_duplicates(
    store: Store, threshold: float = DEFAULT_DEDUP_THRESHOLD
) -> list[DupPair]:
    """All note pairs with cosine >= ``threshold``, best first (ties by paths)."""
    items = list(store.note_vectors())
    if len(items) < 2:
        return []
    paths = [p for p, _ in items]
    matrix = np.vstack([v for _, v in items])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    unit = matrix / norms
    sim = unit @ unit.T
    upper_i, upper_j = np.triu_indices(len(paths), k=1)
    hits = np.nonzero(sim[upper_i, upper_j] >= threshold)[0]
    pairs = [
        DupPair(a=paths[upper_i[h]], b=paths[upper_j[h]],
                cosine=float(sim[upper_i[h], upper_j[h]]))
        for h in hits
    ]
    return sorted(pairs, key=lambda p: (-p.cosine, p.a, p.b))
```

Run: `uv run pytest tests/test_dedup.py -v` → PASS.

- [ ] **Step 5: Failing suppression tests** (append to `tests/test_search.py` —
  read its existing helpers first and reuse them where they fit):

```python
def test_hybrid_search_suppresses_near_dup_twin(tmp_path, real_vectors):
    """Of two >0.97 twins, only the better-ranked survives; a distinct note stays."""
    twins = real_vectors.by_group("neardup:0")
    other = real_vectors.by_group("unfiled")[:1]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    for path, vec in twins + other:
        scoped = f"Knowledge/{path.split('/')[-1]}"
        store.upsert_note(scoped, scoped, f"sha-{scoped}", [])
        store.replace_chunks(scoped, [(0, "shared token text", vec)])

    class OneTwinEmbedder:
        dim = 1024
        def embed_query(self, text):
            return twins[0][1]
        def embed_passages(self, texts):
            return [twins[0][1] for _ in texts]

    results = hybrid_search(store, OneTwinEmbedder(), "shared token", limit=10)
    paths = [p for p, _ in results]
    twin_hits = [p for p in paths if p in {
        f"Knowledge/{t.split('/')[-1]}" for t, _ in twins
    }]
    assert len(twin_hits) == 1, f"expected one surviving twin, got {twin_hits}"
    store.close()


def test_hybrid_search_keeps_distinct_notes(tmp_path, real_vectors):
    """Sub-threshold notes are never suppressed."""
    distinct = real_vectors.by_group("topic:")[:4]  # 4 members of ≥2 topics
    store = Store(tmp_path / "t.db")
    store.init_schema()
    for path, vec in distinct:
        scoped = f"Knowledge/{path.split('/')[-1]}"
        store.upsert_note(scoped, scoped, f"sha-{scoped}", [])
        store.replace_chunks(scoped, [(0, "shared token text", vec)])

    class FirstVecEmbedder:
        dim = 1024
        def embed_query(self, text):
            return distinct[0][1]
        def embed_passages(self, texts):
            return [distinct[0][1] for _ in texts]

    results = hybrid_search(store, FirstVecEmbedder(), "shared token", limit=10)
    assert len(results) == 4
    store.close()
```

(Check the fixture's `topic:` first-4 selection: if two of those members exceed 0.97
cosine — unlikely but possible — pick members from two different `topic:` groups
explicitly. The test must use vectors known to be below the threshold; assert that in
the test setup with `assert all(float(a @ b) < 0.97 ...)` over the chosen pairs.)

Run: `uv run pytest tests/test_search.py -v` → new tests FAIL (no suppression yet).

- [ ] **Step 6: Implement suppression in `search.py`**:

```python
import numpy as np
```

(top of file, after existing imports), then:

```python
SUPPRESS_THRESHOLD = 0.97


def _suppress_near_dups(
    store: Store, ranked: Ranked, threshold: float = SUPPRESS_THRESHOLD
) -> Ranked:
    """Drop results whose note vector is a >threshold cosine twin of a
    higher-ranked kept result (the best-ranked twin survives). Results without
    a stored vector are kept — fail open."""
    vectors = store.note_vectors_for([path for path, _ in ranked])
    kept: Ranked = []
    kept_units: list[np.ndarray] = []
    for path, score in ranked:
        vector = vectors.get(path)
        if vector is None:
            kept.append((path, score))
            continue
        norm = float(np.linalg.norm(vector))
        unit = vector / norm if norm else vector
        if any(float(unit @ ku) > threshold for ku in kept_units):
            continue
        kept.append((path, score))
        kept_units.append(unit)
    return kept
```

and change the tail of `hybrid_search`:

```python
    fused = [(p, s) for p, s in fused if p.startswith(scope_prefix)]
    fused = _suppress_near_dups(store, fused)
    return fused[:limit]
```

Run: `uv run pytest tests/test_search.py tests/test_dedup.py -v` → PASS.

- [ ] **Step 7: Failing CLI test** (append to `tests/test_cli.py`, reusing `_invoke`):

```python
def test_dedup_report_json(tmp_path, monkeypatch, real_vectors):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    for path, vec in real_vectors.by_group("neardup:0"):
        p = f"Knowledge/{path.split('/')[-1]}"
        store.upsert_note(p, p, f"sha-{p}", [])
        store.replace_chunks(p, [(0, p, vec)])
    store.close()
    r = _invoke(
        ["--vault", str(tmp_path), "--db", str(db), "dedup-report", "--json"],
        monkeypatch,
    )
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload["threshold"] == 0.95
    assert len(payload["pairs"]) == 1
    assert payload["pairs"][0]["cosine"] > 0.97
```

- [ ] **Step 8: Implement the CLI command** (in `cli.py`, top-level command near
  the other report commands; import `near_duplicates` + `DEFAULT_DEDUP_THRESHOLD`
  from `kb_engine.dedup`):

```python
@main.command("dedup-report")
@click.option(
    "--threshold",
    default=DEFAULT_DEDUP_THRESHOLD,
    show_default=True,
    type=float,
    help="Min cosine for a pair to count as a near-duplicate.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def dedup_report(cfg: Config, threshold: float, as_json: bool) -> None:
    """Report near-duplicate note pairs (gist-vector cosine >= threshold).

    Read-only. Merging is a human decision — see /kb:review's merge flow."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        pairs = near_duplicates(store, threshold=threshold)
    finally:
        store.close()
    if as_json:
        click.echo(json.dumps({
            "threshold": threshold,
            "pairs": [
                {"a": p.a, "b": p.b, "cosine": round(p.cosine, 6)} for p in pairs
            ],
        }))
        return
    if not pairs:
        click.echo(f"No pairs >= {threshold}.")
        return
    for p in pairs:
        click.echo(f"{p.cosine:.4f}  {p.a}  <->  {p.b}")
    click.echo(f"{len(pairs)} pair(s) >= {threshold}")
```

Run: `uv run pytest tests/test_cli.py -v` → PASS.

- [ ] **Step 9: Merge-flow doc** — add this section to
  `~/.claude/commands/kb/review.md` (after the topic-proposals section; read the file
  and match its heading numbering), and make the identical edit in
  `chezmoi/private_dot_claude/commands/kb/review.md`:

```markdown
### N. Merge near-duplicates (when the user asks, or a sweep is due)

Re-captures of the same content (e.g. the same tweet clipped twice) waste review
attention. Search already suppresses >0.97 cosine twins automatically (best-ranked
survives) — merging cleans the vault itself. **Merging is a decision: propose, let
the human confirm each pair. Never delete a note.**

1. `kb-engine --vault "<Main>" dedup-report --json` → pairs sorted by cosine.
2. For each confirmed pair, pick the keeper (better title/content/enrichment):
   - Union the `why:` lines — if the twin's `why` adds intent the keeper lacks,
     append it to the keeper's `why`.
   - Carry over any human-written frontmatter the keeper lacks (never overwrite
     the keeper's own human text).
   - On the twin, add frontmatter `duplicate_of: "<keeper vault-relative path>"`
     — the twin stays on disk (nothing lost), suppression keeps it out of search.
3. Report merged pairs to the user in the pass summary.
```

Verify: `diff ~/.claude/commands/kb/review.md chezmoi/private_dot_claude/commands/kb/review.md`
→ no output.

- [ ] **Step 10: Full suite + commit**

Run: `cd kb-engine && uv run pytest`
Expected: all green.

```bash
git add kb-engine/src/kb_engine/dedup.py kb-engine/src/kb_engine/search.py \
  kb-engine/src/kb_engine/store.py kb-engine/src/kb_engine/cli.py \
  kb-engine/tests/test_dedup.py kb-engine/tests/test_search.py \
  kb-engine/tests/test_store.py kb-engine/tests/test_cli.py \
  chezmoi/private_dot_claude/commands/kb/review.md
git commit -m "feat(kb-engine): near-dup report + search-time twin suppression + merge flow"
```

(The live `~/.claude/commands/kb/review.md` copy is outside the repo — edited but not
committed; chezmoi source is the committed twin.)

**Controller note (not an implementer step):** after this task's review closes, the
controller runs the LIVE eval (`kb-engine --vault "<Main>" eval`) — suppression
touches retrieval, so the gate must be checked here, not just at phase exit. Also
cross-check: no probe expected path may lose its hit to a suppressed-twin ranking
above it (any-of probe lists make this unlikely; if it fires, the fix is adding the
surviving twin to that probe's any-of list — a vault `probes.yaml` edit, human-visible).

---

### Task 4: Member-centroid re-anchoring

**Files:**
- Create: `kb-engine/src/kb_engine/topics/anchoring.py`
- Modify: `kb-engine/src/kb_engine/models.py` (Topic gains `anchor_source`)
- Modify: `kb-engine/src/kb_engine/store.py` (column + load/save + `update_topic_anchor`)
- Modify: `kb-engine/src/kb_engine/cli.py` (`topics reanchor`)
- Test: `kb-engine/tests/test_anchoring.py`, `tests/test_store.py` (append),
  `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `Store.note_vectors_for` (Task 3), `Store.topic_members`.
- Produces: `Topic.anchor_source: str = "label"` (`"label" | "members"`);
  `Store.update_topic_anchor(slug: str, centroid: np.ndarray, anchor_source: str) -> None`;
  `anchoring.reanchor_topics(store: Store) -> ReanchorResult` with
  `ReanchorResult(reanchored: tuple[str, ...], kept_label: tuple[str, ...])`;
  `anchoring.MIN_MEMBERS_FOR_REANCHOR = 3`.
  Task 7's weekly pass calls `reanchor_topics` first.

- [ ] **Step 1: Failing model/store tests** (append to `tests/test_store.py`):

```python
def test_topic_anchor_source_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    c = np.array([1.0, 0.0], np.float32)
    store.add_manual_topic("t1", "T1", "desc", c)
    loaded = store.load_topics()[0]
    assert loaded.anchor_source == "label"
    new = np.array([0.0, 1.0], np.float32)
    store.update_topic_anchor("t1", new, "members")
    loaded = store.load_topics()[0]
    assert loaded.anchor_source == "members"
    assert np.allclose(loaded.centroid, new)
    store.close()


def test_existing_db_gains_anchor_source_column(tmp_path):
    """init_schema on a pre-Phase-4 DB backfills the column with 'label'."""
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        "CREATE TABLE topics (slug TEXT PRIMARY KEY, label TEXT, keywords TEXT,"
        " centroid BLOB NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL);"
    )
    conn.execute(
        "INSERT INTO topics VALUES ('old', 'Old', '[]', ?, 'manual', 'active')",
        (np.ones(2, np.float32).tobytes(),),
    )
    conn.commit()
    conn.close()
    store = Store(db)
    store.init_schema()
    assert store.load_topics()[0].anchor_source == "label"
    store.close()
```

(`import sqlite3` at the top of the test file if not present.)

- [ ] **Step 2: Implement model + store changes.**

`models.py` — Topic gains one field (defaulted, so all existing constructor calls
stay valid):

```python
@dataclass(frozen=True)
class Topic:
    slug: str
    label: str
    keywords: tuple[str, ...]
    centroid: np.ndarray  # float32, unit-normalized
    kind: str  # "discovered" | "manual"
    status: str  # "proposed" | "active" | "deprecated"
    anchor_source: str = "label"  # "label" (text anchor) | "members" (centroid of members)
```

`store.py`:
- In `init_schema`, after the existing `_ensure_column` calls:

```python
        # Backfill for databases created before topic re-anchoring (Phase 4).
        self._ensure_column("topics", "anchor_source", "TEXT NOT NULL DEFAULT 'label'")
```

- Add `anchor_source` to the `topics` CREATE TABLE in `_SCHEMA`
  (`anchor_source TEXT NOT NULL DEFAULT 'label'` after `status`).
- `load_topics`: SELECT gains `anchor_source`; constructor passes it through.
- `save_topics`: INSERT gains the column, value `topic.anchor_source`.
- New method:

```python
    def update_topic_anchor(
        self, slug: str, centroid: np.ndarray, anchor_source: str
    ) -> None:
        """Swap a topic's anchor centroid and record where it came from."""
        with self._conn:
            self._conn.execute(
                "UPDATE topics SET centroid = ?, anchor_source = ? WHERE slug = ?",
                (_to_blob(centroid), anchor_source, slug),
            )
```

Run: `uv run pytest tests/test_store.py -v` → PASS.

- [ ] **Step 3: Failing anchoring tests** — `tests/test_anchoring.py`:

```python
import numpy as np

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics.anchoring import MIN_MEMBERS_FOR_REANCHOR, reanchor_topics


def _seed(store, slug, members, status="active"):
    store.add_manual_topic(slug, slug.upper(), "desc", np.ones(1024, np.float32))
    if status != "active":
        store._conn.execute("UPDATE topics SET status=? WHERE slug=?", (status, slug))
    rows = []
    for path, vec in members:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
        rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
    store.set_members(slug, rows)


def test_reanchor_uses_unit_mean_of_members(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:3]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed(store, "warm", members)
    result = reanchor_topics(store)
    assert result.reanchored == ("warm",)
    topic = store.load_topics()[0]
    mean = np.mean([v for _, v in members], axis=0)
    expected = mean / np.linalg.norm(mean)
    assert np.allclose(topic.centroid, expected, atol=1e-6)
    assert topic.anchor_source == "members"
    assert abs(float(np.linalg.norm(topic.centroid)) - 1.0) < 1e-5
    store.close()


def test_cold_start_keeps_label_anchor(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[: MIN_MEMBERS_FOR_REANCHOR - 1]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed(store, "cold", members)
    result = reanchor_topics(store)
    assert result.reanchored == ()
    assert result.kept_label == ("cold",)
    topic = store.load_topics()[0]
    assert topic.anchor_source == "label"
    assert np.allclose(topic.centroid, np.ones(1024, np.float32))
    store.close()


def test_reanchor_skips_non_manual_and_non_active(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:3]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed(store, "dormant", members, status="deprecated")
    result = reanchor_topics(store)
    assert result.reanchored == ()
    assert result.kept_label == ()
    store.close()


def test_reanchor_is_idempotent(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:3]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed(store, "warm", members)
    reanchor_topics(store)
    first = store.load_topics()[0].centroid.copy()
    reanchor_topics(store)
    assert np.allclose(store.load_topics()[0].centroid, first)
    store.close()
```

Run: `uv run pytest tests/test_anchoring.py -v` → FAIL (module missing).

- [ ] **Step 4: Implement `topics/anchoring.py`**:

```python
"""Member-centroid re-anchoring for manual topics.

A manual topic starts life anchored by an embedding of its label+description
(cold start). Once it has enough confirmed members, the members themselves are
the better definition of the topic — the anchor becomes the unit-normalized
mean of member vectors, and ``anchor_source`` records the provenance.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.store import Store

MIN_MEMBERS_FOR_REANCHOR = 3


@dataclass(frozen=True)
class ReanchorResult:
    reanchored: tuple[str, ...]  # slugs whose anchor was recomputed from members
    kept_label: tuple[str, ...]  # manual/active slugs still on their label anchor


def reanchor_topics(store: Store) -> ReanchorResult:
    """Recompute anchors for manual/active topics with enough member vectors.

    Idempotent: the mean of an unchanged member set is unchanged. Members
    without a stored vector (e.g. evicted, never synced) don't count toward
    the minimum.
    """
    reanchored: list[str] = []
    kept: list[str] = []
    for topic in store.load_topics():
        if topic.kind != "manual" or topic.status != "active":
            continue
        member_paths = [m.note_path for m in store.topic_members(topic.slug)]
        vectors = store.note_vectors_for(member_paths)
        if len(vectors) < MIN_MEMBERS_FOR_REANCHOR:
            kept.append(topic.slug)
            continue
        mean = np.mean(list(vectors.values()), axis=0)
        norm = float(np.linalg.norm(mean))
        if norm == 0.0:
            kept.append(topic.slug)
            continue
        store.update_topic_anchor(
            topic.slug, (mean / norm).astype(np.float32), "members"
        )
        reanchored.append(topic.slug)
    return ReanchorResult(reanchored=tuple(reanchored), kept_label=tuple(kept))
```

Run: `uv run pytest tests/test_anchoring.py -v` → PASS.

- [ ] **Step 5: CLI command + test.** Failing test (append to `tests/test_cli.py`):

```python
def test_topics_reanchor_json(tmp_path, monkeypatch, real_vectors):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("warm", "Warm", "d", np.ones(1024, np.float32))
    rows = []
    for path, vec in real_vectors.by_group("topic:")[:3]:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
        rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
    store.set_members("warm", rows)
    store.close()
    r = _invoke(
        ["--vault", str(tmp_path), "--db", str(db), "topics", "reanchor", "--json"],
        monkeypatch,
    )
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload["reanchored"] == ["warm"]
```

Implementation (in `cli.py` under the `topics` group; import `reanchor_topics`
from `kb_engine.topics.anchoring`):

```python
@topics.command("reanchor")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_reanchor(cfg: Config, as_json: bool) -> None:
    """Recompute manual-topic anchors from member vectors (>=3 members)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        result = reanchor_topics(store)
    finally:
        store.close()
    _emit(
        {
            "reanchored": list(result.reanchored),
            "kept_label": list(result.kept_label),
        },
        as_json,
        f"Re-anchored {len(result.reanchored)} topic(s); "
        f"{len(result.kept_label)} kept label anchor.",
    )
```

Run: `uv run pytest tests/test_cli.py -v` → PASS.

- [ ] **Step 6: Full suite + commit**

Run: `cd kb-engine && uv run pytest`

```bash
git add kb-engine/src/kb_engine/topics/anchoring.py kb-engine/src/kb_engine/models.py \
  kb-engine/src/kb_engine/store.py kb-engine/src/kb_engine/cli.py \
  kb-engine/tests/test_anchoring.py kb-engine/tests/test_store.py kb-engine/tests/test_cli.py
git commit -m "feat(kb-engine): member-centroid re-anchoring with anchor provenance"
```

---

### Task 5: Per-topic thresholds (derive + persist + dry-run report)

**Files:**
- Create: `kb-engine/src/kb_engine/topics/thresholds.py`
- Modify: `kb-engine/src/kb_engine/models.py` (Topic gains `threshold_high`/`threshold_secondary`)
- Modify: `kb-engine/src/kb_engine/store.py` (columns + `set_topic_thresholds`)
- Modify: `kb-engine/src/kb_engine/cli.py` (`topics thresholds [--dry-run]`)
- Test: `kb-engine/tests/test_thresholds.py`, `tests/test_store.py` (append),
  `tests/test_cli.py` (append)

**Interfaces:**
- Produces: `Topic.threshold_high: float | None = None`,
  `Topic.threshold_secondary: float | None = None` (None = underived → assignment
  falls back to global flags);
  `Store.set_topic_thresholds(slug: str, high: float, secondary: float) -> None`;
  `thresholds.derive_thresholds(store: Store, statuses: tuple[str, ...] = ("active",)) -> list[TopicThresholdStats]`
  with `TopicThresholdStats(slug, n_members, p25, p50, p75, high, secondary)`;
  `thresholds.persist_thresholds(store: Store, stats: list[TopicThresholdStats]) -> int`;
  `thresholds.THRESHOLD_FLOOR = 0.45`, `thresholds.SECONDARY_OFFSET = 0.08`.
- Formula (from the spec, validated on live data): `high = max(0.45, p25(member
  sims vs current centroid))`, `secondary = high − 0.08`. Sims are computed against
  the CURRENT stored centroid — run after `reanchor` for member-based thresholds.

- [ ] **Step 1: Failing store tests** (append to `tests/test_store.py`):

```python
def test_topic_thresholds_roundtrip_and_default_none(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(2, np.float32))
    assert store.load_topics()[0].threshold_high is None
    assert store.load_topics()[0].threshold_secondary is None
    store.set_topic_thresholds("t1", 0.61, 0.53)
    loaded = store.load_topics()[0]
    assert loaded.threshold_high == pytest.approx(0.61)
    assert loaded.threshold_secondary == pytest.approx(0.53)
    store.close()
```

- [ ] **Step 2: Implement model + store changes.**

`models.py` Topic (after `anchor_source`):

```python
    threshold_high: float | None = None  # per-topic primary bar; None = use global
    threshold_secondary: float | None = None  # per-topic cross-link bar; None = global
```

`store.py`:
- `_SCHEMA` topics table gains `threshold_high REAL, threshold_secondary REAL`.
- `init_schema` gains:

```python
        self._ensure_column("topics", "threshold_high", "REAL")
        self._ensure_column("topics", "threshold_secondary", "REAL")
```

- `load_topics` SELECT + constructor pass both through.
- `save_topics` INSERT includes both (values from the Topic; discovered topics
  carry None).
- New method:

```python
    def set_topic_thresholds(self, slug: str, high: float, secondary: float) -> None:
        """Persist a topic's derived assignment thresholds."""
        with self._conn:
            self._conn.execute(
                "UPDATE topics SET threshold_high = ?, threshold_secondary = ? "
                "WHERE slug = ?",
                (high, secondary, slug),
            )
```

Run: `uv run pytest tests/test_store.py -v` → PASS.

- [ ] **Step 3: Failing derivation tests** — `tests/test_thresholds.py`:

```python
import numpy as np
import pytest

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics.thresholds import (
    SECONDARY_OFFSET,
    THRESHOLD_FLOOR,
    derive_thresholds,
    persist_thresholds,
)


def _seed_topic(store, slug, members):
    store.add_manual_topic(slug, slug.upper(), "d", np.ones(1024, np.float32))
    rows = []
    for path, vec in members:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
        rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
    store.set_members(slug, rows)


def test_derive_matches_numpy_percentiles(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:4]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed_topic(store, "t1", members)
    centroid = store.load_topics()[0].centroid
    c_unit = centroid / np.linalg.norm(centroid)
    sims = np.array([
        float((v / np.linalg.norm(v)) @ c_unit) for _, v in members
    ])
    stats = derive_thresholds(store)
    assert len(stats) == 1
    s = stats[0]
    assert s.slug == "t1"
    assert s.n_members == 4
    assert s.p25 == pytest.approx(float(np.percentile(sims, 25)), abs=1e-6)
    assert s.high == pytest.approx(max(THRESHOLD_FLOOR, s.p25))
    assert s.secondary == pytest.approx(s.high - SECONDARY_OFFSET)
    store.close()


def test_floor_binds_for_loose_topics(tmp_path, real_vectors):
    """Members from DIFFERENT topics make a loose cluster — p25 vs the label
    anchor lands low, so the 0.45 floor must bind."""
    mixed = [real_vectors.by_group("topic:")[0], real_vectors.by_group("unfiled")[0],
             real_vectors.by_group("neardup:0")[0]]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed_topic(store, "loose", mixed)
    stats = derive_thresholds(store)
    assert stats[0].high >= THRESHOLD_FLOOR
    store.close()


def test_persist_writes_columns(tmp_path, real_vectors):
    members = real_vectors.by_group("topic:")[:3]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    _seed_topic(store, "t1", members)
    stats = derive_thresholds(store)
    n = persist_thresholds(store, stats)
    assert n == 1
    loaded = store.load_topics()[0]
    assert loaded.threshold_high == pytest.approx(stats[0].high)
    assert loaded.threshold_secondary == pytest.approx(stats[0].secondary)
    store.close()


def test_topics_without_member_vectors_skipped(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.add_manual_topic("empty", "E", "d", np.ones(4, np.float32))
    assert derive_thresholds(store) == []
    store.close()
```

Run: `uv run pytest tests/test_thresholds.py -v` → FAIL (module missing).

- [ ] **Step 4: Implement `topics/thresholds.py`**:

```python
"""Per-topic assignment thresholds derived from member-similarity distributions.

Formula (spec §6 Phase 4, validated on live data at plan time):
``high = max(0.45, p25(member sims vs current centroid))``,
``secondary = high - 0.08``. Derive AFTER re-anchoring so member-based topics
measure against their member-mean anchor.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.store import Store

THRESHOLD_FLOOR = 0.45
SECONDARY_OFFSET = 0.08


@dataclass(frozen=True)
class TopicThresholdStats:
    slug: str
    n_members: int
    p25: float
    p50: float
    p75: float
    high: float
    secondary: float


def derive_thresholds(
    store: Store, statuses: tuple[str, ...] = ("active",)
) -> list[TopicThresholdStats]:
    """Member-sim distribution stats + derived thresholds per topic (by slug).

    Topics with no member vectors (or a degenerate centroid) are skipped —
    they keep whatever thresholds they had (usually None → global fallback).
    """
    out: list[TopicThresholdStats] = []
    for topic in store.load_topics():
        if topic.status not in statuses:
            continue
        centroid_norm = float(np.linalg.norm(topic.centroid))
        if centroid_norm == 0.0:
            continue
        c_unit = topic.centroid / centroid_norm
        member_paths = [m.note_path for m in store.topic_members(topic.slug)]
        vectors = store.note_vectors_for(member_paths)
        if not vectors:
            continue
        sims = np.array([
            float((v / (np.linalg.norm(v) or 1.0)) @ c_unit)
            for v in vectors.values()
        ])
        p25, p50, p75 = (float(np.percentile(sims, q)) for q in (25, 50, 75))
        high = max(THRESHOLD_FLOOR, p25)
        out.append(
            TopicThresholdStats(
                slug=topic.slug,
                n_members=len(sims),
                p25=p25,
                p50=p50,
                p75=p75,
                high=high,
                secondary=high - SECONDARY_OFFSET,
            )
        )
    return out


def persist_thresholds(store: Store, stats: list[TopicThresholdStats]) -> int:
    """Write derived thresholds to the topics table; returns rows written."""
    for s in stats:
        store.set_topic_thresholds(s.slug, s.high, s.secondary)
    return len(stats)
```

Run: `uv run pytest tests/test_thresholds.py -v` → PASS.

- [ ] **Step 5: CLI `topics thresholds` + test.** Failing test (append to
  `tests/test_cli.py`):

```python
def test_topics_thresholds_dry_run_does_not_persist(tmp_path, monkeypatch, real_vectors):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(1024, np.float32))
    rows = []
    for path, vec in real_vectors.by_group("topic:")[:3]:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
        rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
    store.set_members("t1", rows)
    store.close()

    r = _invoke(["--vault", str(tmp_path), "--db", str(db),
                 "topics", "thresholds", "--dry-run", "--json"], monkeypatch)
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload["persisted"] is False
    assert payload["topics"][0]["slug"] == "t1"
    store = Store(db)
    store.init_schema()
    assert store.load_topics()[0].threshold_high is None
    store.close()

    r2 = _invoke(["--vault", str(tmp_path), "--db", str(db),
                  "topics", "thresholds", "--json"], monkeypatch)
    assert json.loads(r2.output)["persisted"] is True
    store = Store(db)
    store.init_schema()
    assert store.load_topics()[0].threshold_high is not None
    store.close()
```

Implementation (in `cli.py` under `topics`; import `derive_thresholds`,
`persist_thresholds` from `kb_engine.topics.thresholds`):

```python
@topics.command("thresholds")
@click.option("--dry-run", is_flag=True, help="Report only; do not persist.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_thresholds(cfg: Config, dry_run: bool, as_json: bool) -> None:
    """Derive per-topic assignment thresholds from member-sim distributions.

    high = max(0.45, p25 of member cosines to the current anchor);
    secondary = high - 0.08. Persists unless --dry-run."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        stats = derive_thresholds(store)
        if not dry_run:
            persist_thresholds(store, stats)
    finally:
        store.close()
    rows = [
        {
            "slug": s.slug, "n_members": s.n_members,
            "p25": round(s.p25, 4), "p50": round(s.p50, 4), "p75": round(s.p75, 4),
            "high": round(s.high, 4), "secondary": round(s.secondary, 4),
        }
        for s in stats
    ]
    if as_json:
        click.echo(json.dumps({"persisted": not dry_run, "topics": rows}))
        return
    for r in rows:
        click.echo(
            f"{r['slug']:40} n={r['n_members']:>3} p25={r['p25']:.3f} "
            f"p50={r['p50']:.3f} p75={r['p75']:.3f} -> high={r['high']:.3f} "
            f"secondary={r['secondary']:.3f}"
        )
    click.echo(
        f"{len(rows)} topic(s) {'reported (dry-run)' if dry_run else 'persisted'}"
    )
```

Run: `uv run pytest tests/test_cli.py -v` → PASS.

- [ ] **Step 6: Full suite + commit**

```bash
cd kb-engine && uv run pytest
git add kb-engine/src/kb_engine/topics/thresholds.py kb-engine/src/kb_engine/models.py \
  kb-engine/src/kb_engine/store.py kb-engine/src/kb_engine/cli.py \
  kb-engine/tests/test_thresholds.py kb-engine/tests/test_store.py kb-engine/tests/test_cli.py
git commit -m "feat(kb-engine): per-topic thresholds derived from member-sim distributions"
```

---

### Task 6: Per-topic assignment + review-queue store primitives

**Files:**
- Modify: `kb-engine/src/kb_engine/topics/assignment.py`
- Modify: `kb-engine/src/kb_engine/models.py` (new `QueueEntry`)
- Modify: `kb-engine/src/kb_engine/store.py` (review_queue table + methods,
  `replace_auto_members`, `user_primary_paths`)
- Modify: `kb-engine/src/kb_engine/cli.py` (assign command: constants import +
  borderline shape)
- Test: `kb-engine/tests/test_assignment.py` (extend), `tests/test_store.py` (append)

**Interfaces:**
- Consumes: `Topic.threshold_high` / `threshold_secondary` (Task 5).
- Produces:
  - Constants move: `DEFAULT_ASSIGN_HIGH = 0.55`, `DEFAULT_ASSIGN_SECONDARY = 0.45`,
    `DEFAULT_ASSIGN_LOW = 0.4` now live in `topics/assignment.py`; `cli.py` imports
    them from there (delete the cli-local definitions).
  - `assign_notes(note_vectors, topics, high, secondary, low)` — same signature,
    new per-topic semantics (below). **Backward compatible:** with no per-topic
    thresholds set, behavior is unchanged.
  - `Borderline` type becomes `list[tuple[str, tuple[tuple[str, float], ...]]]`
    — path + up to top-3 `(slug, score)` candidates, best first.
  - `Store.replace_auto_members(slug: str, members: list[TopicMember]) -> None` —
    deletes the topic's `source='auto'` rows, inserts the new ones with
    `INSERT OR IGNORE` (existing user/seed rows always win).
  - `Store.user_primary_paths() -> set[str]` — note paths having any
    `source='user' AND is_primary=1` membership.
  - `QueueEntry(note_path: str, candidates: tuple[tuple[str, float], ...], reason: str, created_at: str = "")`
    in models.py; `Store.replace_review_queue(entries: list[QueueEntry]) -> None`
    (full rewrite, single transaction, `created_at = datetime('now')`);
    `Store.load_review_queue() -> list[QueueEntry]` (ordered by best-candidate
    score desc, then path); `Store.remove_from_review_queue(note_path: str) -> None`.

**Assignment semantics (per-topic):** for each note, rank all non-degenerate topics
by cosine. Let `high_t = topic.threshold_high if set else high`,
`sec_t = topic.threshold_secondary if set else secondary`,
`low_t = topic.threshold_secondary if set else low`.
- **Primary** = the highest-scoring topic among those the note *clears*
  (`score >= high_t`). (Not merely the top-ranked topic — a note may fail a tight
  topic's bar yet clear a looser one ranked just below.)
- **Secondaries** = up to 2 other topics with `score >= sec_t` (their own bar),
  taken in rank order. Unchanged `secondary > high` global validation stays.
- **Borderline** (only when nothing was cleared): the top-ranked topic's score is in
  `[low_t, high_t)` → the note is queued with its top-3 `(slug, score)` candidates.
- Else unassigned.

- [ ] **Step 1: Failing assignment tests** (extend `tests/test_assignment.py`; keep
  every existing test unchanged — they must still pass, proving fallback compat):

```python
def _topic(slug, centroid, high=None, secondary=None):
    return Topic(
        slug=slug, label=slug.upper(), keywords=(slug,),
        centroid=np.asarray(centroid, np.float32), kind="manual", status="active",
        threshold_high=high, threshold_secondary=secondary,
    )


def _distinct_pair(real_vectors):
    """First fixture group pair where member 0 of g1 sits closer to its own
    centroid than to g2's — the geometric premise the tests below need
    (test_topic_groups_are_geometrically_distinct guarantees such pairs exist)."""
    groups = {}
    for e, row in zip(real_vectors.entries, real_vectors.matrix):
        if e["group"].startswith("topic:"):
            groups.setdefault(e["group"], []).append(row)
    items = list(groups.values())
    for i, v1 in enumerate(items):
        c1 = np.mean(v1, axis=0)
        c1 = c1 / np.linalg.norm(c1)
        for v2 in items[i + 1:]:
            c2 = np.mean(v2, axis=0)
            c2 = c2 / np.linalg.norm(c2)
            if float(v1[0] @ c1) > float(v1[0] @ c2):
                return v1, c1, v2, c2
    raise AssertionError("no geometrically distinct fixture group pair")


def test_per_topic_high_overrides_global(real_vectors):
    """A note failing a tight topic's bar but clearing a looser lower-ranked
    topic gets the looser topic as primary."""
    v1, c1, v2, c2 = _distinct_pair(real_vectors)
    note = v1[0]  # a member of g1
    s1 = float(note @ c1)
    s2 = float(note @ c2)
    assert s1 > s2
    # tight bar on its own topic (just above its score), loose on the other
    topics = [
        _topic("own", c1, high=s1 + 0.01, secondary=s1 - 0.02),
        _topic("other", c2, high=max(0.0, s2 - 0.01), secondary=max(0.0, s2 - 0.02)),
    ]
    assigned, borderline = assign_notes(
        {"n.md": note}, topics, high=0.99, secondary=0.98, low=0.0
    )
    assert "n.md" in assigned
    assert assigned["n.md"][0].slug == "other"
    assert assigned["n.md"][0].is_primary is True


def test_borderline_carries_top3_candidates(real_vectors):
    members = real_vectors.by_group("topic:")
    note = members[0][1]
    cents = []
    for i in range(3):
        c = members[i][1].astype(np.float64)
        cents.append((c / np.linalg.norm(c)).astype(np.float32))
    scores = sorted((float(note @ c) for c in cents), reverse=True)
    top = scores[0]
    topics = [
        _topic(f"t{i}", cents[i], high=top + 0.05, secondary=None) for i in range(3)
    ]
    assigned, borderline = assign_notes(
        {"n.md": note}, topics, high=top + 0.05, secondary=top + 0.04, low=0.0
    )
    assert assigned == {}
    assert len(borderline) == 1
    path, candidates = borderline[0]
    assert path == "n.md"
    assert 1 <= len(candidates) <= 3
    assert candidates[0][1] == pytest.approx(top, abs=1e-5)
    assert [c[1] for c in candidates] == sorted(
        [c[1] for c in candidates], reverse=True
    )


def test_secondary_uses_each_topics_own_bar(real_vectors):
    v1, c1, v2, c2 = _distinct_pair(real_vectors)
    note = v1[0]
    s2 = float(note @ c2)
    topics_loose = [
        _topic("home", c1, high=0.0, secondary=0.0),
        _topic("link", c2, high=0.99, secondary=max(0.0, s2 - 0.01)),
    ]
    assigned, _ = assign_notes({"n.md": note}, topics_loose, 0.99, 0.98, 0.0)
    slugs = [a.slug for a in assigned["n.md"]]
    assert slugs[0] == "home" and "link" in slugs
    topics_tight = [
        _topic("home", c1, high=0.0, secondary=0.0),
        _topic("link", c2, high=0.99, secondary=min(1.0, s2 + 0.01)),
    ]
    assigned2, _ = assign_notes({"n.md": note}, topics_tight, 0.99, 0.98, 0.0)
    assert [a.slug for a in assigned2["n.md"]] == ["home"]
```

(`import pytest` and `from kb_engine.models import Topic` as needed at top.)

Run: `uv run pytest tests/test_assignment.py -v` → new tests FAIL.

- [ ] **Step 2: Rewrite `assignment.py`** (full file — it stays under 50-line
  functions):

```python
from dataclasses import dataclass
from typing import Mapping

import numpy as np

from kb_engine.models import Topic
from kb_engine.topics._math import cosine

DEFAULT_ASSIGN_HIGH = 0.55
DEFAULT_ASSIGN_SECONDARY = 0.45  # min cosine for a secondary (cross-link) topic
DEFAULT_ASSIGN_LOW = 0.4  # borderline floor: [low, high) lands in the review queue

_MAX_SECONDARIES = 2
_MAX_BORDERLINE_CANDIDATES = 3


@dataclass(frozen=True)
class Assignment:
    slug: str
    score: float
    is_primary: bool


# {path: [Assignment, ...]} — first element is the primary, rest are secondaries.
Assigned = dict[str, list[Assignment]]
# (path, top candidates (slug, score) best-first) pairs for the review queue.
Borderline = list[tuple[str, tuple[tuple[str, float], ...]]]


def _ranked(vector: np.ndarray, topics: list[Topic]) -> list[tuple[Topic, float]]:
    """(topic, score) for every non-degenerate topic, best first (ties by slug)."""
    scored = [
        (topic, cosine(vector, topic.centroid))
        for topic in topics
        if float(np.linalg.norm(topic.centroid)) != 0.0
    ]
    return sorted(scored, key=lambda ts: (-ts[1], ts[0].slug))


def _high(topic: Topic, fallback: float) -> float:
    return topic.threshold_high if topic.threshold_high is not None else fallback


def _secondary(topic: Topic, fallback: float) -> float:
    return (
        topic.threshold_secondary
        if topic.threshold_secondary is not None
        else fallback
    )


def assign_notes(
    note_vectors: Mapping[str, np.ndarray],
    topics: list[Topic],
    high: float,
    secondary: float,
    low: float,
) -> tuple[Assigned, Borderline]:
    """Assign each note a primary topic plus up to two secondaries.

    Per-topic thresholds (``Topic.threshold_high`` / ``threshold_secondary``)
    override the global ``high`` / ``secondary`` / ``low`` fallbacks:

    - primary: the highest-scoring topic whose own high bar the note clears
    - secondaries: up to 2 other topics clearing their own secondary bar
    - borderline: nothing cleared, but the top-ranked topic's score is inside
      ``[low_t, high_t)`` (``low_t`` = the topic's derived secondary, else
      ``low``) — reported with its top candidates for the review queue
    - else unassigned

    With no per-topic thresholds set this reduces exactly to the old global
    behavior. Deterministic (sorted paths; ranked ties by slug).
    """
    if secondary > high:
        raise ValueError(f"secondary ({secondary}) must be <= high ({high})")
    assigned: Assigned = {}
    borderline: Borderline = []
    for path in sorted(note_vectors):
        ranked = _ranked(note_vectors[path], topics)
        if not ranked:
            continue
        clearing = [(t, s) for t, s in ranked if s >= _high(t, high)]
        if not clearing:
            top_topic, top_score = ranked[0]
            low_t = (
                top_topic.threshold_secondary
                if top_topic.threshold_secondary is not None
                else low
            )
            if low_t <= top_score < _high(top_topic, high):
                candidates = tuple(
                    (t.slug, s) for t, s in ranked[:_MAX_BORDERLINE_CANDIDATES]
                )
                borderline.append((path, candidates))
            continue
        primary_topic, primary_score = clearing[0]
        members = [Assignment(primary_topic.slug, primary_score, True)]
        for topic, score in ranked:
            if topic.slug == primary_topic.slug:
                continue
            if len(members) - 1 >= _MAX_SECONDARIES:
                break
            if score >= _secondary(topic, secondary):
                members.append(Assignment(topic.slug, score, False))
        assigned[path] = members
    return assigned, borderline
```

- [ ] **Step 3: Update `cli.py` for the moved constants and new Borderline shape.**
  - Delete the three `DEFAULT_ASSIGN_*` definitions from `cli.py`; add them to the
    existing `from kb_engine.topics.assignment import assign_notes` import.
  - In `topics_assign`, replace the borderline rows construction with:

```python
        borderline_rows = [
            {
                "note": note_path,
                "topic": candidates[0][0],
                "score": round(candidates[0][1], 6),
                "candidates": [
                    {"topic": slug, "score": round(score, 6)}
                    for slug, score in candidates
                ],
            }
            for note_path, candidates in borderline
        ]
```

Run: `uv run pytest tests/test_assignment.py tests/test_cli.py -v` → PASS
(existing global-behavior tests must pass UNCHANGED — if one fails, the new
semantics broke backward compat; fix the implementation, not the test).

- [ ] **Step 4: Failing store tests** (append to `tests/test_store.py`):

```python
def test_replace_auto_members_preserves_user_rows(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(2, np.float32))
    store.set_members("t1", [
        TopicMember("keep.md", 1.0, "user", True),
        TopicMember("old-auto.md", 0.6, "auto", True),
    ])
    store.replace_auto_members("t1", [
        TopicMember("new-auto.md", 0.7, "auto", True),
        TopicMember("keep.md", 0.5, "auto", True),  # collides with user row
    ])
    members = {m.note_path: m for m in store.topic_members("t1")}
    assert set(members) == {"keep.md", "new-auto.md"}
    assert members["keep.md"].source == "user"  # user row untouched
    assert members["keep.md"].score == pytest.approx(1.0)
    store.close()


def test_user_primary_paths(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(2, np.float32))
    store.set_members("t1", [
        TopicMember("u.md", 1.0, "user", True),
        TopicMember("a.md", 0.6, "auto", True),
        TopicMember("s.md", 0.6, "user", False),  # user but secondary
    ])
    assert store.user_primary_paths() == {"u.md"}
    store.close()


def test_review_queue_roundtrip_and_ordering(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.replace_review_queue([
        QueueEntry("b.md", (("t1", 0.50), ("t2", 0.48)), "borderline"),
        QueueEntry("a.md", (("t3", 0.52),), "borderline"),
    ])
    entries = store.load_review_queue()
    assert [e.note_path for e in entries] == ["a.md", "b.md"]  # best score first
    assert entries[0].candidates == (("t3", 0.52),)
    assert entries[0].reason == "borderline"
    assert entries[0].created_at  # stamped by the store
    store.replace_review_queue([QueueEntry("c.md", (("t1", 0.5),), "borderline")])
    assert [e.note_path for e in store.load_review_queue()] == ["c.md"]
    store.remove_from_review_queue("c.md")
    assert store.load_review_queue() == []
    store.close()
```

(`from kb_engine.models import QueueEntry` at top of test file.)

- [ ] **Step 5: Implement models + store.**

`models.py`:

```python
@dataclass(frozen=True)
class QueueEntry:
    """A note awaiting a human topic decision (the borderline review queue)."""

    note_path: str
    candidates: tuple[tuple[str, float], ...]  # (topic slug, score), best first
    reason: str  # "borderline" (Phase 5 adds classifier reasons)
    created_at: str = ""  # stamped by the store on insert
```

`store.py` — `_SCHEMA` gains:

```sql
CREATE TABLE IF NOT EXISTS review_queue (
  note_path TEXT PRIMARY KEY,
  candidates TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

and the methods (import `QueueEntry` from models):

```python
    def replace_auto_members(self, slug: str, members: list[TopicMember]) -> None:
        """Replace a topic's auto-sourced members wholesale (one weekly pass's
        truth). Human rows (source user/seed) are never touched — on a path
        collision the existing human row wins (INSERT OR IGNORE)."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM topic_members WHERE topic_slug = ? AND source = 'auto'",
                (slug,),
            )
            for member in members:
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO topic_members(
                        topic_slug, note_path, score, source, is_primary
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (slug, member.note_path, member.score, member.source,
                     int(member.is_primary)),
                )

    def user_primary_paths(self) -> set[str]:
        """Note paths a human has pinned as primary somewhere (assignment skips them)."""
        rows = self._conn.execute(
            "SELECT DISTINCT note_path FROM topic_members "
            "WHERE source = 'user' AND is_primary = 1"
        ).fetchall()
        return {row[0] for row in rows}

    def replace_review_queue(self, entries: list[QueueEntry]) -> None:
        """Rewrite the borderline review queue (one weekly pass's truth)."""
        with self._conn:
            self._conn.execute("DELETE FROM review_queue")
            for entry in entries:
                self._conn.execute(
                    "INSERT INTO review_queue(note_path, candidates, reason, created_at) "
                    "VALUES(?, ?, ?, datetime('now'))",
                    (
                        entry.note_path,
                        json.dumps([[slug, score] for slug, score in entry.candidates]),
                        entry.reason,
                    ),
                )

    def load_review_queue(self) -> list[QueueEntry]:
        """Queue entries, best top-candidate score first (ties by path)."""
        rows = self._conn.execute(
            "SELECT note_path, candidates, reason, created_at FROM review_queue"
        ).fetchall()
        entries = [
            QueueEntry(
                note_path=path,
                candidates=tuple(
                    (slug, float(score)) for slug, score in json.loads(candidates)
                ),
                reason=reason,
                created_at=created_at,
            )
            for path, candidates, reason, created_at in rows
        ]
        return sorted(
            entries,
            key=lambda e: (-(e.candidates[0][1] if e.candidates else 0.0), e.note_path),
        )

    def remove_from_review_queue(self, note_path: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM review_queue WHERE note_path = ?", (note_path,)
            )
```

Run: `uv run pytest tests/test_store.py -v` → PASS.

- [ ] **Step 6: Full suite + commit**

```bash
cd kb-engine && uv run pytest
git add kb-engine/src/kb_engine/topics/assignment.py kb-engine/src/kb_engine/models.py \
  kb-engine/src/kb_engine/store.py kb-engine/src/kb_engine/cli.py \
  kb-engine/tests/test_assignment.py kb-engine/tests/test_store.py kb-engine/tests/test_cli.py
git commit -m "feat(kb-engine): per-topic assignment thresholds + review-queue store"
```

---

### Task 7: Weekly topic pass — retire sticky, wire pipeline + digest + nudge

**Files:**
- Create: `kb-engine/src/kb_engine/topics/weekly.py`
- Delete: `kb-engine/src/kb_engine/topics/sticky.py`, `kb-engine/tests/test_sticky.py`
- Modify: `kb-engine/src/kb_engine/pipeline.py` (weekly rewire)
- Modify: `kb-engine/src/kb_engine/importing/digest.py` (queue section)
- Modify: `kb-engine/src/kb_engine/cli.py` (drop `discover --sticky`; pipeline
  `--json` counts gain `queue`)
- Modify: `modules/home/dev/kb-engine.nix` (nudge sum includes queue — code edit
  only; `just switch` happens in Task 9)
- Test: `kb-engine/tests/test_weekly.py`, `tests/test_pipeline.py` (extend),
  `tests/test_digest.py` (extend), `tests/test_cli.py` (adjust)

**Interfaces:**
- Consumes: `reanchor_topics` (T4), `derive_thresholds`/`persist_thresholds` (T5),
  `assign_notes` + queue/store methods (T6), `build_topics` + `Clusterer` (existing).
- Produces: `weekly.weekly_topic_pass(store: Store, clusterer: Clusterer,
  high: float = DEFAULT_ASSIGN_HIGH, secondary: float = DEFAULT_ASSIGN_SECONDARY,
  low: float = DEFAULT_ASSIGN_LOW) -> WeeklyTopicsResult` with
  `WeeklyTopicsResult(reanchored: int, thresholds_set: int, assigned: int,
  queued: int, new_topics: int, unfiled: int)`.
  Weekly pipeline order becomes: import-mail → enrich → backfill → sync →
  **topics** → apply-topics → eval → digest (topics pass BEFORE apply so freshly
  assigned members get their tags the same run).
  `pipeline --json` counts gain `"queue"`; digest gains a "Borderline queue"
  section + checklist line.

**Weekly pass steps (inside `weekly_topic_pass`):**
1. `reanchor_topics(store)` — member-anchored manual topics.
2. `persist_thresholds(store, derive_thresholds(store))` — vs fresh anchors.
3. Assignment input = `dict(store.note_vectors())` minus `store.user_primary_paths()`
   (human-pinned notes are settled).
4. `assign_notes(input, active_topics, high, secondary, low)` where
   `active_topics = [t for t in store.load_topics() if t.status == "active"]`.
5. For EVERY active topic: `replace_auto_members(slug, new_members_for_slug)`
   (empty list clears a topic that lost all auto members — is_primary semantics are
   now real: one primary per note per pass, cross-topic staleness impossible).
6. `replace_review_queue([QueueEntry(path, candidates, "borderline") ...])`.
7. Residual = notes not assigned, not borderline, not user-pinned → cluster →
   `build_topics` → `save_topics` (discovered proposals, exactly like today).

- [ ] **Step 1: Failing weekly tests** — `tests/test_weekly.py`:

```python
import numpy as np

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics.weekly import WeeklyTopicsResult, weekly_topic_pass


class NoiseClusterer:
    """All-noise clusterer sized to its input (FakeClusterer needs exact-length
    labels known upfront; the weekly residual size varies with geometry)."""

    def cluster(self, vectors: np.ndarray) -> np.ndarray:
        return np.full(len(vectors), -1, dtype=int)


def _store_with_topicked_corpus(tmp_path, real_vectors):
    """Two manual topics seeded from fixture groups + a handful of loose notes."""
    store = Store(tmp_path / "t.db")
    store.init_schema()
    groups: dict[str, list[tuple[str, np.ndarray]]] = {}
    for entry, row in zip(real_vectors.entries, real_vectors.matrix):
        if entry["group"].startswith("topic:"):
            groups.setdefault(entry["group"], []).append((entry["path"], row))
    two = [g for g in groups.values() if len(g) >= 2][:2]
    for i, members in enumerate(two):
        slug = f"seed{i}"
        anchor = np.mean([v for _, v in members], axis=0)
        store.add_manual_topic(
            slug, slug.upper(), "d", (anchor / np.linalg.norm(anchor)).astype(np.float32)
        )
        rows = []
        for path, vec in members:
            store.upsert_note(path, path, f"sha-{path}", [])
            store.replace_chunks(path, [(0, path, vec)])
            rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
        store.set_members(slug, rows)
    for path, vec in real_vectors.by_group("unfiled"):
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
    return store


def test_weekly_pass_end_to_end(tmp_path, real_vectors):
    store = _store_with_topicked_corpus(tmp_path, real_vectors)
    n_notes = store.count_notes()
    result = weekly_topic_pass(store, NoiseClusterer())
    assert isinstance(result, WeeklyTopicsResult)
    # both seeded topics have <3 members? no — each has >=2; only >=3 reanchor.
    assert result.thresholds_set >= 1
    assert result.assigned >= 2  # at minimum the seeded members re-assign home
    assert result.assigned + result.queued + result.unfiled <= n_notes
    # members were written with real primary/secondary semantics
    primaries = [
        m for t in store.load_topics() for m in store.topic_members(t.slug)
        if m.is_primary
    ]
    assert len({m.note_path for m in primaries}) == len(primaries), (
        "a note must be primary in at most one topic"
    )
    store.close()


def test_weekly_pass_skips_user_pinned_notes(tmp_path, real_vectors):
    store = _store_with_topicked_corpus(tmp_path, real_vectors)
    pinned = store.topic_members("seed0")[0].note_path
    store.set_members(
        "seed1", [TopicMember(note_path=pinned, score=1.0, source="user", is_primary=True)]
    )
    weekly_topic_pass(store, NoiseClusterer())
    members1 = {m.note_path: m for m in store.topic_members("seed1")}
    assert members1[pinned].source == "user"
    seed0_auto = [
        m for m in store.topic_members("seed0")
        if m.note_path == pinned and m.source == "auto" and m.is_primary
    ]
    assert seed0_auto == [], "user-pinned note must not be auto-primaried elsewhere"
    store.close()


def test_weekly_pass_queues_borderline(tmp_path, real_vectors):
    store = _store_with_topicked_corpus(tmp_path, real_vectors)
    weekly_topic_pass(store, NoiseClusterer())
    for entry in store.load_review_queue():
        assert entry.reason == "borderline"
        assert entry.candidates
    store.close()
```

Run: `uv run pytest tests/test_weekly.py -v` → FAIL (module missing).

- [ ] **Step 2: Implement `topics/weekly.py`**:

```python
"""The weekly topic pass: re-anchor → derive thresholds → assign → queue →
cluster the residual into proposals.

Replaces the retired sticky-single mode (topics/sticky.py). Assignment is the
real primary + up-to-2-secondaries semantics with per-topic thresholds; the
borderline band lands in the persisted review_queue for /kb:review.
"""
from dataclasses import dataclass

import numpy as np

from kb_engine.models import QueueEntry, TopicMember
from kb_engine.store import Store
from kb_engine.topics.assignment import (
    DEFAULT_ASSIGN_HIGH,
    DEFAULT_ASSIGN_LOW,
    DEFAULT_ASSIGN_SECONDARY,
    assign_notes,
)
from kb_engine.topics.anchoring import reanchor_topics
from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.discover import build_topics
from kb_engine.topics.thresholds import derive_thresholds, persist_thresholds


@dataclass(frozen=True)
class WeeklyTopicsResult:
    reanchored: int
    thresholds_set: int
    assigned: int
    queued: int
    new_topics: int
    unfiled: int


def weekly_topic_pass(
    store: Store,
    clusterer: Clusterer,
    high: float = DEFAULT_ASSIGN_HIGH,
    secondary: float = DEFAULT_ASSIGN_SECONDARY,
    low: float = DEFAULT_ASSIGN_LOW,
) -> WeeklyTopicsResult:
    """One unattended weekly maintenance pass over the topic layer.

    Human-pinned notes (a ``source='user'`` primary anywhere) are excluded
    from auto-assignment entirely. Every active topic's auto members are
    replaced wholesale each pass — one primary per note per pass, no
    cross-run staleness. The residual (unassigned, non-borderline) is
    clustered into fresh ``discovered`` proposals exactly as before.
    """
    note_vectors = dict(store.note_vectors())
    if not note_vectors:
        return WeeklyTopicsResult(0, 0, 0, 0, 0, 0)

    reanchor_result = reanchor_topics(store)
    stats = derive_thresholds(store)
    persist_thresholds(store, stats)

    pinned = store.user_primary_paths()
    assignable_vectors = {
        path: vec for path, vec in note_vectors.items() if path not in pinned
    }
    active = [t for t in store.load_topics() if t.status == "active"]
    assigned, borderline = assign_notes(
        assignable_vectors, active, high=high, secondary=secondary, low=low
    )

    members_by_slug: dict[str, list[TopicMember]] = {}
    for note_path, assignments in assigned.items():
        for a in assignments:
            members_by_slug.setdefault(a.slug, []).append(
                TopicMember(
                    note_path=note_path,
                    score=a.score,
                    source="auto",
                    is_primary=a.is_primary,
                )
            )
    for topic in active:
        store.replace_auto_members(topic.slug, members_by_slug.get(topic.slug, []))

    store.replace_review_queue(
        [QueueEntry(path, candidates, "borderline") for path, candidates in borderline]
    )

    queued_paths = {path for path, _ in borderline}
    residual_paths = sorted(
        set(assignable_vectors) - set(assigned) - queued_paths
    )
    n_new_topics = 0
    n_unfiled = len(residual_paths)
    if residual_paths:
        residual_matrix = np.vstack([note_vectors[p] for p in residual_paths])
        labels = clusterer.cluster(residual_matrix)
        texts_by_path = store.note_texts()
        topics, new_members, unfiled = build_topics(
            residual_paths, residual_matrix, texts_by_path, labels
        )
        store.save_topics(topics, new_members)
        n_new_topics = len(topics)
        n_unfiled = len(unfiled)

    return WeeklyTopicsResult(
        reanchored=len(reanchor_result.reanchored),
        thresholds_set=len(stats),
        assigned=len(assigned),
        queued=len(borderline),
        new_topics=n_new_topics,
        unfiled=n_unfiled,
    )
```

Run: `uv run pytest tests/test_weekly.py -v` → PASS.

- [ ] **Step 3: Retire sticky + rewire pipeline (failing tests first).**
  In `tests/test_pipeline.py`: update line 15's
  `_WEEKLY_STEPS = ["import-mail", "enrich", "backfill", "sync", "apply-topics", "discover", "eval"]`
  to `["import-mail", "enrich", "backfill", "sync", "topics", "apply-topics", "eval"]`,
  and update the tests that reference the `discover` step by name (e.g. line 72's
  `by_name["discover"].detail` → `by_name["topics"].detail` — the
  `"1 new topic(s)"` substring assertion still matches the new detail format).
  `FakeClusterer(labels=[...])` in those tests returns its labels verbatim, so
  keep each test's label list sized to the notes that will actually reach
  clustering (for corpora with no active topics that is ALL notes, unchanged).
  No new ordering test is needed: `test_pipeline_runs_steps_and_summarizes`
  already asserts `[o.name for o in res.outcomes] == _WEEKLY_STEPS` — the
  updated list IS the exact-sequence (and no-`discover`) assertion, and its
  `by_name["topics"].detail` check exercises the new step's detail format
  end-to-end.

Run first: `uv run pytest tests/test_pipeline.py -v` → FAILS (step still named
`discover`, wrong order).

Then in `pipeline.py`:
- Replace the sticky import with `from kb_engine.topics.weekly import weekly_topic_pass`.
- Replace `_discover_step` with:

```python
def _topics_step(cfg: Config, store: Store, clusterer: Clusterer) -> str:
    r = weekly_topic_pass(store, clusterer)
    return (
        f"{r.reanchored} reanchored · {r.thresholds_set} thresholds · "
        f"{r.assigned} assigned · {r.queued} queued · "
        f"{r.new_topics} new topic(s) · {r.unfiled} unfiled"
    )
```

- Weekly block becomes (topics before apply):

```python
    if tier == "weekly":
        _run_step("topics", lambda: _topics_step(cfg, store, clusterer), outcomes)
        _run_step("apply-topics", lambda: _apply_step(cfg, store), outcomes)
        _run_step("eval", lambda: _eval_step(cfg, store, embedder), outcomes)
```

- Update the module docstring's tier line to
  `weekly: import-mail → enrich → backfill → sync → topics → apply-topics → eval → digest`.
- Delete `src/kb_engine/topics/sticky.py` and `tests/test_sticky.py`
  (`git rm`). In `cli.py`: remove the `--sticky`/`--high` options and the sticky
  branch from `topics_discover` (plain re-cluster remains), remove the
  `sticky_discover` import; fix any `test_cli.py` tests that used `--sticky`
  (delete them — the behavior they covered lives in `test_weekly.py` now).

Run: `cd kb-engine && uv run pytest` → green.

- [ ] **Step 4: Digest queue section (failing test first).** Append to
  `tests/test_digest.py` (reuse its existing store/tmp helpers):

```python
def test_digest_renders_borderline_queue(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.replace_review_queue([
        QueueEntry("Knowledge/a.md", (("rust-learning", 0.52), ("rust-tooling", 0.47)),
                   "borderline"),
        QueueEntry("Knowledge/b.md", (("ui-design", 0.49),), "borderline"),
    ])
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "## Borderline queue" in text
    assert "- [ ] Decide 2 borderline assignment(s)" in text
    a = text.index("Knowledge/a.md")
    b = text.index("Knowledge/b.md")
    assert a < b  # best top-candidate first
    assert "rust-learning (0.52)" in text
    store.close()


def test_digest_no_queue_section_when_empty(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "Borderline queue" not in text
    store.close()
```

Implement in `digest.py`:
- Module constant `_MAX_QUEUE_LISTED = 10`.
- In `build_digest`, after loading topics/areas: `queue = store.load_review_queue()`.
- Summary block gains `f"- Borderline queue: {len(queue)}"` after the unfiled line.
- Checklist gains (before the nothing-to-review fallback):

```python
    if queue:
        checklist.append(
            f"- [ ] Decide {len(queue)} borderline assignment(s) (`/kb:review`)"
        )
```

- After the unfiled section:

```python
    if queue:
        lines.extend(["", "## Borderline queue", ""])
        for entry in queue[:_MAX_QUEUE_LISTED]:
            options = ", ".join(
                f"{slug} ({score:.2f})" for slug, score in entry.candidates
            )
            lines.append(f"- [[{entry.note_path}]] → {options}")
        if len(queue) > _MAX_QUEUE_LISTED:
            lines.append(f"- …and {len(queue) - _MAX_QUEUE_LISTED} more")
```

Run: `uv run pytest tests/test_digest.py -v` → PASS.

- [ ] **Step 5: pipeline `--json` queue count + nix nudge.**
  In `cli.py`, find the `pipeline` command's counts construction (it builds
  `{"inbox": ..., "proposals": ..., "unfiled": ...}` — added in P2.T4). Add
  `"queue": <len of store.load_review_queue())>` computed the same way/place the
  other counts are. Extend the existing pipeline-counts test in `test_cli.py`
  to assert the `queue` key exists (int ≥ 0).

  In `modules/home/dev/kb-engine.nix`, the nudge parse line becomes:

```nix
    n="$(printf '%s' "$out" | /usr/bin/python3 -c \
      'import json,sys; c=json.load(sys.stdin)["counts"]; print(c["inbox"]+c["proposals"]+c["unfiled"]+c.get("queue",0))' \
      2>/dev/null || echo "")"
```

  (`.get` keeps the runner tolerant of an older engine. Do NOT run `just switch`
  here — that's Task 9's live step.)

Run: `cd kb-engine && uv run pytest` → green.

- [ ] **Step 6: Commit**

```bash
git add -A kb-engine/src kb-engine/tests modules/home/dev/kb-engine.nix
git commit -m "feat(kb-engine): weekly topic pass replaces sticky — assign+queue+digest"
```

---

### Task 8: `topics confirm` + /kb:review queue workflow doc

**Files:**
- Modify: `kb-engine/src/kb_engine/store.py` (`clear_auto_primaries`)
- Modify: `kb-engine/src/kb_engine/cli.py` (`topics confirm`)
- Modify: `~/.claude/commands/kb/review.md` AND
  `chezmoi/private_dot_claude/commands/kb/review.md`
- Test: `tests/test_store.py` (append), `tests/test_cli.py` (append)

**Interfaces:**
- Produces: `Store.clear_auto_primaries(note_path: str) -> None` (deletes the
  note's `source='auto' AND is_primary=1` rows — a human decision supersedes
  them); CLI `kb-engine topics confirm SLUG NOTE_PATH [--json]` → writes a
  `source='user', is_primary=True` membership (score = the queue's score for that
  slug when present, else 1.0), clears auto primaries, removes the queue row.
  Errors (exit ≠ 0, clean message): unknown topic slug; note not in the store.
  Tag writing stays `topics apply`'s job (run it after a confirm batch).

- [ ] **Step 1: Failing store test** (append to `tests/test_store.py`):

```python
def test_clear_auto_primaries_leaves_user_and_secondaries(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(2, np.float32))
    store.add_manual_topic("t2", "T2", "d", np.ones(2, np.float32))
    store.set_members("t1", [TopicMember("n.md", 0.6, "auto", True)])
    store.set_members("t2", [
        TopicMember("n.md", 0.5, "auto", False),  # secondary survives
        TopicMember("other.md", 0.9, "user", True),
    ])
    store.clear_auto_primaries("n.md")
    assert store.topic_members("t1") == []
    t2 = {(m.note_path, m.source, m.is_primary) for m in store.topic_members("t2")}
    assert t2 == {("n.md", "auto", False), ("other.md", "user", True)}
    store.close()
```

- [ ] **Step 2: Implement `clear_auto_primaries`**:

```python
    def clear_auto_primaries(self, note_path: str) -> None:
        """Drop a note's auto primary rows — a human confirm supersedes them."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM topic_members "
                "WHERE note_path = ? AND source = 'auto' AND is_primary = 1",
                (note_path,),
            )
```

Run: `uv run pytest tests/test_store.py -v` → PASS.

- [ ] **Step 3: Failing CLI tests** (append to `tests/test_cli.py`):

```python
def test_topics_confirm_from_queue(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(4, np.float32))
    store.upsert_note("Knowledge/n.md", "N", "sha-n", [])
    store.replace_review_queue(
        [QueueEntry("Knowledge/n.md", (("t1", 0.52),), "borderline")]
    )
    store.close()
    r = _invoke(["--vault", str(tmp_path), "--db", str(db),
                 "topics", "confirm", "t1", "Knowledge/n.md", "--json"], monkeypatch)
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload == {
        "slug": "t1", "note": "Knowledge/n.md",
        "score": 0.52, "source": "user", "dequeued": True,
    }
    store = Store(db)
    store.init_schema()
    members = store.topic_members("t1")
    assert [(m.note_path, m.source, m.is_primary) for m in members] == [
        ("Knowledge/n.md", "user", True)
    ]
    assert store.load_review_queue() == []
    store.close()


def test_topics_confirm_unknown_slug_fails(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.upsert_note("Knowledge/n.md", "N", "sha-n", [])
    store.close()
    r = _invoke(["--vault", str(tmp_path), "--db", str(db),
                 "topics", "confirm", "nope", "Knowledge/n.md"], monkeypatch)
    assert r.exit_code != 0
    assert "no such topic" in r.output


def test_topics_confirm_unknown_note_fails(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(4, np.float32))
    store.close()
    r = _invoke(["--vault", str(tmp_path), "--db", str(db),
                 "topics", "confirm", "t1", "Knowledge/ghost.md"], monkeypatch)
    assert r.exit_code != 0
    assert "not in the index" in r.output
```

- [ ] **Step 4: Implement `topics confirm`** (in `cli.py` under `topics`;
  `TopicMember` is already imported there):

```python
@topics.command("confirm")
@click.argument("slug")
@click.argument("note_path")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_confirm(cfg: Config, slug: str, note_path: str, as_json: bool) -> None:
    """Confirm NOTE_PATH into topic SLUG as its human-decided primary.

    The /kb:review queue verb: writes a source='user' primary membership,
    clears any auto primaries for the note, and removes its queue row.
    Run `topics apply` afterwards to write the tag into the note."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        known = {t.slug for t in store.load_topics()}
        if slug not in known:
            raise click.ClickException(f"no such topic: {slug}")
        if store.note_sha(note_path) is None:
            raise click.ClickException(f"note not in the index: {note_path}")
        score = 1.0
        dequeued = False
        for entry in store.load_review_queue():
            if entry.note_path == note_path:
                score = next(
                    (s for cand, s in entry.candidates if cand == slug), 1.0
                )
                dequeued = True
                break
        store.clear_auto_primaries(note_path)
        store.set_members(
            slug,
            [TopicMember(note_path=note_path, score=score, source="user",
                         is_primary=True)],
        )
        store.remove_from_review_queue(note_path)
    finally:
        store.close()
    _emit(
        {"slug": slug, "note": note_path, "score": round(score, 6),
         "source": "user", "dequeued": dequeued},
        as_json,
        f"Confirmed {note_path} -> {slug} (score {score:.2f}).",
    )
```

Run: `uv run pytest tests/test_cli.py -v` → PASS.

- [ ] **Step 5: /kb:review queue workflow doc.** Add to BOTH review.md copies
  (live + chezmoi), as a numbered section after the proposals section (renumber
  consistently with the merge-flow section from Task 3):

```markdown
### N. Decide borderline assignments (when the digest lists a queue)

The weekly pass queues notes whose best topic score sits just under that topic's
bar — each is one human call the engine won't make alone.

For each `## Borderline queue` line (`[[note]] → topic-a (0.52), topic-b (0.48)`):
- **Agree with a candidate:** `kb-engine --vault "<Main>" topics confirm <slug> "<note path>"`
  — records a user-pinned primary (auto passes will never fight it).
- **None fit:** leave it. The queue is rewritten every weekly pass; if it keeps
  re-appearing, consider a new manual topic (`kb-engine topics add`).

After a confirm batch: `kb-engine --vault "<Main>" topics apply` writes the tags.
```

Verify twins: `diff ~/.claude/commands/kb/review.md chezmoi/private_dot_claude/commands/kb/review.md` → empty.

- [ ] **Step 6: Full suite + commit**

```bash
cd kb-engine && uv run pytest
git add kb-engine/src/kb_engine/store.py kb-engine/src/kb_engine/cli.py \
  kb-engine/tests/test_store.py kb-engine/tests/test_cli.py \
  chezmoi/private_dot_claude/commands/kb/review.md
git commit -m "feat(kb-engine): topics confirm — human queue decisions pin user primaries"
```

---

### Task 9: Live supervised pass + eval gate + phase exit (controller-led)

No implementer dispatch — the controller runs this against the live vault/DB,
exactly like P0.T4/P3.T8. Vault path always quoted.

- [ ] **Step 1: Probe-twin safety check.** For each expected path in
  `_system/probes.yaml`, verify no >0.97 twin outranks it in its probe query
  (script over `dedup-report --json` + probe list). If a probe would lose its
  hit to suppression: add the surviving twin to that probe's any-of `expected`
  list (vault edit, reported to user) BEFORE running eval.
- [ ] **Step 2: `just switch`** — activates the nix nudge change (Task 7).
- [ ] **Step 3: Live topic pass, staged:**
  - `kb-engine --vault "<Main>" topics reanchor --json` → expect ~24 reanchored.
  - `kb-engine --vault "<Main>" topics thresholds --dry-run` → save the table to
    the ledger dir (`.superpowers/sdd/phase4/live-thresholds.txt`); sanity: highs
    within [0.45, 0.85].
  - `kb-engine --vault "<Main>" topics thresholds` → persisted.
  - `kb-engine --vault "<Main>" pipeline --tier weekly --json` → full pass. Check:
    every step ok; `topics` line shows assigned ≥ 243 (current sticky coverage —
    the preserve-or-improve exit criterion), queued > 0 expected.
- [ ] **Step 4: Eval gate.** `kb-engine --vault "<Main>" eval` → recall@5 MUST be
  1.00 (8/8). MRR compared to 0.67 reference (report drift; recall is the gate).
- [ ] **Step 5: Coverage + tag-loss check.** `unfiled` count vs pre-pass (from the
  digest before/after); confirm no `topic/` tag was REMOVED from any note
  (`git -C "<Main>" diff` shows only additions in tags lines + digest + queue).
- [ ] **Step 6: Dedup report for the human.**
  `kb-engine --vault "<Main>" dedup-report` → save to
  `.superpowers/sdd/phase4/live-dedup-report.txt`; summarize pair count to the
  user (merges happen later via /kb:review at the user's pace — not automated).
- [ ] **Step 7: Vault commit** (tags + digest changed):
  `git -C "<Main>" add -A && git -C "<Main>" commit -m "phase 4: per-topic assignment + queue"`.
- [ ] **Step 8: Phase exit bookkeeping.** Ledger PHASE 4 EXIT entry (tasks,
  commits, live numbers, carried Minors); archive sdd artifacts to
  `.superpowers/sdd/phase4/`; ff `main`; report the phase-exit summary.

**Exit criteria (from the spec):** re-running assign preserves-or-improves coverage
(≥ 243 assigned) without manual tag loss; borderline queue populated + surfaced;
eval ≥ baseline (8/8); fixture-backed geometry tests green.
