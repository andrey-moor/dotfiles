# KB Phase 2a — Clustering & Topic Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development with TDD. Checkbox (`- [ ]`) steps.

**Goal:** Discover topics from the KB's embeddings — cluster note vectors (UMAP→HDBSCAN), compute a centroid + keyword label per topic, leave unclustered notes as an explicit "unfiled" set, persist topics in the store, and expose `kb-engine topics discover --json`.

**Architecture:** Extends the Phase 1 `kb-engine`. Per-note vectors (mean-pooled chunks) are clustered by an injectable `Clusterer` (real = UMAP→HDBSCAN, mirroring Orrery's proven pipeline; fake = deterministic, for unit tests). `build_topics` turns cluster labels into `Topic` objects (centroid = mean of members, label = top c-TF-IDF-style keywords). Topics + members persist in new SQLite tables. The engine stays **LLM-free**: labels are keyword slugs; nice human/LLM renaming happens later in the `kb` skill layer (Phase 2c). Clustering quality is proven by an integration test on well-separated fixtures; all surrounding logic is unit-tested with a `FakeClusterer`.

**Tech Stack:** Phase 1 stack + a new `[topics]` extra: `umap-learn>=0.5.5`, `hdbscan>=0.8.33`, `scikit-learn>=1.4.0`, `scipy>=1.11.0` (proven pins from orrery-engine). `numpy` already present.

---

## Testing strategy

- `Clusterer` is a Protocol (like `Embedder`). `FakeClusterer` returns caller-supplied labels — so `build_topics`, centroiding, keyword labeling, noise handling, and storage are all unit-tested deterministically with no UMAP/HDBSCAN.
- One integration test (`@pytest.mark.integration`, `KB_RUN_INTEGRATION=1`) runs the real `UmapHdbscanClusterer` over 3 well-separated synthetic vector groups and asserts it recovers ≥2 clusters with the right membership.
- Coverage ≥80% on new logic modules (`clustering`, the new store methods, `discover`).

## File structure (additions)

```
kb-engine/
├── pyproject.toml                       # add [topics] extra
└── src/kb_engine/
    ├── models.py                        # + Topic, TopicMember
    ├── store.py                         # + note_vectors(), + topic tables/CRUD
    └── topics/
        ├── __init__.py
        ├── clustering.py                # Clusterer protocol, FakeClusterer, UmapHdbscanClusterer
        ├── labeling.py                  # keyword labels (c-TF-IDF-ish) + slugify
        └── discover.py                  # orchestration: pool→cluster→build→store
└── tests/
    ├── test_topic_store.py
    ├── test_clustering.py
    ├── test_labeling.py
    ├── test_discover.py
    └── test_integration_clustering.py
```

---

### Task 1: `[topics]` extra + package skeleton

- [ ] **Step 1:** In `kb-engine/pyproject.toml`, add under `[project.optional-dependencies]`:
```toml
topics = [
    "umap-learn>=0.5.5",
    "hdbscan>=0.8.33",
    "scikit-learn>=1.4.0",
    "scipy>=1.11.0",
]
```
- [ ] **Step 2:** Create `src/kb_engine/topics/__init__.py` (empty).
- [ ] **Step 3:** `cd kb-engine && uv sync --extra dev` (no topics/ML install needed for unit tests). Verify `uv run pytest -q` still green (38 passed).
- [ ] **Step 4: Commit** `feat(kb-engine): add [topics] extra + topics package`

---

### Task 2: Topic models + note-vector pooling

**Files:** `src/kb_engine/models.py`, `src/kb_engine/store.py`, `tests/test_topic_store.py`

- [ ] **Step 1: Failing test** for `note_vectors` (mean-pool chunks per note)
```python
import numpy as np
from kb_engine.store import Store

def test_note_vectors_mean_pools_chunks(tmp_path):
    s = Store(tmp_path/"t.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h", tags=[])
    s.replace_chunks("Knowledge/a.md", [(0, "x", np.array([1,0,0,0], np.float32)),
                                        (1, "y", np.array([0,1,0,0], np.float32))])
    nv = dict((p, v) for p, v in s.note_vectors())
    assert nv["Knowledge/a.md"].shape == (4,)
    assert np.allclose(nv["Knowledge/a.md"], [0.5, 0.5, 0, 0])
```

- [ ] **Step 2: Failing test** for topic persistence
```python
import numpy as np
from kb_engine.store import Store
from kb_engine.models import Topic, TopicMember

def test_save_and_load_topics(tmp_path):
    s = Store(tmp_path/"t.db"); s.init_schema()
    t = Topic(slug="ai-agents", label="AI Agents", keywords=("agent","tool"),
              centroid=np.ones(4, np.float32), kind="discovered", status="proposed")
    s.save_topics([t], {"ai-agents": [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]})
    loaded = s.load_topics()
    assert loaded[0].slug == "ai-agents" and loaded[0].centroid.shape == (4,)
    mem = s.topic_members("ai-agents")
    assert mem[0].note_path == "Knowledge/a.md" and abs(mem[0].score-0.9) < 1e-6

def test_save_topics_replaces_previous_discovered(tmp_path):
    s = Store(tmp_path/"t.db"); s.init_schema()
    t1 = Topic(slug="old", label="Old", keywords=(), centroid=np.ones(4,np.float32), kind="discovered", status="proposed")
    s.save_topics([t1], {"old": []})
    t2 = Topic(slug="new", label="New", keywords=(), centroid=np.ones(4,np.float32), kind="discovered", status="proposed")
    s.save_topics([t2], {"new": []})              # discover re-run
    slugs = {t.slug for t in s.load_topics()}
    assert slugs == {"new"}                        # stale discovered topics cleared
```

- [ ] **Step 3: Run → fail.**

- [ ] **Step 4: Implement.** `models.py` add:
```python
@dataclass(frozen=True)
class Topic:
    slug: str
    label: str
    keywords: tuple[str, ...]
    centroid: "np.ndarray"     # float32, unit-normalized
    kind: str                  # "discovered" | "manual"
    status: str                # "proposed" | "active" | "deprecated"

@dataclass(frozen=True)
class TopicMember:
    note_path: str
    score: float               # cosine to centroid
    source: str                # "auto" | "seed" | "user"
```
`store.py` add schema:
```sql
CREATE TABLE IF NOT EXISTS topics (
  slug TEXT PRIMARY KEY, label TEXT, keywords TEXT, centroid BLOB NOT NULL,
  kind TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS topic_members (
  topic_slug TEXT NOT NULL, note_path TEXT NOT NULL, score REAL, source TEXT,
  PRIMARY KEY (topic_slug, note_path),
  FOREIGN KEY (topic_slug) REFERENCES topics(slug) ON DELETE CASCADE);
```
Methods: `note_vectors() -> Iterable[(path, ndarray)]` (mean of chunk vectors per note, via `iter_vectors`); `save_topics(topics, members_by_slug)` — within a txn, **delete existing `kind='discovered'` topics** (FK-cascades members) then insert the given ones (preserves any `kind='manual'` topics — added in 2b); `load_topics() -> list[Topic]`; `topic_members(slug) -> list[TopicMember]`. Keywords stored as JSON; centroid as float32 `.tobytes()`.

- [ ] **Step 5: Run → pass; commit** `feat(kb-engine): note-vector pooling + topic store tables`

---

### Task 3: Clusterer protocol + FakeClusterer

**Files:** `src/kb_engine/topics/clustering.py`, `tests/test_clustering.py`

- [ ] **Step 1: Failing test**
```python
import numpy as np
from kb_engine.topics.clustering import FakeClusterer

def test_fake_clusterer_returns_supplied_labels():
    c = FakeClusterer(labels=[0, 0, -1, 1])      # -1 = noise
    out = c.cluster(np.zeros((4, 8), np.float32))
    assert list(out) == [0, 0, -1, 1]
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** the protocol + fake (real impl is Task 6):
```python
from typing import Protocol
import numpy as np

class Clusterer(Protocol):
    def cluster(self, vectors: np.ndarray) -> np.ndarray:
        """Return an int label per row; -1 = noise/unclustered."""

class FakeClusterer:
    def __init__(self, labels: list[int]) -> None:
        self._labels = labels
    def cluster(self, vectors: np.ndarray) -> np.ndarray:
        return np.asarray(self._labels, dtype=int)
```

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): clusterer protocol + fake`

---

### Task 4: Keyword labeling

**Files:** `src/kb_engine/topics/labeling.py`, `tests/test_labeling.py`

- [ ] **Step 1: Failing tests**
```python
from kb_engine.topics.labeling import slugify, top_keywords

def test_slugify():
    assert slugify("AI Agents & Tools") == "ai-agents-tools"

def test_top_keywords_finds_distinctive_terms():
    docs_by_cluster = {0: ["rust macros borrow checker", "rust lifetimes borrow"],
                       1: ["prompt engineering llm", "llm prompting tokens"]}
    kw = top_keywords(docs_by_cluster, n=2)
    assert "rust" in kw[0] and "borrow" in kw[0]
    assert "llm" in kw[1] or "prompt" in kw[1]
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `slugify(text)` (lowercase, non-alnum→`-`, collapse, strip, max 60) and `top_keywords(docs_by_cluster, n)` — a simple c-TF-IDF: term freq within a cluster ÷ doc-freq across clusters; return top-n terms per cluster (lowercased, tokenized on `\w+`, drop a small English stopword set + tokens <3 chars). Returns `{cluster_id: tuple[str,...]}`.

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): keyword topic labeling (c-tf-idf)`

---

### Task 5: `build_topics`

**Files:** `src/kb_engine/topics/discover.py`, `tests/test_discover.py`

- [ ] **Step 1: Failing test** (deterministic via supplied labels)
```python
import numpy as np
from kb_engine.topics.discover import build_topics

def test_build_topics_centroids_labels_and_noise():
    paths = ["Knowledge/a.md","Knowledge/b.md","Knowledge/c.md"]
    vecs = np.array([[1,0],[0.9,0.1],[0,1]], np.float32)
    texts = {"Knowledge/a.md":"rust macros","Knowledge/b.md":"rust borrow","Knowledge/c.md":"llm prompt"}
    labels = np.array([0,0,-1])                   # c is noise
    topics, members, unfiled = build_topics(paths, vecs, texts, labels)
    assert len(topics) == 1                        # one real cluster (label 0)
    t = topics[0]
    assert t.centroid.shape == (2,) and np.linalg.norm(t.centroid) > 0
    assert "rust" in t.keywords
    assert {m.note_path for m in members[t.slug]} == {"Knowledge/a.md","Knowledge/b.md"}
    assert unfiled == ["Knowledge/c.md"]           # noise → unfiled
    # member score = cosine of note vec to centroid
    assert all(0.0 <= m.score <= 1.0001 for m in members[t.slug])
```

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `build_topics(paths, vectors, texts_by_path, labels) -> (topics, members_by_slug, unfiled)`:
  - Group note indices by label; label `-1` → `unfiled` (list of paths).
  - Per cluster: centroid = unit-normalized mean of member vectors; keywords via `labeling.top_keywords`; `label` = `" ".join(keywords[:3]).title()` (placeholder pretty name; LLM rename in 2c); `slug` = `slugify` of keywords (dedupe slugs with a numeric suffix); `kind="discovered"`, `status="proposed"`.
  - Per member: `score` = cosine(note_vec, centroid); `source="auto"`.
  - Deterministic ordering (sort clusters by size desc, then slug).

- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): build_topics (centroids, labels, members, unfiled)`

---

### Task 6: Real UMAP→HDBSCAN clusterer + integration test

**Files:** `src/kb_engine/topics/clustering.py` (extend), `tests/test_integration_clustering.py`

- [ ] **Step 1: Implement `UmapHdbscanClusterer`** (lazy imports inside `cluster`):
```python
class UmapHdbscanClusterer:
    def __init__(self, min_cluster_size: int | None = None, random_state: int = 42) -> None:
        self.min_cluster_size = min_cluster_size
        self.random_state = random_state
    def _adaptive(self, n: int) -> int:
        if self.min_cluster_size: return self.min_cluster_size
        if n < 100: return 2
        if n < 500: return 3
        return 5
    def cluster(self, vectors):
        import numpy as np, umap, hdbscan
        n = len(vectors)
        if n < 3:
            return np.full(n, -1, dtype=int)
        n_comp = min(5, n - 1)
        reduced = umap.UMAP(n_components=n_comp, metric="cosine",
                            random_state=self.random_state).fit_transform(vectors)
        labels = hdbscan.HDBSCAN(min_cluster_size=self._adaptive(n),
                                 cluster_selection_method="eom").fit_predict(reduced)
        return labels.astype(int)
```

- [ ] **Step 2: Integration test** (`tests/test_integration_clustering.py`, opt-in)
```python
import os, numpy as np, pytest
pytestmark = pytest.mark.integration

@pytest.mark.skipif(os.getenv("KB_RUN_INTEGRATION") != "1", reason="set KB_RUN_INTEGRATION=1")
def test_umap_hdbscan_recovers_separated_groups():
    from kb_engine.topics.clustering import UmapHdbscanClusterer
    rng = np.random.default_rng(0)
    groups = [rng.normal(c, 0.02, (12, 16)).astype(np.float32) for c in (-5, 0, 5)]
    vecs = np.vstack(groups)
    labels = UmapHdbscanClusterer(min_cluster_size=5).cluster(vecs)
    n_clusters = len({l for l in labels if l != -1})
    assert n_clusters >= 2                          # recovers the separation
```

- [ ] **Step 3: Run it for real**
```bash
cd kb-engine && uv sync --extra topics --extra dev
KB_RUN_INTEGRATION=1 uv run pytest tests/test_integration_clustering.py -m integration -v
```
Expected PASS (umap/hdbscan compile/install may take minutes on first run; if the env can't build them, report it — unit logic is fully covered regardless).

- [ ] **Step 4: Commit** `feat(kb-engine): umap→hdbscan clusterer + integration test`

---

### Task 7: `discover` orchestration + CLI

**Files:** `src/kb_engine/topics/discover.py` (extend), `src/kb_engine/cli.py`, `tests/test_discover.py`, `tests/test_cli.py`

- [ ] **Step 1: Failing test** for the orchestrator (fake clusterer)
```python
def test_discover_topics_stores_and_reports(tmp_path):
    from kb_engine.store import Store
    from kb_engine.topics.clustering import FakeClusterer
    from kb_engine.topics.discover import discover_topics
    import numpy as np
    s = Store(tmp_path/"t.db"); s.init_schema()
    for i, (p, txt) in enumerate([("Knowledge/a.md","rust macros"),("Knowledge/b.md","rust borrow"),("Knowledge/c.md","llm prompt")]):
        s.upsert_note(path=p, title=p, sha256="h", tags=[])
        v = np.eye(4, dtype=np.float32)[i % 4]
        s.replace_chunks(p, [(0, txt, v)])
    result = discover_topics(s, FakeClusterer(labels=[0,0,-1]))
    assert result.n_topics == 1 and result.n_unfiled == 1
    assert {t.slug for t in s.load_topics()} == {result.topics[0].slug}
```

- [ ] **Step 2: Failing CLI test**
```python
def test_topics_discover_cli_json(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED","1"); monkeypatch.setenv("KB_FAKE_CLUSTER","0,0,-1")
    v = tmp_path/"Knowledge"; v.mkdir(parents=True)
    for n,(t,b) in {"a.md":("Rust A","rust macros"),"b.md":("Rust B","rust borrow"),"c.md":("LLM","llm prompt")}.items():
        (v/n).write_text(f"---\ntitle: {t}\n---\n{b}")
    from click.testing import CliRunner; from kb_engine.cli import main; import json
    db = tmp_path/"t.db"
    CliRunner().invoke(main, ["--vault",str(tmp_path),"--db",str(db),"sync"])
    r = CliRunner().invoke(main, ["--vault",str(tmp_path),"--db",str(db),"topics","discover","--json"])
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert out["n_topics"] == 1 and out["n_unfiled"] == 1
```

- [ ] **Step 3: Run → fail.**

- [ ] **Step 4: Implement.** `discover_topics(store, clusterer) -> DiscoverResult`: read `store.note_vectors()` (sorted paths), stack into a matrix, `labels = clusterer.cluster(matrix)`, gather note texts (titles + first chunk text via a store helper `note_texts()`), `build_topics(...)`, `store.save_topics(...)`, return `DiscoverResult(topics, members, unfiled, n_topics, n_unfiled)` (frozen). CLI: add a `topics` group with a `discover` command; build the clusterer from env `KB_FAKE_CLUSTER` (comma ints → `FakeClusterer`) else `UmapHdbscanClusterer()`; `--json` prints `{n_topics, n_unfiled, topics:[{slug,label,keywords,size}]}`; human output lists topics + the unfiled count.

- [ ] **Step 5: Run → pass; commit** `feat(kb-engine): topics discover orchestration + CLI`

---

### Task 8: Coverage + README

- [ ] **Step 1:** `uv run pytest --cov --cov-report=term-missing`; ensure ≥80% on `clustering` (the fake+protocol+build paths), `labeling`, `discover`, and the new `store` topic methods. Add targeted tests for: all-noise corpus (0 topics, all unfiled), duplicate-slug suffixing, empty corpus.
- [ ] **Step 2:** README — add a "Topics" section: `kb-engine topics discover`, the `[topics]` extra, the LLM-free keyword-label note (pretty naming comes from the `kb` skill).
- [ ] **Step 3: Commit** `test(kb-engine): topics coverage >=80% + README`

---

## Self-review

- **Spec coverage (§5.1–§5.2):** clustering→topics ✓ (T6,T7), per-topic centroids ✓ (T5), keyword labels (LLM rename deferred to skill) ✓ (T4), explicit "unfiled" residual ✓ (T5), topic persistence ✓ (T2), `discovered` re-run clears stale proposals ✓ (T2). Areas, manual topics, incremental assignment = **2b**; restructure-diff, governance, MOC/`_taxonomy.md` write-back, `apply` = **2c**.
- **No placeholders:** schema, protocol, build_topics, real clusterer, and tests are concrete. 
- **Type consistency:** `Clusterer.cluster(vectors)->ndarray`, `Topic`/`TopicMember` fields, `store.note_vectors/save_topics/load_topics/topic_members/note_texts`, `DiscoverResult` used consistently T2–T7.
- **LLM-free engine** preserved — labels are deterministic keywords; testable without any model.
```
