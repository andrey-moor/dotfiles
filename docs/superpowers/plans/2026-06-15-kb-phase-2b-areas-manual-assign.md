# KB Phase 2b — Areas, Manual Topics & Assignment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development with TDD.

**Goal:** Build the three remaining "topic shape" capabilities on top of 2a's discovery: (1) group topics into **areas** via agglomerative clustering on centroids (tunable cut), (2) let the user **add manual topics** anchored by an embedding of their name+description (coexisting with discovered ones), and (3) **incrementally assign** notes to topics by cosine-to-centroid (high → auto-member, borderline → reported for review).

**Architecture:** Extends 2a. Areas use `sklearn.cluster.AgglomerativeClustering` on the topic centroid matrix — fully deterministic, so unit-tested directly (no integration gate). Manual topics reuse the Phase-1 `Embedder` (real jina or FakeEmbedder) to embed `label + " " + description` → centroid; `save_topics` already preserves `kind='manual'`. Assignment is pure numpy cosine over centroids. New CLI: `topics areas`, `topics add`, `topics list`, `topics assign`.

**Tech Stack:** unchanged (sklearn already in `[topics]`; embedder from `[ml]`). No new deps.

## Testing strategy
Everything here is deterministic (agglomerative clustering, cosine, FakeEmbedder) — so all of 2b is **unit-tested**, no new integration test needed. Coverage ≥80% on `areas`, `assignment`, and new store/CLI paths.

## File structure (additions)
```
src/kb_engine/
  models.py            # + Area
  store.py             # + area tables/CRUD; + add_manual_topic; + set_members
  topics/
    areas.py           # build_areas (agglomerative on centroids)
    assignment.py      # assign_notes (cosine → high/borderline)
    discover.py        # (unchanged)
  cli.py               # + topics areas / add / list / assign
tests/ test_areas.py test_assignment.py test_manual_topics.py (+ cli additions)
```

---

### Task 1: Area model + store tables

**Files:** `models.py`, `store.py`, `tests/test_areas.py`

- [ ] **Step 1: Failing test**
```python
import numpy as np
from kb_engine.store import Store
from kb_engine.models import Topic, Area

def _topic(slug):
    return Topic(slug=slug, label=slug, keywords=(), centroid=np.ones(4,np.float32),
                 kind="discovered", status="proposed")

def test_save_and_load_areas(tmp_path):
    s = Store(tmp_path/"t.db"); s.init_schema()
    s.save_topics([_topic("a"), _topic("b")], {"a": [], "b": []})
    s.save_areas([Area(slug="ai", label="AI", topic_slugs=("a","b"))])
    areas = s.load_areas()
    assert areas[0].slug == "ai" and set(areas[0].topic_slugs) == {"a","b"}

def test_save_areas_replaces_previous(tmp_path):
    s = Store(tmp_path/"t.db"); s.init_schema()
    s.save_topics([_topic("a")], {"a": []})
    s.save_areas([Area(slug="x", label="X", topic_slugs=("a",))])
    s.save_areas([Area(slug="y", label="Y", topic_slugs=("a",))])
    assert {a.slug for a in s.load_areas()} == {"y"}
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement.** `models.py`:
```python
@dataclass(frozen=True)
class Area:
    slug: str
    label: str
    topic_slugs: tuple[str, ...]
```
`store.py` schema: `areas(slug PK, label)` + `area_members(area_slug, topic_slug, PK(area_slug,topic_slug), FK→areas ON DELETE CASCADE)`. `save_areas(areas)` (txn: delete all areas+members, insert). `load_areas() -> list[Area]` (ORDER BY slug; topic_slugs sorted).
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): area model + store tables`

---

### Task 2: `build_areas` (agglomerative on centroids)

**Files:** `topics/areas.py`, `tests/test_areas.py`

- [ ] **Step 1: Failing test**
```python
import numpy as np
from kb_engine.models import Topic
from kb_engine.topics.areas import build_areas

def _t(slug, vec):
    return Topic(slug=slug, label=slug, keywords=(slug,), centroid=np.array(vec,np.float32),
                 kind="discovered", status="proposed")

def test_build_areas_groups_near_centroids():
    topics = [_t("rust1",[1,0,0]), _t("rust2",[0.95,0.05,0]), _t("llm",[0,0,1])]
    areas = build_areas(topics, distance_threshold=0.3)
    # the two rust topics share an area; llm is its own
    by_topic = {ts: a.slug for a in areas for ts in a.topic_slugs}
    assert by_topic["rust1"] == by_topic["rust2"] != by_topic["llm"]

def test_build_areas_single_topic_is_its_own_area():
    areas = build_areas([_t("solo",[1,0,0])], distance_threshold=0.3)
    assert len(areas) == 1 and areas[0].topic_slugs == ("solo",)

def test_build_areas_empty():
    assert build_areas([], distance_threshold=0.3) == []
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `build_areas(topics, distance_threshold) -> list[Area]`:
  - 0 topics → `[]`; 1 topic → one area containing it.
  - Else: stack centroids; `AgglomerativeClustering(n_clusters=None, distance_threshold=distance_threshold, metric="cosine", linkage="average")` → labels.
  - Group topics by label; per group, `slug` = slugify of the most common keyword across member topics (fallback `area-{i}`); `label` = `" / ".join(top member topic labels[:3])`; `topic_slugs` = sorted member slugs. Dedupe slugs with `-N`. Deterministic ordering (by group size desc).
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): build_areas via agglomerative clustering`

---

### Task 3: `topics areas` CLI

**Files:** `cli.py`, `tests/test_cli.py`

- [ ] **Step 1: Failing test** — after a fake-cluster discover, `topics areas --json` returns areas grouping the discovered topics.
```python
def test_topics_areas_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED","1"); monkeypatch.setenv("KB_FAKE_CLUSTER","0,0,1,1")
    v = tmp_path/"Knowledge"; v.mkdir(parents=True)
    for n,(t,b) in {"a.md":("A","rust macros"),"b.md":("B","rust borrow"),
                    "c.md":("C","llm prompt"),"d.md":("D","llm tokens")}.items():
        (v/n).write_text(f"---\ntitle: {t}\n---\n{b}")
    from click.testing import CliRunner; from kb_engine.cli import main; import json
    db = tmp_path/"t.db"; args=["--vault",str(tmp_path),"--db",str(db)]
    CliRunner().invoke(main, args+["sync"]); CliRunner().invoke(main, args+["topics","discover"])
    r = CliRunner().invoke(main, args+["topics","areas","--json"])
    assert r.exit_code == 0
    assert "areas" in json.loads(r.output)
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `topics areas [--threshold FLOAT (default 0.3)] [--json]`: load topics, `build_areas`, `save_areas`, report `{n_areas, areas:[{slug,label,topics:[slug...]}]}`. `init_schema()` first.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): topics areas CLI`

---

### Task 4: Manual topics (`topics add` + `topics list`)

**Files:** `store.py`, `cli.py`, `tests/test_manual_topics.py`

- [ ] **Step 1: Failing test**
```python
def test_topics_add_creates_manual_topic(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED","1")
    from click.testing import CliRunner; from kb_engine.cli import main; from kb_engine.store import Store
    db = tmp_path/"t.db"; args=["--vault",str(tmp_path),"--db",str(db)]
    r = CliRunner().invoke(main, args+["topics","add","my-topic","--label","My Topic",
                                       "--description","about rust filesystems"])
    assert r.exit_code == 0
    topics = {t.slug: t for t in Store(db).load_topics()}
    assert topics["my-topic"].kind == "manual" and topics["my-topic"].status == "active"
    assert topics["my-topic"].centroid.shape[0] > 0   # embedded the description

def test_manual_topic_survives_rediscover(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED","1")
    # add manual topic, then save_topics([discovered]) must NOT delete the manual one
    ...
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement.** `store.add_manual_topic(slug, label, description, centroid)` → insert a `kind='manual', status='active'` topic (reject if slug exists). CLI `topics add SLUG --label TEXT --description TEXT [--json]`: build embedder, `centroid = embedder.embed_query(f"{label}. {description}")`, store. Also add `topics list [--json]` → all topics with `{slug,label,kind,status,size}` (size from member count). Verify the manual topic survives a subsequent `topics discover` (save_topics only deletes `kind='discovered'`).
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): manual topics (add) + topics list`

---

### Task 5: Incremental assignment (`topics assign`)

**Files:** `topics/assignment.py`, `store.py`, `cli.py`, `tests/test_assignment.py`

- [ ] **Step 1: Failing tests**
```python
import numpy as np
from kb_engine.models import Topic
from kb_engine.topics.assignment import assign_notes

def _t(slug, vec):
    return Topic(slug=slug, label=slug, keywords=(), centroid=np.array(vec,np.float32),
                 kind="manual", status="active")

def test_assign_high_and_borderline():
    topics = [_t("rust",[1,0,0]), _t("llm",[0,0,1])]
    note_vecs = {"Knowledge/a.md": np.array([0.98,0.02,0],np.float32),    # clearly rust
                 "Knowledge/b.md": np.array([0.6,0.0,0.4],np.float32)}    # borderline rust
    assigned, borderline = assign_notes(note_vecs, topics, high=0.9, low=0.5)
    assert assigned["Knowledge/a.md"][0] == "rust"
    assert "Knowledge/b.md" in {p for p,_ in borderline}                  # between low and high

def test_assign_below_low_is_unassigned():
    topics = [_t("rust",[1,0,0])]
    assigned, borderline = assign_notes({"Knowledge/x.md": np.array([0,1,0],np.float32)},
                                        topics, high=0.9, low=0.5)
    assert assigned == {} and borderline == []
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `assign_notes(note_vectors, topics, high, low) -> (assigned, borderline)`:
  - For each note: best topic by cosine (note vec vs each centroid). `score ≥ high` → `assigned[path] = (slug, score)`; `low ≤ score < high` → `borderline.append((path, (slug, score)))`; `< low` → unassigned.
  - Deterministic; topics with zero-norm centroid skipped.
  - `store.set_members(slug, members)` to persist high-confidence members (source="auto") — additive to existing members (use INSERT OR REPLACE on the PK).
  - CLI `topics assign [--high 0.55] [--low 0.4] [--apply] [--json]`: compute over `store.note_vectors()` and `store.load_topics()` (active+proposed); `--json` reports `{assigned:[{note,topic,score}], borderline:[...], unassigned:N}`; with `--apply`, write high-confidence to `topic_members`. Without `--apply`, report only (dry-run default — engine never mutates membership silently).
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): incremental note→topic assignment`

---

### Task 6: Coverage + README

- [ ] **Step 1:** `uv run pytest --cov`; ≥80% on `areas`, `assignment`, new store/CLI. Add tests for: area dedupe-slug, assign tie-break determinism, `add` duplicate-slug rejection, `list` ordering (manual then discovered, or by size).
- [ ] **Step 2:** README — document `topics areas` / `add` / `list` / `assign` (note `assign` is dry-run unless `--apply`).
- [ ] **Step 3: Commit** `test(kb-engine): 2b coverage + README`

## Self-review
- **Spec coverage (§5):** areas via agglomerative-on-centroids ✓ (T2), tunable cut ✓ (`--threshold`), manual vector-anchored topics coexisting ✓ (T4), incremental cosine assignment high/borderline ✓ (T5), dry-run-by-default (no silent mutation) ✓. Restructure-diff + governance + MOC/`_taxonomy.md` write-back = **2c**.
- **No placeholders / type consistency:** `Area`, `build_areas`, `assign_notes`, `store.save_areas/load_areas/add_manual_topic/set_members` consistent across tasks.
- **Determinism:** all unit-tested; no new integration gate needed.
```
