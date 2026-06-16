# KB Phase 4 — Synthesis Re-activation & Proactive Surfacing Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development with TDD.

**Goal:** Close the loop on "get value out": (1) `synthesis-candidates` — list topics/tags with ≥N members and no wiki article, so synthesis stops going idle; (2) `related` — proactive surfacing: given a query or a note, return the most semantically relevant KB notes ("what's relevant to what I'm working on now"); (3) `kb` skill wiring so `/kb:synthesize` is topic-triggered and a new "surface" op answers relevance questions.

**Architecture:** Both engine commands reuse existing primitives — `synthesis-candidates` reads `load_topics`/`topic_members` + scans `Knowledge/wiki/`; `related` reuses `hybrid_search` (for `--query`) and stored note vectors (for `--to`). Small new surface, no new deps. The actual wiki *writing* stays in the `kb` skill (`/kb:synthesize`, already exists) — the engine just identifies candidates.

**Tech Stack:** unchanged.

## Testing strategy
All deterministic (fake embedder + seeded store + tmp vault). Coverage ≥80% on new code. Real validation runs both commands against the live KB (read-only).

## File structure (additions)
```
src/kb_engine/
  synthesis.py      # synthesis_candidates(store, vault, min_members)
  surface.py        # related_to_query / related_to_note (reuse search)
  cli.py            # + synthesis-candidates, + related
tests/ test_synthesis.py test_surface.py (+ cli)
```

---

### Task 1: `synthesis-candidates`

**Files:** `synthesis.py`, `cli.py`, `tests/test_synthesis.py`

- [ ] **Step 1: Failing tests**
```python
import numpy as np
from kb_engine.store import Store
from kb_engine.models import Topic, TopicMember
from kb_engine.synthesis import synthesis_candidates

def _topic(s, slug, n_members):
    t = Topic(slug=slug, label=slug, keywords=(slug,), centroid=np.ones(4,np.float32),
              kind="discovered", status="proposed")
    s.save_topics([t], {slug: [TopicMember(note_path=f"Knowledge/{slug}-{i}.md", score=0.9, source="auto")
                                for i in range(n_members)]})

def test_candidates_are_topics_over_threshold_without_wiki(tmp_path):
    (tmp_path/"Knowledge"/"wiki").mkdir(parents=True)
    s = Store(tmp_path/"t.db"); s.init_schema()
    # NOTE: save_topics replaces discovered each call, so seed in one call:
    big = Topic(slug="rag", label="RAG", keywords=("rag",), centroid=np.ones(4,np.float32), kind="discovered", status="proposed")
    small = Topic(slug="niche", label="Niche", keywords=("niche",), centroid=np.ones(4,np.float32), kind="discovered", status="proposed")
    s.save_topics([big, small], {"rag":[TopicMember(f"Knowledge/r{i}.md",0.9,"auto") for i in range(6)],
                                 "niche":[TopicMember("Knowledge/n.md",0.9,"auto")]})
    cands = synthesis_candidates(s, tmp_path, min_members=5)
    assert [c.slug for c in cands] == ["rag"]      # rag has 6, niche has 1

def test_existing_wiki_excludes_candidate(tmp_path):
    (tmp_path/"Knowledge"/"wiki").mkdir(parents=True)
    (tmp_path/"Knowledge"/"wiki"/"rag.md").write_text("---\ntype: wiki\n---\n# RAG")
    s = Store(tmp_path/"t.db"); s.init_schema()
    big = Topic(slug="rag", label="RAG", keywords=("rag",), centroid=np.ones(4,np.float32), kind="discovered", status="proposed")
    s.save_topics([big], {"rag":[TopicMember(f"Knowledge/r{i}.md",0.9,"auto") for i in range(6)]})
    assert synthesis_candidates(s, tmp_path, min_members=5) == []   # wiki/rag.md exists → excluded
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `synthesis_candidates(store, vault_path, min_members=5) -> list[Candidate]` where `Candidate(slug, label, size)` (frozen): for each topic with `len(members) >= min_members`, exclude if a wiki article exists at `Knowledge/wiki/<slug>.md` (or whose frontmatter `topic`/title matches the slug — keep it simple: filename match on slug). Sort by size desc. CLI `synthesis-candidates [--min 5] [--json]` → `{candidates:[{slug,label,size}]}`.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): synthesis-candidates command`

---

### Task 2: `related` (proactive surfacing)

**Files:** `surface.py`, `cli.py`, `tests/test_surface.py`

- [ ] **Step 1: Failing tests**
```python
def test_related_to_query_returns_relevant(tmp_path, monkeypatch):
    # seed store with notes; FakeEmbedder; related_to_query returns ranked notes
    ...
    from kb_engine.surface import related_to_query
    hits = related_to_query(store, embedder, "memory for agents", limit=3)
    assert hits and all(h.note_path.startswith("Knowledge/") for h in hits)

def test_related_to_note_excludes_self(tmp_path):
    from kb_engine.surface import related_to_note
    hits = related_to_note(store, "Knowledge/a.md", limit=3)
    assert "Knowledge/a.md" not in [h.note_path for h in hits]   # don't surface the note itself
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `related_to_query(store, embedder, query, limit=10)` → reuse `hybrid_search` (returns ranked `(path, score)` → `SurfaceHit(note_path, title, score)` resolving titles). `related_to_note(store, note_path, limit=10)` → take the note's mean vector (`note_vectors`), cosine vs all other note vectors, exclude self, top-N. CLI `related (--query TEXT | --to PATH) [--limit 10] [--json]` (exactly one of query/to required). `init_schema()` first.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): related/surface command`

---

### Task 3: `kb` skill wiring

**Files:** `chezmoi/private_dot_claude/skills/kb/SKILL.md`, `commands/kb/synthesize.md` (enhance), `commands/kb/surface.md` (new)

- [ ] **Step 1:** Enhance the **Synthesize** operation in `SKILL.md` + `synthesize.md`: before suggesting, run `kb-engine synthesis-candidates --json` and offer to compile wikis for topics ≥5 members with no article (in addition to the existing tag-based logic). Lower the suggestion threshold note to 5.
- [ ] **Step 2:** Add a **Surface** operation (op 12) to `SKILL.md` + a `/kb:surface` command: "given what I'm working on now (a description, project, or note), what's relevant?" → `kb-engine related --query "<context>"` (or `--to <note>`) → present ranked notes + offer to open/synthesize. Triggers: "what do I have related to X", "surface notes for my current project", "what's relevant to <note>".
- [ ] **Step 3:** Deploy scoped: `chezmoi apply ~/.claude/commands/kb ~/.claude/skills/kb`. Confirm `surface.md` landed.
- [ ] **Step 4: Commit** `feat(kb): synthesis-candidate + surface skill ops`

---

### Task 4: Coverage + README + real validation

- [ ] **Step 1:** `uv run pytest --cov`; ≥80% on `synthesis`/`surface`. Edge tests: no candidates, related with empty store, `--to` for a missing note.
- [ ] **Step 2:** README — "Synthesis candidates" + "Proactive surfacing (related)" sections.
- [ ] **Step 3:** Real validation against the live KB (read-only; engine cache DB already exists from Phase 3b):
  ```bash
  cd kb-engine && uv run kb-engine --vault "<Main>" synthesis-candidates --min 5 --json
  uv run kb-engine --vault "<Main>" related --query "long-term memory for AI agents" --limit 5 --json
  ```
  Report both outputs (expect ~7 synthesis candidates per the original review; related should surface the memory/agent notes).
- [ ] **Step 4: Commit** `test(kb-engine): phase 4 coverage + README + real validation`

## Self-review
- **Spec coverage (§6 surfacing, §8 synthesis):** synthesis triggers off topic size ≥5 ✓ (T1), proactive "what's relevant to now" ✓ (T2), skill wiring ✓ (T3). Both reuse existing search/topic primitives (KISS/YAGNI — no new infra).
- **No placeholders / type consistency:** `synthesis_candidates`/`Candidate`, `related_to_query`/`related_to_note`/`SurfaceHit` consistent.
- **Read-only:** neither command mutates the vault; real validation is safe.
```
