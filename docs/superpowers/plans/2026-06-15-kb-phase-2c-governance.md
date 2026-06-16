# KB Phase 2c — Governance, Restructure-Diff & Write-Back Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development with TDD.

**Goal:** Make topics usable and governable: (1) **sticky re-discover** (assign to existing approved topics first, cluster only the residual for new proposals), (2) a **restructure-diff** that compares discovered topics against the existing `_system/_taxonomy.md`, (3) **render** topic/area MOC notes + `_taxonomy.md` proposals from the DB (render-not-append, idempotent), (4) a **gated `apply`** that writes approved topic tags into note frontmatter, and (5) **`kb` skill integration** so Claude drives discover→name→review→apply.

**Architecture:** Extends 2a/2b. Stickiness uses 2b's `assign_notes` to hold approved topics fixed, then runs the clusterer only on the residual (the practical sticky loop; semi-supervised y-label re-fit is a noted future enhancement, deferred per YAGNI). The engine writes vault files **directly** (files-as-truth): MOCs to `_system/topics/` (outside `Knowledge/`, so they're never embedded) and proposals into `_system/_taxonomy.md`, both rendered from the DB. `apply` writes tags into `Knowledge/*.md` frontmatter idempotently. The engine stays LLM-free; the `kb` skill (Claude) does pretty-naming + presents the diff + gates `apply`.

**Tech Stack:** unchanged. New file writes use `python-frontmatter` (already a dep) for safe frontmatter edits.

## Testing strategy
All deterministic (fake embedder/clusterer + tmp vaults). Render/apply tested by writing to a `tmp_path` vault and asserting file contents + idempotency. Coverage ≥80% on new modules.

## File structure (additions)
```
src/kb_engine/topics/
  sticky.py        # sticky_discover: assign-existing → cluster residual
  taxonomy.py      # parse _system/_taxonomy.md tags; diff_taxonomy
  render.py        # render MOCs (_system/topics/) + _taxonomy.md proposals
  apply.py         # write approved topic tags into note frontmatter (gated)
cli.py             # + topics discover --sticky, diff-taxonomy, render, apply
chezmoi/private_dot_claude/skills/kb/  # skill integration (2c Task 6)
```

---

### Task 1: Sticky re-discover

**Files:** `topics/sticky.py`, `topics/discover.py` (wire `--sticky`), `tests/test_sticky.py`

- [ ] **Step 1: Failing test** (fake clusterer)
```python
import numpy as np
from kb_engine.store import Store
from kb_engine.models import Topic, TopicMember
from kb_engine.topics.clustering import FakeClusterer
from kb_engine.topics.sticky import sticky_discover

def _seed_existing(s):
    # an approved manual topic anchored near [1,0,0]
    s.add_manual_topic("rust", "Rust", "rust", np.array([1,0,0],np.float32))

def test_sticky_keeps_existing_and_proposes_from_residual(tmp_path):
    s = Store(tmp_path/"t.db"); s.init_schema(); _seed_existing(s)
    # 3 notes: 2 near rust (assigned to existing), 1 elsewhere (residual→new cluster)
    vecs = {"Knowledge/a.md":[0.99,0.01,0],"Knowledge/b.md":[0.98,0,0.02],"Knowledge/c.md":[0,0,1]}
    for p,v in vecs.items():
        s.upsert_note(path=p,title=p,sha256="h",tags=[]); s.replace_chunks(p,[(0,p,np.array(v,np.float32))])
    # clusterer only ever sees the residual (1 note) — return single cluster label
    res = sticky_discover(s, FakeClusterer(labels=[0]), high=0.9)
    assert "rust" in {t.slug for t in s.load_topics()}        # existing preserved
    assert res.n_assigned_existing == 2                        # a,b → rust
    assert res.n_new_topics >= 0                                # c may form a new proposal or stay unfiled
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `sticky_discover(store, clusterer, high=0.55) -> StickyResult`:
  1. Load existing topics with `status in ('active','proposed')` that are `kind='manual'` OR previously-approved (for now: `kind='manual'` + any `status='active'`).
  2. `assign_notes(note_vectors, existing_topics, high=high, low=high)` → notes with score≥high are assigned to existing (write members via `set_members`); the rest are the **residual**.
  3. Run `clusterer.cluster(residual_matrix)` + `build_topics(residual...)` → new discovered proposals; `save_topics(new_discovered, members)` (preserves existing `manual`/`active`).
  4. Return `StickyResult(n_assigned_existing, n_new_topics, n_unfiled)`.
  Wire `discover --sticky` in the CLI to call this instead of plain `discover_topics`.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): sticky re-discover (assign existing, cluster residual)`

---

### Task 2: Taxonomy parse + restructure-diff

**Files:** `topics/taxonomy.py`, `tests/test_taxonomy.py`

- [ ] **Step 1: Failing tests**
```python
from kb_engine.topics.taxonomy import parse_taxonomy_tags, diff_taxonomy

def test_parse_taxonomy_tags(tmp_path):
    f = tmp_path/"_taxonomy.md"
    f.write_text("# Taxonomy\n## Categories\n- AI/RAG — retrieval\n- Dev/Rust — rust\n")
    tags = parse_taxonomy_tags(f)
    assert "AI/RAG" in tags and "Dev/Rust" in tags

def test_diff_taxonomy_maps_existing_to_topics():
    # existing tag -> set of note paths; topic -> member note paths
    existing = {"Dev/Rust": {"Knowledge/a.md","Knowledge/b.md"}, "AI/RAG": {"Knowledge/c.md"}}
    topic_members = {"rust-macros": {"Knowledge/a.md","Knowledge/b.md"}, "retrieval": {"Knowledge/c.md"}}
    d = diff_taxonomy(existing, topic_members)
    # Dev/Rust aligns with rust-macros; AI/RAG with retrieval
    assert d.mapping["Dev/Rust"][0][0] == "rust-macros"
    assert "rust-macros" in d.covered_topics
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `parse_taxonomy_tags(path) -> set[str]` (parse `Category/Sub` tokens from the taxonomy markdown lines; tolerate the real file's table/section format — match `\b[A-Z][A-Za-z]+/[A-Za-z]+\b` plus list-item `- Cat/Sub`). `diff_taxonomy(existing_tag_notes, topic_member_notes) -> TaxonomyDiff` with: `mapping` (per existing tag → ranked list of (topic_slug, jaccard overlap)), `covered_topics` (topics that align with some tag ≥ threshold), `new_topics` (topics with no aligned tag — "data found structure your taxonomy lacks"), `orphan_tags` (tags with no aligned topic). Pure set math (Jaccard).
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): taxonomy parse + restructure diff`

---

### Task 3: `diff-taxonomy` CLI

**Files:** `store.py` (helper `notes_by_tag()`), `cli.py`, `tests/test_cli.py`

- [ ] **Step 1: Failing test** — after sync+discover on a fake vault with frontmatter tags, `topics diff-taxonomy --json` returns mapping/new_topics/orphan_tags.
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `store.notes_by_tag() -> dict[str, set[str]]` (from notes.tags JSON). CLI `topics diff-taxonomy [--taxonomy PATH (default <vault>/_system/_taxonomy.md)] [--json]`: build `existing` from `parse_taxonomy_tags` ∩ `notes_by_tag`, `topic_members` from `load_topics`+`topic_members`, `diff_taxonomy`, report `{mapping, new_topics, orphan_tags}`. If the taxonomy file is missing, report `new_topics` = all topics (greenfield).
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): topics diff-taxonomy CLI`

---

### Task 4: Render MOCs + proposals (render-not-append)

**Files:** `topics/render.py`, `cli.py`, `tests/test_render.py`

- [ ] **Step 1: Failing tests** (write to tmp vault)
```python
def test_render_writes_topic_and_area_mocs_idempotently(tmp_path):
    # build a store with 2 topics + 1 area, then render twice → identical files
    ...
    from kb_engine.topics.render import render_topics
    out = render_topics(store, vault_path=tmp_path)
    moc = (tmp_path/"_system"/"topics"/"index.md").read_text()
    assert "rust" in moc.lower()
    before = (tmp_path/"_system"/"topics"/"index.md").read_text()
    render_topics(store, vault_path=tmp_path)
    assert (tmp_path/"_system"/"topics"/"index.md").read_text() == before   # idempotent
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `render_topics(store, vault_path) -> RenderResult`:
  - Write `<vault>/_system/topics/index.md` — an areas→topics outline with `[[_system/topics/<slug>]]` wikilinks, member counts, status. Frontmatter `type: system, generated: true`.
  - Write one MOC per topic `<vault>/_system/topics/<slug>.md` — label, keywords, `## Notes` listing member `[[Knowledge/...]]` wikilinks sorted by score, `kind`/`status`. Deterministic content (no timestamps in body → idempotent).
  - Render the **Proposals** section of `<vault>/_system/_taxonomy.md` between stable markers `<!-- KB-PROPOSALS:START -->`…`<!-- KB-PROPOSALS:END -->`: a table of `discovered` `status='proposed'` topics (slug, keywords, size). Replace only between markers (create the block if absent) — **render-not-append**, preserving the rest of the file.
  - CLI `topics render [--json]`. `_system/topics/` is outside `Knowledge/`, so sync never embeds these.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): render topic/area MOCs + taxonomy proposals`

---

### Task 5: Gated `apply` (tags → note frontmatter)

**Files:** `topics/apply.py`, `cli.py`, `tests/test_apply.py`

- [ ] **Step 1: Failing tests** (tmp vault)
```python
def test_apply_adds_topic_tag_to_member_notes(tmp_path):
    # a note file + a topic with that note as a high-score member, status approved
    ...
    from kb_engine.topics.apply import apply_topic_tags
    res = apply_topic_tags(store, vault_path=tmp_path, only_status=("active",))
    import frontmatter
    fm = frontmatter.load(tmp_path/"Knowledge"/"a.md")
    assert "topic/rust-macros" in fm["tags"]
    # idempotent: second apply doesn't duplicate
    apply_topic_tags(store, vault_path=tmp_path, only_status=("active",))
    fm2 = frontmatter.load(tmp_path/"Knowledge"/"a.md")
    assert fm2["tags"].count("topic/rust-macros") == 1
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `apply_topic_tags(store, vault_path, only_status=("active",)) -> ApplyResult`:
  - For each topic with `status in only_status`, for each member, load the note via `python-frontmatter`, add tag `topic/<slug>` to the `tags` list if absent (dedupe), write back (preserve body + other frontmatter). Count notes changed.
  - CLI `topics apply [--status active] [--json]` — **only writes with explicit invocation** (the command itself IS the gate; there is no implicit apply elsewhere). Default `--status active` so only approved topics apply (discovered proposals stay `proposed` until confirmed). Idempotent.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): gated apply of topic tags to notes`

---

### Task 6: `kb` skill integration

**Files:** `chezmoi/private_dot_claude/skills/kb/SKILL.md`, a new `chezmoi/private_dot_claude/commands/kb/topics.md`

- [ ] **Step 1:** Add a **Topics** operation to `SKILL.md` (operation 10) describing the engine-driven flow: `kb-engine sync` → `topics discover --sticky` (or `diff-taxonomy`) → Claude LLM-renames the keyword slugs into nice labels and proposes area names → present the restructure diff + proposals to the user → on approval, `topics render` + (gated) `topics apply`. Note the engine is LLM-free; Claude supplies naming + judgment; the engine does the deterministic compute + file writes.
- [ ] **Step 2:** Create `/kb:topics` command doc mirroring the operation (subcommands: `discover`, `diff`, `areas`, `add`, `render`, `apply`).
- [ ] **Step 3:** Deploy: `just chezmoi-apply` for the kb skill paths only (scoped, like Phase 0). Validate the command files exist under `~/.claude/`.
- [ ] **Step 4: Commit** `feat(kb): kb skill topics operation driving kb-engine`

---

### Task 7: Coverage + README + real e2e check

- [ ] **Step 1:** `uv run pytest --cov`; ≥80% on `sticky`, `taxonomy`, `render`, `apply`. Add edge tests: missing taxonomy file, render with zero topics, apply with note file missing on disk (skip + report), proposals-marker absent (block created).
- [ ] **Step 2:** README — document the full topic lifecycle + the `_system/topics/` MOC location + the `topic/<slug>` tag convention.
- [ ] **Step 3:** Run a real e2e against the actual vault (read-only-ish: render writes to `_system/topics/` which is safe/regenerable; do NOT run `apply` on the real vault in this task): `kb-engine --vault "<Main>" --db <tmp> sync && topics discover && topics render` then inspect `_system/topics/index.md`. Report what the real MOC looks like. (If unsure about writing into the real vault, render to a tmp copy.)
- [ ] **Step 4: Commit** `test(kb-engine): 2c coverage + README + e2e render`

## Self-review
- **Spec coverage (§5.3, §5.4):** fresh restructure proposal diffed vs existing taxonomy ✓ (T2,T3), sticky governance (assign-existing→residual) ✓ (T1), render-not-append MOCs + `_taxonomy.md` proposals ✓ (T4), gated apply (no silent note mutation) ✓ (T5), files-as-truth (MOCs in `_system/`, rebuildable; tags in notes) ✓, Claude-drives-naming via skill ✓ (T6). Deferred (noted, YAGNI): semi-supervised y-label re-clustering (the assign-existing→residual loop is the practical stickiness).
- **No placeholders / type consistency:** `sticky_discover`/`StickyResult`, `parse_taxonomy_tags`/`diff_taxonomy`/`TaxonomyDiff`, `render_topics`/`RenderResult`, `apply_topic_tags`/`ApplyResult`, `store.notes_by_tag` consistent across tasks.
- **Safety:** `apply` is the only note-mutating command and requires explicit invocation; render targets a regenerable `_system/` area excluded from embedding.
```
