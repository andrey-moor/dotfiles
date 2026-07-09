# KB Hardening Phase 5 — Areas → Topics Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One aboutness hierarchy — 9 seeded areas over topics. Every topic carries an
area; every note gets an `area/<slug>` tag; the two-level `Cat/Sub` taxonomy retires
through a human-approved disposition table; a flag-gated classifier (LLM + embedding
fallback) covers notes the mechanical migration can't.

**Architecture:** Evolves `kb-engine/` in place. New modules `topics/areas_registry.py`
(seeded registry + category map), `topics/migration.py` (proposal generator + parser),
`topics/classify.py` (flag-gated LLM + embedding fallback), `topics/cutover.py` (mass
retag engine). `topics/areas.py` (agglomerative grouping) RETIRES — areas are seeded,
not clustered (kills the perennial sklearn-gated "2 deselected"). One new `topics.area`
column. `render.py` regroups by registry areas. **Hard human gate:** ONE review session
approves `_system/migration-proposal.md` before the live cutover (Task 7).

**Tech Stack:** Python 3.12, click, sqlite3, numpy, httpx (llm.py), pytest, uv;
`vault.load_post`/`write_post_atomic` house I/O for every note write.

## Global Constraints

Every task implicitly includes these (from the spec / master plan):

- **Eval gate:** `kb-engine eval` recall@5 must not regress at any task or phase
  boundary. Baseline: 8/8 probes (recall 1.00; MRR ~0.66 watch item). Note: tags live
  only in frontmatter — retag touches neither `embedding_text` nor `fts_text` — so the
  gate is structurally safe here, but it is still checked at the boundary.
- **TDD:** test-first; suite green before each commit (`cd kb-engine && uv run pytest`).
  Current: 431 passed, 2 deselected (the 2 die with `topics/areas.py` in Task 1).
- **No LLM/API calls in unit tests:** `FakeLLM` / `FakeEmbedder` / `MockTransport`;
  real-model checks behind `KB_RUN_INTEGRATION=1`.
- **Decisions stay human-gated (D14):** the disposition table and topic→area map need
  the user's approval before any mass mutation. The signed-off exception: **area**
  auto-assign at high confidence with `area_provenance: auto`, digest-listed.
- **Dependency direction (D15):** LLM calls go through `llm.py` (direct Anthropic API);
  the engine works with no key — embedding-similarity fallback IS the no-LLM path.
- **Nothing lost:** no note deleted; taxonomy tags are dropped only by the approved
  dispositions; facet tags (`Reference`, `Tutorials`, `Inspiration`, `Tools`) and junk
  inline numeric tags are untouched; the vault git history is the revert path (commit
  before AND after cutover).
- **Vault writers use the house I/O** (`vault.load_post` + `vault.write_post_atomic`).
- **Frozen dataclasses / immutability**; functions ≤ 50 lines; `cli.py` remains the
  known >800-line exception (split scheduled Phase 6/T6.4).
- **Vault path:** `/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main`
  (always quote). **DB:** `~/.local/state/kb-engine/kb-engine.db` (`immutable=1` for
  ad-hoc reads).
- **Commit per task**, conventional commits, no attribution footer.
- **Doc twins:** `~/.claude/commands/kb/*.md` and `chezmoi/private_dot_claude/commands/kb/*.md`
  edited identically, verified byte-identical with `diff`.

## Plan-time live data (2026-07-09, post-Phase-4; 601 notes)

- **Tag census (from `notes.tags`):** 26 two-level tags in live use, ALL under the 9
  declared categories. Top: Dev/Tools 160, AI/Agents 139, AI/LLMs 104, AI/Prompting 39,
  Business/SaaS 34, Career/Growth 32, Business/Startups 28, Dev/Rust 27, AI/MLOps 21,
  Business/Marketing 16, Career/Interviews 12, Home/Improvement 10, Arch/Distributed 9,
  AI/RAG 8, Personal/Cooking 8, Personal/Photography 8, Arch/APIs 7, Dev/TypeScript 7,
  Infra/Kubernetes 6, Personal/Travel 6, Dev/Go 5, Infra/Networking 5, Home/Gear 4,
  Infra/GitOps 3, Dev/Nix 2, Personal/Fitness 2. Plus the single-level category tag
  `GameDev` (15). Facets: Reference 172, Tutorials 90, Tools 66, Inspiration 57. Junk
  numeric inline tags (`1`, `2`, `876`, …) exist — leave them alone.
- **Coverage:** 210 notes have no category tag; **80 have neither category tag nor any
  topic membership** — the classifier's mechanical-residual at cutover.
- **`_taxonomy.md`:** 9 categories (AI, Dev, Infra, Architecture→`Arch/`, GameDev,
  Business, Career, Home, Personal), a Cross-cutting Tags section, human governance
  tables (Proposals/Deprecated), and the `<!-- KB-PROPOSALS:START/END -->` splice block
  `render_topics` maintains.
- **`Knowledge/tags.base`:** 6 table views filtering `file.hasTag("AI")` etc. (Obsidian
  nested-tag match) — missing Infra/Arch/GameDev; regenerated with 9 `area/<slug>`
  views. `knowledge.base` unchanged.
- **Topics:** 24 manual/active (member-anchored, per-topic thresholds), 19 discovered
  proposals, 106-note review queue. All manual topics currently have NO area.
- **llm.py:** `LLM` Protocol `complete(system, user, max_tokens=1024) -> str`; `FakeLLM`
  records calls; `AnthropicLLM(model, api_key, transport)` accepts `httpx.MockTransport`.

## File structure

| File | Change |
|---|---|
| `kb-engine/src/kb_engine/topics/areas_registry.py` | new: `SEEDED_AREAS`, `CATEGORY_TO_AREA`, `seed_areas` |
| `kb-engine/src/kb_engine/topics/areas.py` + `tests/test_areas.py` | **delete** (agglomerative grouping retires) |
| `kb-engine/src/kb_engine/models.py` | `Topic.area: str \| None`; `Area.description` |
| `kb-engine/src/kb_engine/store.py` | `topics.area` column; `set_topic_area`; `load_areas`/`save_areas` repointed to registry+column |
| `kb-engine/src/kb_engine/topics/migration.py` | new: proposal generator + strict table parser |
| `kb-engine/src/kb_engine/topics/classify.py` | new: LLM area classifier + embedding fallback + queue annotation |
| `kb-engine/src/kb_engine/topics/cutover.py` | new: mass-retag engine (dry-run first-class) |
| `kb-engine/src/kb_engine/topics/apply.py` | primary topic's area → `area/<slug>` tag ownership |
| `kb-engine/src/kb_engine/topics/weekly.py` | queue annotation hook (flag-gated) |
| `kb-engine/src/kb_engine/pipeline.py` | weekly `areas` step (classifier mop-up) |
| `kb-engine/src/kb_engine/importing/digest.py` | area coverage line |
| `kb-engine/src/kb_engine/topics/render.py` | index by registry areas; per-area pages; unfiled-by-area; taxonomy v2 |
| `kb-engine/src/kb_engine/cli.py` | `topics seed-areas`, `topics set-area`, `topics propose-migration`, `topics migrate`; `topics areas` → registry view |
| `~/.claude/commands/kb/review.md` (+ chezmoi twin) | area spot-veto section |
| `<vault>/_system/migration-proposal.md` | generated for the human gate (Task 3 output, live) |

Execution note: Tasks 1→6 run subagent-driven without pause. The **human gate** sits
between Task 3's live artifact and Task 7 (live cutover): generate the proposal early,
let the user review while Tasks 4–6 build, block only Task 7 on approval.

---

### Task 1: Areas registry, `topic.area` column, agglomerative retirement

**Files:**
- Create: `kb-engine/src/kb_engine/topics/areas_registry.py`
- Delete: `kb-engine/src/kb_engine/topics/areas.py`, `kb-engine/tests/test_areas.py`
- Modify: `kb-engine/src/kb_engine/models.py`, `kb-engine/src/kb_engine/store.py`,
  `kb-engine/src/kb_engine/cli.py`
- Test: `kb-engine/tests/test_areas_registry.py` (new), `tests/test_store.py` (append),
  `tests/test_cli.py` (adjust `topics areas` + add `set-area`/`seed-areas`)

**Interfaces:**
- Produces:
  - `areas_registry.SEEDED_AREAS: tuple[Area, ...]` — the 9 areas, slugs:
    `ai, dev, infra, arch, gamedev, business, career, home, personal`, each with
    label + one-line description (topic_slugs empty — composed at read time).
  - `areas_registry.CATEGORY_TO_AREA: dict[str, str]` — `{"AI": "ai", "Dev": "dev",
    "Infra": "infra", "Arch": "arch", "GameDev": "gamedev", "Business": "business",
    "Career": "career", "Home": "home", "Personal": "personal"}`.
  - `areas_registry.seed_areas(store) -> int` — idempotent registry write.
  - `Topic.area: str | None = None` (LAST field, defaulted);
    `Area.description: str = ""` (defaulted, after `topic_slugs`).
  - `Store.set_topic_area(slug: str, area: str | None) -> None`;
    `topics.area TEXT` column (both `_SCHEMA` and `_ensure_column`);
    `load_topics`/`save_topics` carry it.
  - `Store.save_areas(areas)` now writes ONLY the registry rows (slug, label,
    description — `areas` table gains a `description` column via `_ensure_column`);
    it no longer touches `area_members` (table stays, orphaned, harmless).
  - `Store.load_areas()` composes `Area.topic_slugs` from `topics.area` (GROUP BY),
    ordered by slug — NOT from `area_members`.
- Consumers to fix in this task: `digest.py` uses only `len(areas)` (no change needed —
  verify); `render.py` uses `area.topic_slugs` (works unchanged against the new
  `load_areas`); `cli.py topics areas` currently calls the agglomerative
  `build_areas` — becomes a pure registry listing.

- [ ] **Step 1: Write the failing registry tests** — `tests/test_areas_registry.py`:

```python
import numpy as np

from kb_engine.store import Store
from kb_engine.topics.areas_registry import (
    CATEGORY_TO_AREA,
    SEEDED_AREAS,
    seed_areas,
)


def test_seeded_areas_are_the_nine_spec_areas():
    assert [a.slug for a in SEEDED_AREAS] == [
        "ai", "dev", "infra", "arch", "gamedev",
        "business", "career", "home", "personal",
    ]
    assert all(a.label for a in SEEDED_AREAS)
    assert all(a.description for a in SEEDED_AREAS)
    assert all(a.topic_slugs == () for a in SEEDED_AREAS)


def test_category_map_covers_live_categories():
    assert CATEGORY_TO_AREA == {
        "AI": "ai", "Dev": "dev", "Infra": "infra", "Arch": "arch",
        "GameDev": "gamedev", "Business": "business", "Career": "career",
        "Home": "home", "Personal": "personal",
    }
    assert set(CATEGORY_TO_AREA.values()) == {a.slug for a in SEEDED_AREAS}


def test_seed_areas_idempotent_and_composed_membership(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    n = seed_areas(store)
    assert n == 9
    assert seed_areas(store) == 9  # idempotent re-run
    store.add_manual_topic("rust-learning", "Rust", "d", np.ones(4, np.float32))
    store.set_topic_area("rust-learning", "dev")
    areas = {a.slug: a for a in store.load_areas()}
    assert len(areas) == 9
    assert areas["dev"].topic_slugs == ("rust-learning",)
    assert areas["ai"].topic_slugs == ()
    assert areas["dev"].description
    store.close()
```

- [ ] **Step 2: Failing store tests** (append to `tests/test_store.py`):

```python
def test_topic_area_roundtrip_and_default_none(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(2, np.float32))
    assert store.load_topics()[0].area is None
    store.set_topic_area("t1", "dev")
    assert store.load_topics()[0].area == "dev"
    store.set_topic_area("t1", None)
    assert store.load_topics()[0].area is None
    store.close()
```

Run: `cd kb-engine && uv run pytest tests/test_areas_registry.py tests/test_store.py -v`
Expected: new tests FAIL (module/field missing).

- [ ] **Step 3: Implement models + store.**

`models.py`:
- `Area` gains `description: str = ""` (after `topic_slugs`).
- `Topic` gains `area: str | None = None  # registry area slug; None = unassigned`
  as the LAST field.

`store.py`:
- `_SCHEMA`: topics table gains `area TEXT`; areas table becomes
  `slug TEXT PRIMARY KEY, label TEXT, description TEXT`.
- `init_schema` gains:

```python
        # Backfill for databases created before the areas→topics hierarchy (Phase 5).
        self._ensure_column("topics", "area", "TEXT")
        self._ensure_column("areas", "description", "TEXT")
```

- `load_topics` SELECT + constructor gain `area` (append at end, keyword-constructed
  as Task 5 of Phase 4 left it); `save_topics` INSERT carries `topic.area`.
- New method:

```python
    def set_topic_area(self, slug: str, area: str | None) -> None:
        """Assign a topic to a registry area (None clears it)."""
        with self._conn:
            self._conn.execute(
                "UPDATE topics SET area = ? WHERE slug = ?", (area, slug)
            )
```

- `save_areas` becomes registry-only (docstring updated accordingly):

```python
    def save_areas(self, areas: list[Area]) -> None:
        """Replace the areas REGISTRY (slug/label/description rows).

        Membership is not stored here: an area's topics are composed at read
        time from ``topics.area``. The legacy ``area_members`` table is no
        longer written (kept for old DBs; harmless)."""
        with self._conn:
            self._conn.execute("DELETE FROM areas")
            for area in areas:
                self._conn.execute(
                    "INSERT INTO areas(slug, label, description) VALUES(?, ?, ?)",
                    (area.slug, area.label, area.description),
                )
```

- `load_areas` composes membership from `topics.area`:

```python
    def load_areas(self) -> list[Area]:
        by_area: dict[str, list[str]] = {}
        for slug, area in self._conn.execute(
            "SELECT slug, area FROM topics WHERE area IS NOT NULL ORDER BY slug"
        ):
            by_area.setdefault(area, []).append(slug)
        rows = self._conn.execute(
            "SELECT slug, label, description FROM areas ORDER BY slug"
        ).fetchall()
        return [
            Area(
                slug=slug,
                label=label,
                topic_slugs=tuple(by_area.get(slug, [])),
                description=description or "",
            )
            for slug, label, description in rows
        ]
```

- [ ] **Step 4: Implement `topics/areas_registry.py`:**

```python
"""The seeded areas registry — the coarse tier of the one aboutness hierarchy.

Nine areas seeded from the taxonomy's categories (spec §6 Phase 5). Areas are
DECLARED, not discovered: the old agglomerative grouping (topics/areas.py)
retired with this module's arrival. ``CATEGORY_TO_AREA`` maps the legacy
two-level tag categories onto area slugs for the migration.
"""
from kb_engine.models import Area
from kb_engine.store import Store

SEEDED_AREAS: tuple[Area, ...] = (
    Area("ai", "AI", (), "LLMs, agents, RAG, prompting, MLOps"),
    Area("dev", "Dev", (), "Languages, developer tools, editors, Nix"),
    Area("infra", "Infra", (), "Kubernetes, GitOps, networking"),
    Area("arch", "Architecture", (), "Distributed systems, APIs, databases"),
    Area("gamedev", "GameDev", (), "Game development, pixel art, engines"),
    Area("business", "Business", (), "SaaS, marketing, startups, indie hacking"),
    Area("career", "Career", (), "Interviews, growth, leadership"),
    Area("home", "Home", (), "Improvement, organization, gear"),
    Area("personal", "Personal", (), "Fitness, travel, cooking, photography"),
)

CATEGORY_TO_AREA: dict[str, str] = {
    "AI": "ai",
    "Dev": "dev",
    "Infra": "infra",
    "Arch": "arch",
    "GameDev": "gamedev",
    "Business": "business",
    "Career": "career",
    "Home": "home",
    "Personal": "personal",
}


def seed_areas(store: Store) -> int:
    """Write the seeded registry (idempotent full replace). Returns row count."""
    store.save_areas(list(SEEDED_AREAS))
    return len(SEEDED_AREAS)
```

(If `Area` field order makes positional construction awkward, use keyword args in
`SEEDED_AREAS` — match the actual dataclass.)

Run: `uv run pytest tests/test_areas_registry.py tests/test_store.py -v` → PASS.

- [ ] **Step 5: Retire the agglomerative module + rewire the CLI.**
- `git rm kb-engine/src/kb_engine/topics/areas.py kb-engine/tests/test_areas.py`.
- `cli.py`: remove `from kb_engine.topics.areas import build_areas` and
  `DEFAULT_AREA_THRESHOLD`; rewrite `topics areas` as a registry listing (drop the
  `--threshold` option); add `seed-areas` and `set-area`:

```python
@topics.command("areas")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_areas(cfg: Config, as_json: bool) -> None:
    """List the areas registry with each area's member topics."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        areas = store.load_areas()
    finally:
        store.close()
    rows = [
        {
            "slug": a.slug, "label": a.label, "description": a.description,
            "topics": list(a.topic_slugs),
        }
        for a in areas
    ]
    if as_json:
        click.echo(json.dumps({"areas": rows}))
        return
    if not rows:
        click.echo("No areas. Run `kb-engine topics seed-areas` first.")
        return
    for row in rows:
        topics_list = ", ".join(row["topics"]) or "—"
        click.echo(f"{row['slug']:10} {row['label']:14} [{topics_list}]")


@topics.command("seed-areas")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_seed_areas(cfg: Config, as_json: bool) -> None:
    """Seed the 9-area registry (idempotent full replace)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        n = seed_areas(store)
    finally:
        store.close()
    _emit({"seeded": n}, as_json, f"Seeded {n} areas.")


@topics.command("set-area")
@click.argument("topic_slug")
@click.argument("area_slug")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_set_area(cfg: Config, topic_slug: str, area_slug: str, as_json: bool) -> None:
    """Assign TOPIC_SLUG to AREA_SLUG (both must exist)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        if topic_slug not in {t.slug for t in store.load_topics()}:
            raise click.ClickException(f"no such topic: {topic_slug}")
        if area_slug not in {a.slug for a in store.load_areas()}:
            raise click.ClickException(f"no such area: {area_slug} (seed-areas first?)")
        store.set_topic_area(topic_slug, area_slug)
    finally:
        store.close()
    _emit(
        {"topic": topic_slug, "area": area_slug},
        as_json,
        f"{topic_slug} -> {area_slug}",
    )
```

- `tests/test_cli.py`: DELETE any test driving the old agglomerative `topics areas`
  (grep for `areas`); ADD:

```python
def test_topics_seed_and_set_area(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    r = _invoke(["--vault", str(tmp_path), "--db", str(db), "topics", "seed-areas",
                 "--json"], monkeypatch)
    assert json.loads(r.output) == {"seeded": 9}
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(4, np.float32))
    store.close()
    r2 = _invoke(["--vault", str(tmp_path), "--db", str(db), "topics", "set-area",
                  "t1", "dev", "--json"], monkeypatch)
    assert r2.exit_code == 0
    r3 = _invoke(["--vault", str(tmp_path), "--db", str(db), "topics", "areas",
                  "--json"], monkeypatch)
    dev = [a for a in json.loads(r3.output)["areas"] if a["slug"] == "dev"][0]
    assert dev["topics"] == ["t1"]


def test_topics_set_area_unknown_area_fails(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(4, np.float32))
    store.close()
    r = _invoke(["--vault", str(tmp_path), "--db", str(db), "topics", "set-area",
                 "t1", "nope"], monkeypatch)
    assert r.exit_code != 0
    assert "no such area" in r.output
```

- Check `test_cli.py`/`test_digest.py`/`test_render.py` for anything relying on
  `area_members`-composed areas or `save_areas` writing memberships — update those
  seams to the new registry semantics (they should be few; the digest uses only
  counts).

- [ ] **Step 6: Full suite + commit** (the 2 sklearn deselections disappear):

```bash
cd kb-engine && uv run pytest
git add -A kb-engine modules 2>/dev/null; git add -A kb-engine
git commit -m "feat(kb-engine): seeded areas registry + topic.area — agglomerative areas retire"
```

---

### Task 2: Migration proposal generator + strict parser

**Files:**
- Create: `kb-engine/src/kb_engine/topics/migration.py`
- Modify: `kb-engine/src/kb_engine/cli.py` (`topics propose-migration`)
- Test: `kb-engine/tests/test_migration.py`, `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `CATEGORY_TO_AREA`, `SEEDED_AREAS` (T1), `store.notes_by_tag()`,
  `diff_taxonomy` + `parse_taxonomy_tags` (existing), `store.load_topics()` +
  `topic_members`.
- Produces (all in `topics/migration.py`):

```python
@dataclass(frozen=True)
class TagDisposition:
    tag: str                 # e.g. "AI/RAG" or "GameDev"
    count: int               # notes carrying it
    area: str                # implied area slug (from the category)
    best_topic: str | None   # highest-Jaccard aligned topic
    overlap: float           # that Jaccard (0.0 when none)
    decision: str            # "map:<slug>" | "topic:<slug>" | "area"

@dataclass(frozen=True)
class TopicArea:
    slug: str                # topic slug
    proposed_area: str       # area slug ("" when no evidence)
    evidence: str            # e.g. "18/23 member notes tagged AI/*"

@dataclass(frozen=True)
class MigrationProposal:
    topic_areas: tuple[TopicArea, ...]
    dispositions: tuple[TagDisposition, ...]

def build_migration_proposal(store: Store, declared_tags: set[str]) -> MigrationProposal
def render_migration_proposal(proposal: MigrationProposal) -> str   # the .md artifact
def parse_migration_proposal(text: str) -> MigrationProposal        # strict round-trip
```

- **Default-decision heuristics** (proposals only — the human gate corrects):
  `map:<best>` when `overlap >= 0.20`; else `topic:<slugified-tag>` when
  `count >= 8`; else `area`. Topic→area proposal = majority category among the
  topic's member notes' two-level tags (`GameDev` counts as category `GameDev`);
  ties broken by higher count then alphabetical; no categorized members →
  `proposed_area=""` (human fills).
- **Artifact format** (`render_migration_proposal`): a markdown doc with an
  instructions header and two strict pipe tables the human EDITS IN PLACE:

```markdown
# Taxonomy → Areas/Topics Migration Proposal

_Edit the **decision** / **area** columns, then approve. Valid decisions:_
_`map:<topic-slug>` (notes gain that topic tag), `topic:<new-slug>` (a new manual_
_topic is created from this tag), `area` (tag retires; notes keep just the area)._

## Topic → area

| topic | area | evidence |
|---|---|---|
| ai-agents | ai | 18/23 member notes tagged AI/* |

## Tag dispositions

| tag | count | area | best topic (jaccard) | decision |
|---|---|---|---|---|
| AI/RAG | 8 | ai | ai-memory-mcp (0.24) | map:ai-memory-mcp |
```

- `parse_migration_proposal` re-reads exactly this rendering (round-trip property:
  `parse(render(p)) == p` up to evidence text); it VALIDATES: decision grammar,
  known area slugs, `map:`-targets exist among topic slugs listed in the doc or
  store — a malformed cell raises `ValueError` naming the row. The parser is what
  the Task 5 cutover consumes, so the human's edits are machine-read with no
  side channel.

- [ ] **Step 1: Failing tests** — `tests/test_migration.py` (representative core;
  keep all):

```python
import numpy as np
import pytest

from kb_engine.models import TopicMember
from kb_engine.store import Store
from kb_engine.topics.areas_registry import seed_areas
from kb_engine.topics.migration import (
    MigrationProposal,
    TagDisposition,
    TopicArea,
    build_migration_proposal,
    parse_migration_proposal,
    render_migration_proposal,
)


def _seed(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    seed_areas(store)
    store.add_manual_topic("rust-learning", "Rust", "d", np.ones(4, np.float32))
    members = []
    for i in range(4):
        p = f"Knowledge/rust-{i}.md"
        store.upsert_note(p, p, f"sha-{i}", ["Dev/Rust", "Reference"])
        members.append(TopicMember(p, 0.8, "auto"))
    store.set_members("rust-learning", members)
    # an unaligned low-count tag
    store.upsert_note("Knowledge/fit.md", "fit", "sha-f", ["Personal/Fitness"])
    # an unaligned high-count tag (>= 8) that should propose a new topic
    for i in range(8):
        p = f"Knowledge/mkt-{i}.md"
        store.upsert_note(p, p, f"sha-m{i}", ["Business/Marketing"])
    return store


def test_build_proposal_decisions(tmp_path):
    store = _seed(tmp_path)
    declared = {"Dev/Rust", "Personal/Fitness", "Business/Marketing"}
    proposal = build_migration_proposal(store, declared)
    by_tag = {d.tag: d for d in proposal.dispositions}
    assert by_tag["Dev/Rust"].decision == "map:rust-learning"
    assert by_tag["Dev/Rust"].area == "dev"
    assert by_tag["Dev/Rust"].count == 4
    assert by_tag["Dev/Rust"].overlap == pytest.approx(1.0)
    assert by_tag["Personal/Fitness"].decision == "area"
    assert by_tag["Business/Marketing"].decision == "topic:business-marketing"
    topic_area = {t.slug: t for t in proposal.topic_areas}
    assert topic_area["rust-learning"].proposed_area == "dev"
    store.close()


def test_round_trip(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(
        store, {"Dev/Rust", "Personal/Fitness", "Business/Marketing"}
    )
    text = render_migration_proposal(proposal)
    parsed = parse_migration_proposal(text)
    assert [(t.slug, t.proposed_area) for t in parsed.topic_areas] == [
        (t.slug, t.proposed_area) for t in proposal.topic_areas
    ]
    assert [(d.tag, d.count, d.area, d.decision) for d in parsed.dispositions] == [
        (d.tag, d.count, d.area, d.decision) for d in proposal.dispositions
    ]


def test_parse_rejects_bad_decision(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace(
        "map:rust-learning", "yolo:whatever"
    )
    with pytest.raises(ValueError, match="Dev/Rust"):
        parse_migration_proposal(text)
    store.close()


def test_parse_rejects_unknown_area(tmp_path):
    store = _seed(tmp_path)
    proposal = build_migration_proposal(store, {"Dev/Rust"})
    text = render_migration_proposal(proposal).replace("| dev |", "| dve |", 1)
    with pytest.raises(ValueError):
        parse_migration_proposal(text)
    store.close()


def test_tag_with_unknown_category_is_skipped_with_note(tmp_path):
    """A two-level tag whose category isn't in CATEGORY_TO_AREA (shouldn't exist
    live, but defensive) is excluded from dispositions rather than crashing."""
    store = _seed(tmp_path)
    store.upsert_note("Knowledge/weird.md", "w", "sha-w", ["Weird/Thing"])
    proposal = build_migration_proposal(store, {"Dev/Rust", "Weird/Thing"})
    assert "Weird/Thing" not in {d.tag for d in proposal.dispositions}
    store.close()
```

Run: `uv run pytest tests/test_migration.py -v` → FAIL (module missing).

- [ ] **Step 2: Implement `topics/migration.py`.** Core logic (write the full module;
  key functions shown — the implementer completes the straightforward rendering /
  parsing following the exact formats above):

```python
"""Taxonomy→areas/topics migration proposal: generate, render, parse.

The proposal is a FILE the human edits (decisions stay human-gated, D14):
``render_migration_proposal`` writes strict pipe tables;
``parse_migration_proposal`` reads them back with validation. The cutover
engine consumes only the parsed, human-approved result.
"""
from dataclasses import dataclass

from kb_engine.store import Store
from kb_engine.topics.areas_registry import CATEGORY_TO_AREA, SEEDED_AREAS
from kb_engine.topics.labeling import slugify
from kb_engine.topics.taxonomy import diff_taxonomy

MAP_OVERLAP_MIN = 0.20
NEW_TOPIC_MIN_COUNT = 8
_VALID_AREAS = {a.slug for a in SEEDED_AREAS}


def _tag_category(tag: str) -> str:
    return tag.split("/", 1)[0]


def _implied_area(tag: str) -> str | None:
    return CATEGORY_TO_AREA.get(_tag_category(tag))


def _propose_decision(count: int, best: str | None, overlap: float, tag: str) -> str:
    if best is not None and overlap >= MAP_OVERLAP_MIN:
        return f"map:{best}"
    if count >= NEW_TOPIC_MIN_COUNT:
        return f"topic:{slugify(tag.replace('/', ' '))}"
    return "area"


def build_migration_proposal(store: Store, declared_tags: set[str]) -> MigrationProposal:
    notes_by_tag = store.notes_by_tag()
    # Category tags = declared two-level tags in live use + the single-level
    # category tag GameDev; junk/facet tags never enter.
    live_tags = {
        tag for tag in notes_by_tag
        if (("/" in tag and not tag.startswith(("topic/", "area/"))) or
            tag in CATEGORY_TO_AREA)
        and _implied_area(tag) is not None
        and (tag in declared_tags or tag in CATEGORY_TO_AREA)
    }
    topic_members = {
        t.slug: {m.note_path for m in store.topic_members(t.slug)}
        for t in store.load_topics()
    }
    diff = diff_taxonomy(
        {tag: notes_by_tag[tag] for tag in sorted(live_tags)}, topic_members
    )
    dispositions = []
    for tag in sorted(live_tags):
        ranked = diff.mapping.get(tag, [])
        best, overlap = (ranked[0] if ranked else (None, 0.0))
        count = len(notes_by_tag[tag])
        dispositions.append(
            TagDisposition(
                tag=tag, count=count, area=_implied_area(tag),
                best_topic=best, overlap=overlap,
                decision=_propose_decision(count, best, overlap, tag),
            )
        )
    topic_areas = _propose_topic_areas(store, notes_by_tag)
    return MigrationProposal(
        topic_areas=tuple(topic_areas), dispositions=tuple(dispositions)
    )
```

`_propose_topic_areas`: for each topic (sorted by slug), count member notes per
implied area (via each member note's two-level/category tags → `_implied_area`);
majority wins (ties: higher count first, then alphabetical); evidence string
`f"{top_count}/{n_members} member notes tagged {category}/*"`; no evidence →
`proposed_area=""`.

`render_migration_proposal` / `parse_migration_proposal`: exactly the artifact
format above. Parser rules: locate the two `## ` sections; parse pipe rows
(split on `|`, strip); skip the header/divider rows; validate decision grammar
(`^(map:[a-z0-9-]+|topic:[a-z0-9-]+|area)$`), area slugs ∈ `_VALID_AREAS` (empty
allowed in topic→area rows), count int. Any bad cell →
`ValueError(f"row {tag_or_slug!r}: ...")`.

Run: `uv run pytest tests/test_migration.py -v` → PASS.

- [ ] **Step 3: CLI `topics propose-migration` + test.** Failing test (append to
  `tests/test_cli.py`):

```python
def test_topics_propose_migration_writes_artifact(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    (tmp_path / "_system").mkdir()
    (tmp_path / "_system" / "_taxonomy.md").write_text(
        "# Tax\n\n## Categories\n\n- **Dev/Rust** — rust\n"
    )
    store = Store(db)
    store.init_schema()
    seed_areas(store)
    store.upsert_note("Knowledge/r.md", "r", "sha-r", ["Dev/Rust"])
    store.close()
    r = _invoke(["--vault", str(tmp_path), "--db", str(db), "topics",
                 "propose-migration", "--json"], monkeypatch)
    assert r.exit_code == 0
    payload = json.loads(r.output)
    artifact = tmp_path / "_system" / "migration-proposal.md"
    assert artifact.is_file()
    assert payload["path"].endswith("migration-proposal.md")
    assert payload["tags"] == 1
    text = artifact.read_text()
    assert "## Tag dispositions" in text and "Dev/Rust" in text
```

Implementation (cli.py, under `topics`; imports from `kb_engine.topics.migration`
and `parse_taxonomy_tags` already imported):

```python
@topics.command("propose-migration")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_propose_migration(cfg: Config, as_json: bool) -> None:
    """Generate _system/migration-proposal.md for the human review gate.

    Proposes per-tag dispositions + topic→area assignments. Edit the decision
    columns, then run `topics migrate --proposal <path>` (dry-run first)."""
    taxonomy_path = cfg.vault_path / "_system" / "_taxonomy.md"
    declared = parse_taxonomy_tags(taxonomy_path) if taxonomy_path.exists() else set()
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        proposal = build_migration_proposal(store, declared)
    finally:
        store.close()
    out_path = cfg.vault_path / "_system" / "migration-proposal.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_migration_proposal(proposal))
    _emit(
        {
            "path": str(out_path),
            "tags": len(proposal.dispositions),
            "topics": len(proposal.topic_areas),
        },
        as_json,
        f"Wrote {out_path} ({len(proposal.dispositions)} tags, "
        f"{len(proposal.topic_areas)} topic-area rows). Review + edit decisions.",
    )
```

- [ ] **Step 4: Full suite + commit**

```bash
cd kb-engine && uv run pytest
git add kb-engine/src/kb_engine/topics/migration.py kb-engine/src/kb_engine/cli.py \
  kb-engine/tests/test_migration.py kb-engine/tests/test_cli.py
git commit -m "feat(kb-engine): migration proposal generator + strict human-gate parser"
```

**Controller note (not an implementer step):** immediately after this task's review
closes, run LIVE: `kb-engine --vault "<Main>" topics propose-migration` and hand the
artifact path to the user — the human gate opens here and runs concurrently with
Tasks 3–6. Only Task 7 blocks on approval.

---

### Task 3: Classifier — `topics/classify.py`

**Files:**
- Create: `kb-engine/src/kb_engine/topics/classify.py`
- Test: `kb-engine/tests/test_classify.py`

**Interfaces:**
- Consumes: `llm.LLM` Protocol / `FakeLLM`; `store.note_vectors_for`;
  `Topic.centroid`/`area`; `SEEDED_AREAS`.
- Produces:

```python
AUTO_AREA_MIN_LLM_CONF = 0.8
AUTO_AREA_MIN_EMBED_COS = 0.55

@dataclass(frozen=True)
class AreaCandidate:
    slug: str
    confidence: float
    source: str  # "llm" | "embedding"

def area_centroids(store: Store) -> dict[str, np.ndarray]
    # {area_slug: unit mean of that area's topic centroids}; areas with no
    # topics are absent (they can't be embedding-matched).

def classify_area(
    note_text: str,
    note_vector: np.ndarray | None,
    areas: list[Area],
    centroids: dict[str, np.ndarray],
    llm: LLM | None,
) -> AreaCandidate | None
    # LLM path when llm is not None: strict-JSON prompt over the 9 areas
    # (slug + description); malformed/refusal/unknown-slug reply → fall
    # through to the embedding path (never crash). Embedding path when
    # note_vector is not None: best cosine vs centroids → AreaCandidate
    # (confidence = cosine, source "embedding"). Both unavailable → None.

def annotate_queue_reason(reason: str, pick: str, confidence: float) -> str
    # "borderline" -> "borderline; llm: rust-learning (0.85)"
```

- LLM prompt contract (system): "You assign one AREA to a note. Reply with ONLY
  a JSON object {\"area\": \"<slug>\", \"confidence\": 0.0-1.0}. Valid slugs:
  ai, dev, infra, arch, gamedev, business, career, home, personal." User content =
  the note text (title + summary + why) + the areas registry with descriptions.
  Reply parsing: `json.loads` the first `{...}` block; validate slug + clamp
  confidence to [0,1]; ANY failure → embedding fallback.

- [ ] **Step 1: Failing tests** — `tests/test_classify.py`:

```python
import json

import numpy as np

from kb_engine.llm import FakeLLM
from kb_engine.models import Area
from kb_engine.store import Store
from kb_engine.topics.areas_registry import SEEDED_AREAS, seed_areas
from kb_engine.topics.classify import (
    AreaCandidate,
    annotate_queue_reason,
    area_centroids,
    classify_area,
)


def _areas():
    return list(SEEDED_AREAS)


def test_llm_path_valid_json():
    llm = FakeLLM(reply='{"area": "dev", "confidence": 0.9}')
    got = classify_area("Rust ownership notes", None, _areas(), {}, llm)
    assert got == AreaCandidate("dev", 0.9, "llm")
    system, user = llm.calls[0]
    assert "ONLY a JSON object" in system
    assert "Rust ownership notes" in user
    assert "gamedev" in system  # slug vocabulary is in the prompt


def test_llm_garbage_falls_back_to_embedding(real_vectors):
    llm = FakeLLM(reply="I cannot classify this note.")
    members = real_vectors.by_group("topic:")[:2]
    centroid = np.mean([v for _, v in members], axis=0)
    centroid = centroid / np.linalg.norm(centroid)
    got = classify_area(
        "whatever", members[0][1], _areas(), {"ai": centroid}, llm
    )
    assert got is not None
    assert got.source == "embedding"
    assert got.slug == "ai"
    assert 0.0 < got.confidence <= 1.0


def test_llm_unknown_slug_falls_back():
    llm = FakeLLM(reply='{"area": "nonsense", "confidence": 0.99}')
    got = classify_area("x", None, _areas(), {}, llm)
    assert got is None  # no vector either -> nothing


def test_no_llm_no_vector_returns_none():
    assert classify_area("x", None, _areas(), {}, None) is None


def test_area_centroids_unit_mean(tmp_path, real_vectors):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    seed_areas(store)
    members = real_vectors.by_group("topic:")[:2]
    for i, (path, vec) in enumerate(members):
        slug = f"t{i}"
        store.add_manual_topic(slug, slug, "d", vec)
        store.set_topic_area(slug, "ai")
    cents = area_centroids(store)
    assert set(cents) == {"ai"}
    expected = np.mean([v for _, v in members], axis=0)
    expected = expected / np.linalg.norm(expected)
    assert np.allclose(cents["ai"], expected, atol=1e-6)
    assert abs(float(np.linalg.norm(cents["ai"])) - 1.0) < 1e-5
    store.close()


def test_annotate_queue_reason():
    assert annotate_queue_reason("borderline", "rust-learning", 0.85) == (
        "borderline; llm: rust-learning (0.85)"
    )
```

Run: `uv run pytest tests/test_classify.py -v` → FAIL.

- [ ] **Step 2: Implement `topics/classify.py`** per the interface block (complete
  module; the JSON-extraction helper takes the first `{`…`}` span, json.loads it,
  validates; keep every function ≤ 50 lines). The embedding path: normalize the
  note vector (zero-norm guard → None), best cosine over `centroids`, return
  `AreaCandidate(best_slug, cosine, "embedding")`.

Run: `uv run pytest tests/test_classify.py -v` → PASS.

- [ ] **Step 3: Full suite + commit**

```bash
cd kb-engine && uv run pytest
git add kb-engine/src/kb_engine/topics/classify.py kb-engine/tests/test_classify.py
git commit -m "feat(kb-engine): area classifier — flag-gated LLM with embedding fallback"
```

---

### Task 4: Area flow — apply owns topicked notes' area tags; weekly mop-up step; digest line

**Files:**
- Modify: `kb-engine/src/kb_engine/topics/apply.py`, `topics/weekly.py`,
  `pipeline.py`, `importing/digest.py`
- Modify: `~/.claude/commands/kb/review.md` + chezmoi twin (spot-veto section)
- Test: `tests/test_apply.py`, `tests/test_weekly.py`, `tests/test_pipeline.py`,
  `tests/test_digest.py` (append each)

**Interfaces & semantics:**
- **apply** (`apply_topic_tags`): notes with a primary topic whose `Topic.area` is
  set get exactly ONE `area/<slug>` tag matching the primary's area — added if
  absent, and any OTHER stale `area/*` tags on such notes are removed (apply owns
  area vocabulary for topicked notes; this is the single sanctioned tag-removal,
  scoped to `area/*` only). Notes whose primary topic has no area: untouched.
- **weekly mop-up** (new pipeline step `areas`, weekly tier, AFTER `apply-topics`):
  `assign_areas(cfg, store, llm_or_none, limit=50) -> AreaAssignStats` in
  `topics/classify.py` — targets notes with NO topic membership AND no `area/*`
  tag (from `store.notes_by_tag()` + `notes_without_topic()`); for each (up to
  `limit`, sorted paths): `classify_area(...)` with the note's stored vector; when
  candidate clears its bar (`llm ≥ 0.8` / `embedding ≥ 0.55`) → write `area/<slug>`
  tag + frontmatter `area_provenance: auto` via house I/O. Returns counts
  (`assigned`, `skipped_low_confidence`, `no_signal`). No key → LLM None →
  embedding-only (still runs — the fallback IS the no-LLM path).
- **weekly queue annotation** (in `weekly_topic_pass`, flag-gated): when
  `ANTHROPIC_API_KEY` is set, annotate each queue entry's reason via
  `annotate_queue_reason` using an LLM choose-among-candidates call; without the
  key the reason stays "borderline". Implemented as a hook the pipeline passes in
  (keep `weekly_topic_pass` LLM-free by default: new optional param
  `annotate: Callable[[str, tuple], str] | None = None` — the pipeline supplies a
  closure when the key exists).
- **digest**: Summary gains `- Notes with area: {n}/{total}` (derived from
  `notes_by_tag`: count of notes carrying any `area/*` tag). `## Auto-assigned
  areas` is NOT a digest section (YAGNI) — spot-veto goes through /kb:review doc:
  a short section explaining `area_provenance: auto` and how to veto (delete the
  tag + provenance line; apply/mop-up won't re-add against a human edit… note:
  mop-up WILL retry a vetoed topicless note next week — the doc says: to veto
  permanently, set the correct `area/<slug>` yourself).
- **pipeline step detail** (this is the spec's "digest-listed for spot-veto" —
  assigned paths surface in the digest's Status section): `AreaAssignStats` carries
  `assigned_paths: tuple[tuple[str, str], ...]` ((path, area), capped at
  the limit) and the detail string includes up to 5:
  `f"{s.assigned} areas assigned · {s.skipped_low_confidence} low-conf · {s.no_signal} no-signal"`
  plus, when any assigned: `" — " + ", ".join(f"{p}→{a}" for p, a in s.assigned_paths[:5])`
  (+ `" …"` when more).

- [ ] **Step 1: Failing apply tests** (append to `tests/test_apply.py`): a note
  gaining `area/dev` when its primary topic has area "dev"; a stale `area/ai` tag
  on the same note removed; a note whose primary topic has NO area untouched; area
  tag not duplicated on re-run (idempotent). Use the existing `_apply_to_note` /
  `apply_topic_tags` test patterns — pass area via seeded topics in a tmp Store.
  Write the four tests concretely against the current file's helpers (read it
  first); each asserts on the note's rewritten tags list.
- [ ] **Step 2: Implement the apply change.** `_slugs_to_add_by_note` and
  `_primary_by_note` already exist; add `_area_by_note(store, only_status)`
  (primary topic's `Topic.area`); extend `_apply_to_note(note_path, slugs,
  primary_slug, area_slug)`: after topic-tag logic, when `area_slug` is not None —
  compute `wanted = f"area/{area_slug}"`; new tags = existing minus other
  `area/*` plus `wanted` (order preserved: replace in place when an `area/*` tag
  exists, else append); `changed` accounts for area edits. Keep the function
  ≤ 50 lines (extract an `_with_area_tag(tags, area_slug) -> list[str]` helper).
  Run apply tests → PASS.
- [ ] **Step 3: Failing mop-up tests** (append to `tests/test_classify.py` — the
  stats function lives in classify.py): tmp vault + store; one topicless note
  with a stored vector near a seeded area centroid (reuse `real_vectors`) gets
  `area/<slug>` + `area_provenance: auto` written (embedding path, no LLM); one
  below 0.55 → skipped_low_confidence; one with no vector → no_signal; a note
  that ALREADY has an `area/*` tag is not a target; `limit` respected. Assert
  file contents via re-read (house I/O produces parseable frontmatter).
- [ ] **Step 4: Implement `assign_areas` in classify.py** (uses `vault.load_post`
  /`write_post_atomic`; paths resolved under the vault with the same
  outside-vault guard pattern as apply.py). Run → PASS.
- [ ] **Step 5: Pipeline + weekly + digest wiring (failing tests first).**
  - `test_pipeline.py`: `_WEEKLY_STEPS` gains `"areas"` after `"apply-topics"`
    (before `"eval"`); the summarize test's `by_name["areas"]` detail asserted.
  - `test_weekly.py`: with `annotate=lambda reason, cands: reason + "; llm: x (0.9)"`,
    queue entries' reason carries the annotation; default None → plain
    "borderline".
  - `test_digest.py`: Summary shows `- Notes with area: 1/2` given one tagged note.
  - Implement: pipeline `_areas_step` (LLM built only when key set — mirror
    `_enrich_step`'s lazy import pattern; embedding fallback always available);
    weekly’s optional `annotate` param threaded from pipeline;
    digest counts `area/*` from `store.notes_by_tag()`.
- [ ] **Step 6: /kb:review spot-veto doc** (both copies, next numbered section):
  what `area_provenance: auto` means, veto = replace with your own `area/<slug>`
  (a bare delete gets re-proposed next weekly run). Verify twins with `diff`.
- [ ] **Step 7: Full suite + commit**

```bash
cd kb-engine && uv run pytest
git add -A kb-engine chezmoi/private_dot_claude/commands/kb/review.md
git commit -m "feat(kb-engine): area tags flow — apply ownership, weekly classifier mop-up, digest coverage"
```

---

### Task 5: Cutover engine — `topics/cutover.py` + `topics migrate`

**Files:**
- Create: `kb-engine/src/kb_engine/topics/cutover.py`
- Modify: `kb-engine/src/kb_engine/cli.py` (`topics migrate`)
- Test: `kb-engine/tests/test_cutover.py`, `tests/test_cli.py` (append)

**Interfaces:**
- Consumes: `parse_migration_proposal` (T2), `CATEGORY_TO_AREA` (T1), house I/O,
  `store.note_vectors_for`, `store.add_manual_topic` / `set_topic_area` /
  `set_members`.
- Produces:

```python
@dataclass(frozen=True)
class CutoverResult:
    notes_changed: int
    tags_dropped: int
    topic_tags_added: int
    area_tags_added: int
    topics_created: tuple[str, ...]
    skipped_unreadable: tuple[str, ...]
    diff_lines: tuple[str, ...]   # per-note "path: -Dev/Rust +topic/rust-learning +area/dev"

def apply_cutover(
    store: Store, vault_path: Path, proposal: MigrationProposal, dry_run: bool = True
) -> CutoverResult
```

**Cutover semantics (per note, driven by the APPROVED proposal):**
1. Topic→area rows: `store.set_topic_area(slug, area)` for every row with a
   non-empty area (dry-run: skipped; listed in diff_lines as `topic-area: slug -> area`).
2. `topic:<new-slug>` dispositions FIRST: create the manual topic
   (`add_manual_topic(new_slug, label=tag's subcategory title-cased, description=
   f"Migrated from tag {tag}", centroid=unit mean of the tag's notes' vectors —
   zero-vector fallback: skip creation, record in diff_lines)`, then
   `set_topic_area(new_slug, disposition.area)` and `set_members(new_slug,
   [TopicMember(path, cos(note, centroid), "auto", True)...])` for the tag's notes
   *that have no other primary* (is_primary=False otherwise). Skip creation if the
   slug already exists (idempotent re-run) — but still process its notes' tags.
3. Per note carrying any disposed tag (union over dispositions): build the new
   tags list —
   - drop every disposed two-level/category tag,
   - add `topic/<slug>` for each `map:`/`topic:` disposition among its dropped
     tags (no duplicates, order: existing tags order preserved, additions appended),
   - add exactly one `area/<slug>`: primary-topic's area when the note has a
     primary topic with an area; else majority implied area of its dropped tags
     (ties → the areas of the first tag in the note's original order); never a
     second `area/*` if one already exists (existing wins — apply/mop-up own
     ongoing correctness),
   - facet tags and everything else preserved.
4. Writes via `load_post`/`write_post_atomic`; unreadable → skipped_unreadable
   (never abort). `dry_run=True` computes everything incl. diff_lines, writes
   NOTHING (no store writes either).

- [ ] **Step 1: Failing tests** — `tests/test_cutover.py` covering: map disposition
  (tag dropped, topic tag + area tag added); topic: disposition (manual topic
  created w/ unit-norm centroid from the tag notes' vectors, members written,
  area set); area disposition (tag dropped, only area added); note with existing
  `area/*` keeps it; dry-run writes nothing (files byte-identical + store
  unchanged) yet reports the same counts/diff_lines as the real run; idempotent
  second apply (0 changes); facet + junk tags preserved; a `content: unavailable`
  note migrates (house I/O). Use `real_vectors` for the vectors; tmp vault files
  written with realistic frontmatter (tags list + summary + content: unavailable
  on one). Write all ~9 tests concretely.
- [ ] **Step 2: Implement `topics/cutover.py`** per the semantics block. Keep
  `apply_cutover` an orchestrator ≤ 50 lines delegating to `_create_new_topics`,
  `_note_tag_rewrite(tags, note_dispositions, primary_area) -> (new_tags, drops,
  adds)`, `_write_note(...)`. Run → PASS.
- [ ] **Step 3: CLI + test.**

```python
@topics.command("migrate")
@click.option(
    "--proposal",
    "proposal_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="The human-approved _system/migration-proposal.md.",
)
@click.option("--apply", "apply_changes", is_flag=True,
              help="Execute. Default is dry-run (prints the diff, writes nothing).")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_migrate(cfg, proposal_path, apply_changes, as_json):
    """Apply the approved taxonomy migration (dry-run by default)."""
    proposal = parse_migration_proposal(proposal_path.read_text())
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        result = apply_cutover(
            store, cfg.vault_path, proposal, dry_run=not apply_changes
        )
    finally:
        store.close()
    payload = {
        "dry_run": not apply_changes,
        "notes_changed": result.notes_changed,
        "tags_dropped": result.tags_dropped,
        "topic_tags_added": result.topic_tags_added,
        "area_tags_added": result.area_tags_added,
        "topics_created": list(result.topics_created),
        "skipped_unreadable": list(result.skipped_unreadable),
        "diff": list(result.diff_lines),
    }
    if as_json:
        click.echo(json.dumps(payload))
        return
    for line in result.diff_lines:
        click.echo(line)
    click.echo(
        f"{'DRY-RUN — nothing written' if not apply_changes else 'APPLIED'}: "
        f"{result.notes_changed} notes · {result.tags_dropped} tags dropped · "
        f"{result.topic_tags_added} topic tags · {result.area_tags_added} area tags · "
        f"{len(result.topics_created)} new topic(s)"
    )
```

(Wrap `parse_migration_proposal`'s `ValueError` in `click.ClickException` at the
top of the command so a malformed human edit prints the offending row cleanly.)

  Test: dry-run vs apply through the CLI on a 2-note tmp vault (parse errors from
  a corrupted proposal surface as ClickException — wrap the ValueError).
- [ ] **Step 4: Full suite + commit**

```bash
cd kb-engine && uv run pytest
git add kb-engine/src/kb_engine/topics/cutover.py kb-engine/src/kb_engine/cli.py \
  kb-engine/tests/test_cutover.py kb-engine/tests/test_cli.py
git commit -m "feat(kb-engine): taxonomy cutover engine — approved dispositions, dry-run first"
```

---

### Task 6: Rendered artifacts v2 — taxonomy registry, per-area pages, unfiled-by-area, tags.base

**Files:**
- Modify: `kb-engine/src/kb_engine/topics/render.py`
- Test: `kb-engine/tests/test_render.py` (extend)

**Interfaces & semantics:**
- `render.py` gains:
  - `_render_taxonomy_v2(areas, topics, members_by_slug) -> str` — the NEW
    generated `_taxonomy.md` body: frontmatter (`type: taxonomy, version:
    generated, status: active`), `# Knowledge Base Taxonomy`, an intro line
    ("One hierarchy: areas → topics. Tags: `area/<slug>`, `topic/<slug>`; facets
    combine freely."), `## Areas` (table: slug | label | description | topics
    count), `## Topics` (table: slug | label | area | kind/status | notes),
    `## Facets` (the four facet tags, hardcoded lines matching today's
    Cross-cutting section), then the existing `## Proposals` KB-PROPOSALS splice
    block (reuse `_splice_proposals` on the fresh body so `render_topics` keeps
    maintaining it).
  - `render_topics` writes taxonomy v2 INSTEAD of only splicing proposals — but
    ONLY when the registry is seeded (`store.load_areas()` non-empty); with no
    areas it behaves exactly as today (pre-cutover safety: rendering before the
    migration must not nuke the human taxonomy file).
  - Per-area pages `_system/topics/area-<slug>.md`: `# <label>`, description,
    `## Topics` (`- [[_system/topics/<slug>]] — label (n notes)`), rendered for
    every registry area (empty areas say `_None yet._`).
  - `index.md` groups by registry areas (it already iterates `load_areas()` —
    with T1's composed `topic_slugs` this works; extend each `## <label>` header
    to link the area page: `## [[_system/topics/area-<slug>|<label>]]`).
  - `_render_unfiled_by_category` → `_render_unfiled_by_area(by_note, tags_by_note)`:
    group topicless notes by their `area/*` tag (else "(no area)"); file renamed
    `_unfiled-by-area.md`; the old `_unfiled-by-category.md` is DELETED by
    `render_topics` when present (one-time cleanup, guarded `missing_ok`).
  - `tags.base` v2: `render_tags_base(areas) -> str` producing the 9-view YAML
    (view per area, filter `file.hasTag("area/<slug>")`, same order/sort columns
    as today's file); `render_topics` writes `Knowledge/tags.base` ONLY when
    areas are seeded. (Obsidian nested-tag note: `hasTag("area/ai")` matches the
    exact tag — our tags are exactly `area/ai`, no nesting below.)
- `RenderResult` gains `area_paths: tuple[str, ...] = ()` and
  `tags_base_path: str = ""` (defaulted — existing constructions stay valid).

- [ ] **Step 1: Failing render tests** (append to `tests/test_render.py`, reusing
  its store/tmp helpers — read first): seeded registry + 1 topic w/ area →
  taxonomy v2 contains the Areas table row and Topics row with area column;
  proposals block still present + spliced idempotently; area page file written
  with the topic line; index header links the area page; unfiled-by-area groups
  a topicless `area/dev`-tagged note under dev and an untagged one under
  "(no area)"; old `_unfiled-by-category.md` removed when present; `tags.base`
  written with 9 views incl. `file.hasTag("area/ai")`; **no areas seeded → old
  behavior: human taxonomy preserved, no tags.base write, no area pages**. Write
  each concretely.
- [ ] **Step 2: Implement.** Keep functions ≤ 50 lines; taxonomy v2 body built
  from small helpers. Run → PASS.
- [ ] **Step 3: Full suite + commit**

```bash
cd kb-engine && uv run pytest
git add kb-engine/src/kb_engine/topics/render.py kb-engine/tests/test_render.py
git commit -m "feat(kb-engine): render v2 — taxonomy registry, area pages, unfiled-by-area, tags.base"
```

---

### Task 7: HUMAN GATE + live cutover + phase exit (controller-led)

**Blocks on: the user's approved `_system/migration-proposal.md`** (generated live
after Task 2; the user edits decisions in place and says go). No implementer
subagents — controller runs everything, vault path always quoted.

- [ ] **Step 0 (gate):** user has reviewed/edited the proposal. Re-run
  `parse_migration_proposal` on the edited file (via a dry-run `topics migrate`)
  — a clean parse IS the approval artifact check; parse errors go back to the
  user with the row named.
- [ ] **Step 1: Pre-cutover safety.** Vault: `git add -A && git commit` ("pre
  phase-5 cutover"). Engine: seed live registry
  (`kb-engine ... topics seed-areas`).
- [ ] **Step 2: Dry-run.** `topics migrate --proposal "<vault>/_system/migration-proposal.md"`
  → save full diff output to `.superpowers/sdd/phase5/live-cutover-dryrun.txt`;
  sanity-scan (counts vs census; no facet drops; spot-check 5 diff lines) and
  show the user a summary. Proceed on their word in the same session (or
  explicitly granted earlier).
- [ ] **Step 3: Apply.** `topics migrate --proposal ... --apply` → counts recorded.
  Then `topics apply` (writes topic/area tags for existing members per T4's
  ownership), then `topics render` (taxonomy v2 + area pages + unfiled-by-area +
  tags.base).
- [ ] **Step 4: Residual areas.** `kb-engine pipeline --tier weekly` with secrets
  sourced (`set -a; . ~/.config/kb-engine/secrets.env; set +a`) so the `areas`
  mop-up step runs the classifier over the ~80 mechanical-residual notes (raise
  the limit for the one-shot: `assign_areas` limit is a pipeline default — run
  the step twice if the first pass reports a full batch). Record step details.
- [ ] **Step 5: Verification.**
  - `kb-engine eval` → recall@5 MUST be 1.00 (8/8).
  - Area coverage: digest `Notes with area: N/601` — report N (target: every
    non-inbox note; residual no-signal notes listed honestly).
  - No facet/junk tag lost: `git -C "<vault>" diff` — deletions only on disposed
    two-level tags + old unfiled-by-category file.
  - Doctor all-green; suite green.
- [ ] **Step 6: Post-cutover commit + exit.** Vault `git add -A && git commit`
  ("phase 5: areas→topics cutover"). Ledger PHASE 5 EXIT (tasks, commits, live
  numbers, carried Minors); artifacts → `.superpowers/sdd/phase5/`; ff `main`;
  memory update; phase-exit summary to the user.

**Exit criteria (spec):** every note has an area (report the honest count);
one aboutness vocabulary (two-level tags gone per dispositions); Bases + MOCs
browse by area/topic; eval ≥ baseline.
