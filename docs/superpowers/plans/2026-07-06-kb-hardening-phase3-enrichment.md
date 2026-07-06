# KB Hardening Phase 3 — Enrichment + Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retrieval stops waiting for Monday — auto-drafted summaries/whys (flag-gated
Haiku), `why` threaded into vectors, inbox indexed, full content persisted + backfilled,
one supervised re-embed, and fresh-machine secrets provisioning.

**Architecture:** New `llm.py` (httpx Anthropic adapter + FakeLLM), `enrich.py`
(description drafting, provenance-marked), `extract.py` (shared trafilatura HTML→md,
refactored out of mail.py), `backfill.py` + CLI. `chunking.embedding_text` gains `why`;
sync indexes the inbox; pipeline tiers reorder so captures are enriched+indexed in the
same run. Secrets via `~/.config/kb-engine/secrets.env` sourced by the Nix runners.

**Tech Stack:** Python 3.12, httpx (already a dep via `[mail]` extra — MOVE to core deps
in T2), trafilatura (`[mail]` extra), click, pytest, nix-darwin home-manager.

## Global Constraints

All master-plan constraints apply. Phase-specific:

- **Eval gate:** `kb-engine eval` recall@5 = 1.00 (8/8) must hold at T5 exit (inbox
  indexing + why threading re-embed) and at T8 exit (full rebuild). A miss = STOP,
  controller adjudicates; never edit probes to pass.
- **Provenance rule (binding, from spec §3):** auto-written text always carries
  `provenance: auto` in frontmatter; a non-empty human field (no auto mark) is NEVER
  overwritten; `/kb:review` flips provenance to `confirmed` on touch.
- **Engine works without secrets:** no `ANTHROPIC_API_KEY` ⇒ enrich step reports
  `skipped: no ANTHROPIC_API_KEY`; no token ⇒ import-mail skips. Never crash.
- **No real API calls in tests:** `FakeLLM` + `httpx.MockTransport` only. Real LLM runs
  only in T8 (supervised, user present).
- **Timestamps:** never parse `runs` timestamps as RFC-3339 (space-separated SQLite UTC).
- **Pipeline step order after this phase:** daily = import-mail → enrich → sync → digest;
  weekly = import-mail → enrich → backfill → sync → apply-topics → discover → eval →
  digest. (Deliberate reorder of Phase 2's sync-first order so new captures are
  enriched and indexed in the same run; digest always last, always written.)

**Task order note:** master-plan skeleton items T3.6 (drain) and T3.7 (secrets) are
swapped here — provisioning must precede the live drain because enrichment needs the
real key. T8 is **user-gated**: it runs only after Andrey fills `secrets.env`.

---

### Task 1: Record the principle amendments (DECISIONS.md)

**Files:**
- Modify: `<vault>/_system/DECISIONS.md` (vault =
  `/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main`)

**Interfaces:** none (documentation of governance).

- [ ] **Step 1: Read the tail of `_system/DECISIONS.md`** to learn its numbering (13
  decisions, D1–D13 expected) and entry format. Mirror the format exactly.

- [ ] **Step 2: Append three decisions** (next numbers in sequence), content:

```markdown
## D14 — The invariant narrows to decisions (2026-07-06)
"The LLM proposes, never silently decides" governs decisions: topic/area membership,
filing, merges, taxonomy changes. Descriptions (summaries, proposed-why, title repair)
may be auto-drafted unattended — always `provenance: auto`, never overwriting human
text, flipped to `confirmed` when touched in review. Signed-off exception: AREA
assignment may auto-apply at high confidence (coarse, reversible), digest-listed for
spot-veto. Rationale: retrieval quality must not depend on ritual attendance; the
2026-07 review showed summary-starved vectors coupled retrieval to /kb:review.
Source: docs/superpowers/specs/2026-07-06-kb-hardening-design.md §3.

## D15 — Dependency direction is law (2026-07-06)
Interfaces (Claude Code, Cowork, future MCP) consume the engine; the loop completes
headless with the CLI alone. Cowork gets no load-bearing role. The cron LLM is a direct
Anthropic API call from the engine — not Cowork, not `claude` headless. Rationale:
session-authed surfaces are absent in cron; the KB must outlive interface churn.
Source: spec §3.

## D16 — No unverified health claims (2026-07-06)
Digest and `status` always carry last-run timestamp and result; stale or failed state
announces itself (digest Status header, doctor, skill preflight). Rationale: v1 and v2
both died silently behind stale-but-healthy-looking dashboards. Source: spec §3.
```

- [ ] **Step 3: Commit in the vault repo**

```bash
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
git -C "$VAULT" add _system/DECISIONS.md && git -C "$VAULT" commit -m "docs: D14-D16 — decisions-vs-descriptions, dependency direction, no unverified health"
```

---

### Task 2: LLM adapter (`llm.py`)

**Files:**
- Create: `kb-engine/src/kb_engine/llm.py`
- Modify: `kb-engine/src/kb_engine/config.py` (add `llm_model` field)
- Modify: `kb-engine/pyproject.toml` (+ `uv lock`): move `httpx` from the `[mail]` extra
  into core dependencies (llm.py + later backfill need it without the extra)
- Test: `kb-engine/tests/test_llm.py`

**Interfaces:**
- Produces (consumed by Tasks 3, 6 and Phase 5's classifier):
  - `class LLMUnavailable(RuntimeError)`
  - `LLM` Protocol: `complete(self, system: str, user: str, max_tokens: int = 1024) -> str`
  - `FakeLLM(reply: str = "fake summary.")` — records `.calls: list[tuple[str, str]]`
  - `AnthropicLLM(model: str = config default, api_key: str | None = None, transport=None)`
    — key from arg or `ANTHROPIC_API_KEY`; raises `LLMUnavailable` when absent
  - `Config.llm_model: str = "claude-haiku-4-5-20251001"`

- [ ] **Step 1: Write the failing tests**

Create `kb-engine/tests/test_llm.py`:

```python
import json

import httpx
import pytest

from kb_engine.llm import AnthropicLLM, FakeLLM, LLMUnavailable


def test_fake_llm_records_calls_and_replies():
    llm = FakeLLM(reply="a summary")
    out = llm.complete("sys", "user text")
    assert out == "a summary"
    assert llm.calls == [("sys", "user text")]


def test_anthropic_llm_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMUnavailable):
        AnthropicLLM()


def test_anthropic_llm_request_shape_and_text_extraction(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "first "},
                    {"type": "tool_use", "id": "x", "name": "n", "input": {}},
                    {"type": "text", "text": "second"},
                ]
            },
        )

    llm = AnthropicLLM(api_key="test-key", transport=httpx.MockTransport(handler))
    out = llm.complete("the system", "the user", max_tokens=99)
    assert out == "first second"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    p = captured["payload"]
    assert p["model"].startswith("claude-")
    assert p["max_tokens"] == 99
    assert p["system"] == "the system"
    assert p["messages"] == [{"role": "user", "content": "the user"}]


def test_anthropic_llm_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"type": "rate_limit_error"}})

    llm = AnthropicLLM(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        llm.complete("s", "u")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd /Users/andreym/Documents/dotfiles/kb-engine && uv run pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: kb_engine.llm` (after the pyproject move + `uv lock`
+ `uv sync` so httpx resolves in the base env).

- [ ] **Step 3: Implement `llm.py`**

```python
"""LLM adapter for descriptions: flag-gated, minimal, engine works without it.

Direct Anthropic Messages API via httpx (never Cowork/`claude` headless — D15).
Only descriptions flow through here; decisions stay human-gated (D14).
"""

import os
from typing import Protocol

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
REQUEST_TIMEOUT_S = 60.0


class LLMUnavailable(RuntimeError):
    """No API key configured — callers treat enrichment as skipped."""


class LLM(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str: ...


class FakeLLM:
    """Deterministic test double; records calls."""

    def __init__(self, reply: str = "fake summary.") -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        self.calls.append((system, user))
        return self.reply


class AnthropicLLM:
    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMUnavailable("ANTHROPIC_API_KEY not set")
        self.model = model
        self._client = httpx.Client(
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
            headers={"x-api-key": key, "anthropic-version": API_VERSION},
        )

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        resp = self._client.post(
            API_URL,
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        return "".join(
            b.get("text", "") for b in blocks if b.get("type") == "text"
        ).strip()
```

In `config.py`, add to the frozen `Config`: `llm_model: str = "claude-haiku-4-5-20251001"`
(constant `DEFAULT_LLM_MODEL` at module top, matching the file's style). `AnthropicLLM`
callers pass `model=cfg.llm_model`.

- [ ] **Step 4: Full suite** — `uv run pytest`; expect 361 passed (357+4), 2 deselected.
- [ ] **Step 5: Commit**

```bash
git add kb-engine/src/kb_engine/llm.py kb-engine/src/kb_engine/config.py kb-engine/pyproject.toml kb-engine/uv.lock kb-engine/tests/test_llm.py
git commit -m "feat(kb-engine): Anthropic LLM adapter (flag-gated, httpx, FakeLLM)"
```

---

### Task 3: Enrichment step (`enrich.py`) + pipeline reorder

**Files:**
- Create: `kb-engine/src/kb_engine/enrich.py`
- Modify: `kb-engine/src/kb_engine/pipeline.py` (new step + tier reorder)
- Modify: `kb-engine/src/kb_engine/cli.py` (pass an LLM factory / nothing — see below)
- Test: `kb-engine/tests/test_enrich.py`; update `tests/test_pipeline_hardening.py`
  step-order assertions

**Interfaces:**
- Produces:
  - `EnrichStats(summarized: int, whys: int, titles: int, skipped: int, failures: tuple[str, ...])` (frozen)
  - `enrich_notes(cfg: Config, llm: LLM, limit: int = 50) -> EnrichStats` — walks
    `Knowledge/` INCLUDING `inbox/` via `iter_notes`; selects notes with empty
    `summary`; drafts summary always, `why` only if empty, title only if slug-garbage;
    writes frontmatter with `provenance: auto` via python-frontmatter (preserving all
    other fields); NEVER touches a non-empty summary/why/title without an auto mark.
  - Pipeline step `enrich` in BOTH tiers, between import-mail and sync; without a key →
    `"skipped: no ANTHROPIC_API_KEY"`; detail on success:
    `"N summarized · N whys · N titles · N skipped · N failed"`.
- New tier orders (binding): daily = import-mail → enrich → sync;
  weekly = import-mail → enrich → backfill(T6) → sync → apply-topics → discover → eval.
  Digest last, always, unchanged.

**Prompts (module constants, verbatim):**

```python
SUMMARY_SYSTEM = (
    "You write 2-3 sentence factual summaries of saved web content for a personal "
    "knowledge base. Plain prose. No markdown, no preamble, no 'This article...'."
)
WHY_SYSTEM = (
    "Given a saved item, propose ONE short line (max 15 words) guessing why the owner "
    "saved it, grounded in the content and capture channel. Return only the line."
)
TITLE_SYSTEM = (
    "Repair this garbled machine slug into a clean human-readable title (max 80 "
    "chars). Return only the title."
)
```

**Selection + write rules (binding):**
- Candidate: `summary` frontmatter empty/missing. Skip notes whose body is empty AND
  title is not slug-garbage (nothing to summarize from) — count as skipped.
- Slug-garbage title heuristic: matches `re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+){2,}", t)`
  or `re.search(r"-status-\d+", t)` or `t.lower() in {"untitled", "(untitled)"}`.
- LLM user content: `f"Title: {title}\nChannel: {source} · {context}\nContent:\n{body[:6000]}"`.
- Writes: `summary=<draft>`, `why=<draft>` (only if empty), `title=<repair>` (only if
  garbage), plus `provenance: auto`. Use `frontmatter.loads/dumps` round-trip; body
  unchanged. Per-note LLM/HTTP errors → collect in `failures`, continue (never abort).
- `limit` bounds LLM-called notes per run (default 50).

- [ ] **Step 1: Write the failing tests**

Create `kb-engine/tests/test_enrich.py`:

```python
import frontmatter

from kb_engine.config import Config
from kb_engine.enrich import enrich_notes
from kb_engine.llm import FakeLLM


def _vault(tmp_path):
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    return Config(vault_path=tmp_path, db_path=tmp_path / "kb.db")


def _write(cfg, rel, text):
    p = cfg.vault_path / rel
    p.write_text(text)
    return p


def test_enriches_empty_summary_and_marks_provenance(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(cfg, "Knowledge/inbox/some-slug-thing-here.md",
               "---\ntitle: some-slug-thing-here\nsummary: ''\nwhy: ''\nsource: article\n---\nlong body text")
    stats = enrich_notes(cfg, FakeLLM(reply="drafted."))
    assert stats.summarized == 1 and stats.whys == 1 and stats.titles == 1
    post = frontmatter.loads(p.read_text())
    assert post["summary"] == "drafted."
    assert post["why"] == "drafted."
    assert post["title"] == "drafted."
    assert post["provenance"] == "auto"
    assert post.content.strip() == "long body text"


def test_never_overwrites_human_text(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(cfg, "Knowledge/filed.md",
               "---\ntitle: A Human Title\nsummary: human summary\nwhy: human why\n---\nbody")
    llm = FakeLLM()
    stats = enrich_notes(cfg, llm)
    assert stats.summarized == 0 and llm.calls == []
    post = frontmatter.loads(p.read_text())
    assert post["summary"] == "human summary" and "provenance" not in post.metadata


def test_partial_enrich_keeps_existing_why(tmp_path):
    cfg = _vault(tmp_path)
    p = _write(cfg, "Knowledge/n.md",
               "---\ntitle: Clean Title\nsummary: ''\nwhy: my own reason\n---\nbody")
    stats = enrich_notes(cfg, FakeLLM(reply="s."))
    assert stats.summarized == 1 and stats.whys == 0 and stats.titles == 0
    post = frontmatter.loads(p.read_text())
    assert post["why"] == "my own reason" and post["summary"] == "s."


def test_limit_bounds_llm_notes(tmp_path):
    cfg = _vault(tmp_path)
    for i in range(3):
        _write(cfg, f"Knowledge/n{i}.md", f"---\ntitle: T{i}\nsummary: ''\n---\nb{i}")
    stats = enrich_notes(cfg, FakeLLM(reply="s."), limit=2)
    assert stats.summarized == 2


def test_llm_failure_collected_not_raised(tmp_path):
    cfg = _vault(tmp_path)
    _write(cfg, "Knowledge/bad.md", "---\ntitle: T\nsummary: ''\n---\nbody")

    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("api down")

    stats = enrich_notes(cfg, Boom())
    assert stats.failures == ("Knowledge/bad.md",) and stats.summarized == 0
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_enrich.py -v`

- [ ] **Step 3: Implement `enrich.py`** per the interfaces/rules above (~120 lines).
  Structure: `_is_garbage_title(title)`, `_needs(note_post)`, `_draft(llm, system, user)`,
  main loop over `iter_notes(knowledge_dir, base=vault, exclude_dirs=())` (inbox
  INCLUDED — deliberate), stopping LLM calls at `limit`.

- [ ] **Step 4: Pipeline wiring + reorder**

In `pipeline.py`: add `_enrich_step(cfg)` —

```python
def _enrich_step(cfg: Config) -> str:
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "skipped: no ANTHROPIC_API_KEY"
    from kb_engine.enrich import enrich_notes
    from kb_engine.llm import AnthropicLLM

    s = enrich_notes(cfg, AnthropicLLM(model=cfg.llm_model))
    return (
        f"{s.summarized} summarized · {s.whys} whys · {s.titles} titles · "
        f"{s.skipped} skipped · {len(s.failures)} failed"
    )
```

Reorder both tiers: daily = import-mail → enrich → sync; weekly = import-mail → enrich →
sync → apply-topics → discover → eval (backfill slot arrives in T6). Update
`tests/test_pipeline_hardening.py` order assertions (daily names ==
`["import-mail", "enrich", "sync"]`, weekly == `["import-mail", "enrich", "sync",
"apply-topics", "discover", "eval"]`) and add `monkeypatch.delenv("ANTHROPIC_API_KEY")`
alongside the existing FASTMAIL delenv for hermeticity.

- [ ] **Step 5: Full suite** — expect ~366 passed. **Step 6: Commit**

```bash
git add kb-engine/src/kb_engine/enrich.py kb-engine/src/kb_engine/pipeline.py kb-engine/src/kb_engine/cli.py kb-engine/tests/
git commit -m "feat(kb-engine): auto-enrichment step (summaries/whys/titles, provenance-marked)"
```

---

### Task 4: `/kb:review` provenance flip + `/kb:process` content policy + lint rule (docs)

**Files (chezmoi source + live copy, byte-identical, targeted apply as in Phase 1/2):**
- Modify: `chezmoi/private_dot_claude/commands/kb/process.md` + live
- Modify: `chezmoi/private_dot_claude/commands/kb/review.md` + live
- Modify: `chezmoi/private_dot_claude/commands/kb/lint.md` + live

**Changes (keep each file's frontmatter; patch the procedure bodies):**

1. `process.md` — in the per-note processing steps, replace the summarize-then-
   write-summary-as-body behavior with:

```markdown
- **Content policy:** keep the fetched/clipped full readable text in the note under a
  `## Content` section, capped at 4,000 words with a truncation marker
  (`…truncated — full text at <url>`). The summary goes ONLY in frontmatter. Never
  replace the body with the summary. If the note already has auto-drafted frontmatter
  (`provenance: auto`), review the drafts: correcting or accepting them flips
  `provenance` to `confirmed`.
```

2. `review.md` — add one step to the review flow, after inbox processing:

```markdown
- **Provenance pass:** for notes touched this session with `provenance: auto`, confirm
  or correct the drafted summary/why/title, then set `provenance: confirmed`. Auto
  drafts are proposals, not truth (D14).
```

3. `lint.md` — add to the warnings list:

```markdown
- **W: summary-stub note** — body under ~500 chars, has a `url`, and no
  `content: unavailable` marker: candidate for `kb-engine backfill-content`.
- **W: stale auto-provenance** — `provenance: auto` older than 30 days (never
  confirmed): list for the next review pass.
```

- [ ] **Step 1: Apply the three patches** to chezmoi sources, copy to live (or targeted
  `chezmoi apply` on exactly those files), `diff` each pair for byte-identity.
- [ ] **Step 2: Commit** — `git add chezmoi/ && git commit -m "docs(kb): content policy in /kb:process, provenance flip in /kb:review, stub lint"`

---

### Task 5: Retrieval inputs — `why` threading + inbox indexing

**Files:**
- Modify: `kb-engine/src/kb_engine/chunking.py` (`embedding_text`)
- Modify: `kb-engine/src/kb_engine/sync.py` (EXCLUDED_DIRS)
- Modify: `kb-engine/src/kb_engine/search.py` (drop the inbox result filter)
- Test: `kb-engine/tests/test_chunking.py` (extend), `tests/test_sync.py` (flip the
  inbox-exclusion expectation), `tests/test_search.py` (inbox hits included)

**Interfaces / binding behavior:**
- `embedding_text(note)` = `title \n\n summary-or-body[:280] \n\n why-when-present`
  (why appended only when non-empty; exact composition below).
- Sync walks `Knowledge/` INCLUDING `inbox/` (`EXCLUDED_DIRS = ()`); inbox notes are
  embedded + FTS-indexed like any other. Rationale (plan-time resolution of spec's
  "findable within a day with zero human touch"): auto-filing is a gated decision, so
  findability must come from indexing the inbox; the old noise rationale is void now
  that inbox notes carry auto summaries. Consumers see `Knowledge/inbox/` in the path.
- `hybrid_search` keeps the `Knowledge/` scope filter but no longer excludes
  `Knowledge/inbox/` results.
- **Do NOT re-embed the corpus in this task** (T8 does the single rebuild); but DO run
  `kb-engine eval` live after `sync` picks up the 12 inbox files — the eval gate must
  hold 8/8 with inbox notes in the index.

- [ ] **Step 1: Failing tests.** In `test_chunking.py` add:

```python
def test_embedding_text_threads_why():
    note = _note(title="T", frontmatter={"summary": "S", "why": "for the demo"})
    assert embedding_text(note) == "T\n\nS\n\nfor the demo"


def test_embedding_text_no_why_unchanged():
    note = _note(title="T", frontmatter={"summary": "S"})
    assert embedding_text(note) == "T\n\nS"
```

(Adapt `_note` construction to the file's existing test helpers.) In `test_sync.py`,
flip the inbox-exclusion test: an inbox note IS indexed (update name + assertions —
document in the report that this is the deliberate Phase-3 change). In `test_search.py`
add: a synced inbox note appears in `hybrid_search` results.

- [ ] **Step 2: RED**, then implement:
  - `chunking.embedding_text`: after computing the current `title\n\nsummary` result,
    append `f"\n\n{why}"` when `why := str(note.frontmatter.get("why") or "").strip()`
    is non-empty.
  - `sync.EXCLUDED_DIRS = ()` (keep the constant + comment explaining inbox is now
    indexed by design).
  - `search.py`: remove the `inbox_prefix` filtering lines from `hybrid_search` (keep
    `scope_prefix` filtering); delete the now-unused `INBOX_PREFIX` constant.
- [ ] **Step 3: Full suite** (expect ~368) — then **live eval gate**:

```bash
cd /Users/andreym/Documents/dotfiles/kb-engine
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
uv run kb-engine --vault "$VAULT" sync      # picks up the ~12 inbox notes
uv run kb-engine --vault "$VAULT" eval      # MUST be 1.00 (8/8); STOP on any miss
```

- [ ] **Step 4: Commit** — `git add kb-engine/ && git commit -m "feat(kb-engine): thread why into vectors; index the inbox"`

---

### Task 6: Shared extractor + `backfill-content`

**Files:**
- Create: `kb-engine/src/kb_engine/extract.py` (refactor out of `importing/mail.py`)
- Modify: `kb-engine/src/kb_engine/importing/mail.py` (delegate to extract.py —
  behavior byte-identical, its tests stay green)
- Create: `kb-engine/src/kb_engine/backfill.py`
- Modify: `kb-engine/src/kb_engine/cli.py` (command `backfill-content`)
- Modify: `kb-engine/src/kb_engine/pipeline.py` (weekly step `backfill` between enrich
  and sync; detail `"N fetched · N unavailable · N skipped"`; batch limit 50)
- Test: `kb-engine/tests/test_extract.py`, `tests/test_backfill.py`; update
  `test_pipeline_hardening.py` weekly order (insert "backfill")

**Interfaces:**
- `extract.html_to_markdown(html: str) -> str | None` — trafilatura
  (`include_tables=False`, markdown output; the exact call currently in
  `mail.body_markdown`), `None` when trafilatura yields nothing. Lazy-import
  trafilatura exactly as mail.py does today (its `[mail]` extra gating must keep
  working; backfill reports a clean failure when the extra is absent).
- `backfill.BackfillStats(fetched: int, unavailable: int, skipped: int, failures: tuple[str, ...])` (frozen)
- `backfill.backfill_candidates(cfg) -> list[str]` — vault-relative paths where: body
  < 500 chars stripped; frontmatter has `url`; `source` in `{"article", "github", "newsletter"}`;
  no `content: unavailable`; `content_attempts` (int, default 0) < 3; skips `wiki/`.
- `backfill.backfill_content(cfg, store, limit: int = 50, client: httpx.Client | None = None) -> BackfillStats`
  — fetch (follow redirects, 30s timeout, UA `kb-engine/0.1`), extract, append
  `\n\n## Content\n\n` + markdown capped at 4,000 words + truncation marker
  `\n\n…truncated — full text at {url}\n` when capped; per-domain ≥2s spacing
  (monotonic clock dict); on failure increment `content_attempts` in frontmatter; on
  the 3rd failure also set `content: unavailable`; per-item try/except (never abort);
  records a run row (`store.start_run("backfill")`/`finish_run`).
- CLI: `backfill-content [--limit 50] [--json]` printing the stats.

- [ ] **Step 1: Failing tests.**

`test_extract.py`: `html_to_markdown` on a small article HTML fixture returns markdown
containing the article text and NO `|` table-pipe wrapper; returns None on empty/garbage
HTML. (Gate with `pytest.importorskip("trafilatura")` matching the existing mail-test
idiom.)

`test_backfill.py` (httpx.MockTransport; FakeEmbedder-free — no embedding here):

```python
def test_candidates_selects_stubs_only(tmp_path): ...
    # stub (short body + url + article) selected; long-body note, url-less note,
    # tweet-source note, content:unavailable note, wiki/ note all excluded

def test_fetch_success_appends_content_section(tmp_path): ...
    # MockTransport returns article HTML; body gains "## Content" + text;
    # frontmatter untouched except nothing added; stats.fetched == 1

def test_cap_and_truncation_marker(tmp_path): ...
    # >4000-word extraction → capped, marker contains the url

def test_failure_increments_attempts_then_marks_unavailable(tmp_path): ...
    # MockTransport 404 three runs in a row → content_attempts 1,2 then
    # content: unavailable on the 3rd; stats.unavailable == 1 on the third run

def test_per_item_errors_never_abort(tmp_path): ...
    # two candidates, transport raises for the first → failures==(first,), second fetched
```

(Write the bodies fully in the implementation session — each is ~15 lines with the
tmp-vault helpers from test_enrich.py's pattern; the transport handler switches on
request URL.)

- [ ] **Step 2: RED → implement** extract.py (~30 lines), mail.py delegation (import
  from extract; keep `body_markdown`'s public behavior + tests green), backfill.py
  (~130 lines), CLI command (mirror `eval` idioms; runs record), pipeline weekly step.
- [ ] **Step 3: Full suite** (expect ~375+) — includes the untouched mail tests
  (`--extra mail` variant per repo practice if applicable). **Step 4: Commit**

```bash
git add kb-engine/ && git commit -m "feat(kb-engine): shared trafilatura extractor + backfill-content"
```

---

### Task 7: Secrets provisioning + Nix wiring + runbook (ends with USER handoff)

**Files:**
- Modify: `modules/home/dev/kb-engine.nix` (runners source the secrets file)
- Modify: `kb-engine/src/kb_engine/doctor.py` (+ test) — secrets check severity warn→**hard**
- Modify: `kb-engine/README.md` (bootstrap runbook section)

- [ ] **Step 1: Nix — source secrets in the pipeline runners.** In `mkPipelineRunner`,
  before the kb-engine invocation:

```bash
if [ -f "$HOME/.config/kb-engine/secrets.env" ]; then
  set -a
  . "$HOME/.config/kb-engine/secrets.env"
  set +a
fi
```

(Pipeline runners only — NOT the autocommit runner.) `just switch`; kickstart daily;
confirm digest still ✅ (enrich/import-mail still skip until the user fills the file —
that's expected).

- [ ] **Step 2: Doctor flip (TDD).** Change `_check_secrets` severity to `"hard"`;
  update/extend `test_doctor.py` accordingly (missing file → failed hard). Full suite.

- [ ] **Step 3: Create the template file** (0600):

```bash
mkdir -p ~/.config/kb-engine
cat > ~/.config/kb-engine/secrets.env <<'EOF'
# kb-engine secrets — filled from 1Password, never committed anywhere.
# FASTMAIL_API_TOKEN: Fastmail Settings → Privacy & Security → API tokens (read-only, Mail).
# ANTHROPIC_API_KEY:  console.anthropic.com → API keys (dedicated key for KB enrichment).
FASTMAIL_API_TOKEN=
ANTHROPIC_API_KEY=
EOF
chmod 600 ~/.config/kb-engine/secrets.env
```

- [ ] **Step 4: README runbook** — add a "Fresh machine bootstrap" section: clone →
  `just switch` → create+fill `~/.config/kb-engine/secrets.env` from 1Password (0600) →
  `kb-engine --vault "<vault>" rebuild` → `kb-engine --vault "<vault>" doctor` green →
  agents verify via `launchctl list | grep kb`.

- [ ] **Step 5: Commit** —
  `git add modules/ kb-engine/ && git commit -m "feat(kb): secrets provisioning — runners source secrets.env; doctor hardens; runbook"`

- [ ] **Step 6: USER HANDOFF (blocking for T8).** Relay to Andrey: ① rotate the
  Fastmail token NOW if not yet done; ② put the new token + a dedicated
  `ANTHROPIC_API_KEY` into `~/.config/kb-engine/secrets.env`; ③ optional but
  recommended: disable "Optimize Mac Storage". T8 starts only on his confirmation.

---

### Task 8: Supervised drain + single re-embed (USER-GATED; live)

**Prerequisite:** Andrey confirmed `secrets.env` is filled. Verify: `kb-engine doctor`
→ secrets ✅ (hard).

- [ ] **Step 1: Live enrichment spot-check.** `export $(grep -v '^#' ~/.config/kb-engine/secrets.env | xargs)`
  then `uv run kb-engine --vault "$VAULT" pipeline --tier daily --json`: enrich step
  reports N>0 summarized (the ~16 legacy empties + any inbox gaps); spot-read 2 enriched
  notes — sensible summaries, `provenance: auto`, human fields untouched. Digest ✅.
- [ ] **Step 2: One-shot backfill drain.** Loop `uv run kb-engine --vault "$VAULT" backfill-content --limit 100 --json`
  until `fetched == 0 and skipped == 0` remaining candidates (or only permanent
  `unavailable` remain). Report total fetched / unavailable / coverage % (fetched ÷
  original candidate count). Expect a substantial share of the ~460 June stubs to
  fetch; tweets/dead links marked unavailable are accepted.
- [ ] **Step 3: The single re-embed.** `uv run kb-engine --vault "$VAULT" rebuild`
  (minutes; model load + ~600 notes).
- [ ] **Step 4: THE EVAL GATE.** `uv run kb-engine --vault "$VAULT" eval` — recall@5
  1.00 (8/8) required. Any miss: STOP, report per-probe output, controller adjudicates.
- [ ] **Step 5: Vault commit + phase exit.**

```bash
git -C "$VAULT" add -A && git -C "$VAULT" commit -m "feat: phase-3 corpus — auto-enrichment, content backfill"
```

Phase-exit report: enrichment counts, backfill coverage %, eval + MRR (expect MRR to
move — record the new value as the reference alongside the 0.73 baseline), doctor
all-✅ (secrets now hard-green), digest Status ✅.

---

## Phase exit criteria (spec §6 Phase 3)

- A note captured today is auto-summarized and semantically findable the next daily run
  with zero human touch (indexed in inbox, summary drafted, why threaded).
- Backfill drained (coverage % reported; permanent failures marked, accepted).
- Corpus re-embedded once on final inputs; **eval ≥ baseline (8/8)**.
- `doctor` fully green including hard secrets; fresh-machine runbook committed.
