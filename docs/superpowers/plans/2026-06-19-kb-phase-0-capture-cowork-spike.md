# KB Phase 0 — Capture + Cowork Validation Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove — before building the topic/project layers — that the Obsidian Web Clipper can capture everything we need (across sources + devices, with a "why") into an engine-ingestible inbox note, and that Claude Cowork can reach a local kb-engine MCP tool (and refresh a Live Artifact from it).

**Architecture:** Front-load the assistant-buildable artifacts (an inbox clip-schema *verification command*, the *Web Clipper template*, the *test checklist*, a minimal *MCP probe server*, and *Cowork setup docs*) so the user's manual work is just: install the extension, clip a fixed test set on Mac + iPhone, register the MCP, eyeball a Live Artifact. The verification command defines the output contract the template must hit, decoupling us from Web-Clipper-version quirks. Everything is a validation gate — code added here is the small, reusable verification command + a throwaway-grade MCP probe; the production read/review MCP is Phase 1.

**Tech Stack:** Python `kb_engine` (click CLI, `python-frontmatter`, sqlite3); `mcp` Python SDK (FastMCP, new optional `[mcp]` extra) for the probe; Obsidian Web Clipper; Claude Cowork (local MCP + Live Artifacts). Tests: pytest, torch-free (`tmp_path` vaults, no ML deps).

**Working dir for all commands:** `/Users/andreym/Documents/dotfiles/kb-engine` (run `uv run pytest -q` there). Branch: `feat/kb-capture-cowork-topics`. Spec: `docs/superpowers/specs/2026-06-19-kb-capture-cowork-rich-topics-design.md`.

## Global Constraints

- **No silent guesses / nothing lost** (core invariant): verification *reports*, it does not mutate notes. `why` is *reported* (warn if missing), never required — the degraded path adds "why" during review.
- **Engine core stays deterministic + offline**: no `now()`/network in tested functions. The MCP probe's timestamp lives in untested glue at the server edge, not in a tested function.
- **Inbox note schema (exact, from `importing/inbox.py`):** frontmatter keys `title, url, source, date_added, summary, status, context, tags`; `status` value is `inbox`; body is `## Notes\n\nPending processing.`. Clips add two new keys: `why` (free text) and `project` (optional string, may be empty).
- **URL normalization for dedup:** `kb_engine.importing.urls.normalize_url` (lowercased host, tracking params dropped, fragment dropped, trailing slash stripped). Dedup source of truth: `kb_engine.importing.inbox.existing_urls(vault)`.
- **`source` values:** one of `github|tweet|youtube|paper|newsletter|podcast|article` (via `infer_source`).
- Commits are SSH-signed via 1Password (must be unlocked, else `git commit` fails `failed to fill whole buffer`).

---

## File Structure

| File | Task | Responsibility |
|------|------|----------------|
| `kb-engine/src/kb_engine/inbox_check.py` | 1 | Pure validation: given inbox notes, report schema-validity + `why` presence + dup URLs |
| `kb-engine/src/kb_engine/cli.py` | 1 | Wire `inbox-check` command (reads vault, prints JSON/text report) |
| `kb-engine/tests/test_inbox_check.py` | 1 | Unit tests (tmp vault) |
| `kb-engine/capture/web-clipper-template.json` | 2 | The Obsidian Web Clipper template (property → frontmatter mapping) |
| `kb-engine/capture/README-web-clipper.md` | 2 | Install + import + per-field explanation |
| `kb-engine/capture/CAPTURE-TEST-CHECKLIST.md` | 3 | The source×device test matrix the user runs, with pass/fail recording |
| `kb-engine/src/kb_engine/mcp/__init__.py` | 4 | package marker |
| `kb-engine/src/kb_engine/mcp/probe.py` | 4 | Minimal MCP server: `kb_status`, `kb_search` tools wrapping engine reads |
| `kb-engine/tests/test_mcp_probe.py` | 4 | Unit tests for the tool *functions* (not transport) |
| `kb-engine/pyproject.toml` | 4 | add optional `[mcp]` extra (`mcp` SDK) |
| `kb-engine/capture/COWORK-MCP-SETUP.md` | 5 | Register the probe in Claude Desktop/Cowork; Live-Artifact refresh test |
| `docs/superpowers/specs/...-design.md` (Phase 0 results section) | 6 | Record outcomes + degraded-path decisions; gate Phase 1 |

**Who does what:** Tasks 1, 2, 4 are **assistant-built**. Tasks 3 and 5 are assistant-authored docs the **user runs** (install extension, clip on Mac+iPhone, register MCP, open a Live Artifact). Task 6 is a joint gate.

---

## Task 1: `inbox-check` — clip-schema verification command

**Files:**
- Create: `kb-engine/src/kb_engine/inbox_check.py`
- Modify: `kb-engine/src/kb_engine/cli.py` (add `inbox-check` command)
- Test: `kb-engine/tests/test_inbox_check.py`

**Interfaces:**
- Consumes: `kb_engine.importing.urls.normalize_url`; `kb_engine.vault.iter_notes`.
- Produces: `check_inbox(vault: Path) -> InboxReport` where `InboxReport` is a frozen dataclass with fields `n_notes: int`, `schema_ok: tuple[str, ...]`, `schema_bad: tuple[tuple[str, tuple[str, ...]], ...]` (path, missing-keys), `missing_why: tuple[str, ...]`, `dup_in_inbox: tuple[tuple[str, tuple[str, ...]], ...]` (normalized-url, paths), `dup_vs_knowledge: tuple[tuple[str, str], ...]` (inbox-path, normalized-url already filed).

- [ ] **Step 1: Write the failing test**

```python
# kb-engine/tests/test_inbox_check.py
from pathlib import Path

import frontmatter

from kb_engine.inbox_check import check_inbox, InboxReport

_REQUIRED = ("title", "url", "source", "date_added", "status", "tags")


def _write(vault: Path, relpath: str, **fm) -> None:
    p = vault / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(frontmatter.dumps(frontmatter.Post("## Notes\n\nPending processing.", **fm)) + "\n")


def _good_fm(url="https://example.com/a", **over):
    fm = dict(title="A", url=url, source="article", date_added="2026-06-19",
              summary="", status="inbox", context="Web Clipper", tags=[],
              why="for the game project", project="retro-platformer")
    fm.update(over)
    return fm


def test_valid_clip_passes_and_has_why(tmp_path):
    _write(tmp_path, "Knowledge/inbox/a.md", **_good_fm())
    report = check_inbox(tmp_path)
    assert isinstance(report, InboxReport)
    assert report.n_notes == 1
    assert report.schema_ok == ("Knowledge/inbox/a.md",)
    assert report.schema_bad == ()
    assert report.missing_why == ()


def test_missing_required_key_is_schema_bad(tmp_path):
    fm = _good_fm(); del fm["source"]
    _write(tmp_path, "Knowledge/inbox/b.md", **fm)
    report = check_inbox(tmp_path)
    assert report.schema_ok == ()
    assert report.schema_bad == (("Knowledge/inbox/b.md", ("source",)),)


def test_missing_why_is_warned_not_failed(tmp_path):
    fm = _good_fm(); del fm["why"]
    _write(tmp_path, "Knowledge/inbox/c.md", **fm)
    report = check_inbox(tmp_path)
    assert report.schema_ok == ("Knowledge/inbox/c.md",)   # why is NOT required
    assert report.missing_why == ("Knowledge/inbox/c.md",)  # but it is reported


def test_duplicate_urls_within_inbox_are_reported(tmp_path):
    # same URL up to normalization (trailing slash + tracking param)
    _write(tmp_path, "Knowledge/inbox/d.md", **_good_fm(url="https://example.com/x"))
    _write(tmp_path, "Knowledge/inbox/e.md", **_good_fm(url="https://example.com/x/?utm_source=t"))
    report = check_inbox(tmp_path)
    assert report.dup_in_inbox == (
        ("https://example.com/x", ("Knowledge/inbox/d.md", "Knowledge/inbox/e.md")),
    )


def test_inbox_url_already_filed_is_reported(tmp_path):
    _write(tmp_path, "Knowledge/articles/filed.md", **_good_fm(url="https://example.com/y", status="reference"))
    _write(tmp_path, "Knowledge/inbox/f.md", **_good_fm(url="https://example.com/y"))
    report = check_inbox(tmp_path)
    assert report.dup_vs_knowledge == (("Knowledge/inbox/f.md", "https://example.com/y"),)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_inbox_check.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kb_engine.inbox_check'`.

- [ ] **Step 3: Implement**

```python
# kb-engine/src/kb_engine/inbox_check.py
"""Validate Knowledge/inbox/ notes against the clip schema (report-only).

A *gate* for the capture spike: confirms clipped notes carry the inbox schema,
reports whether each recorded its "why", and surfaces duplicate URLs (within the
inbox and against already-filed notes). It never mutates notes — surfacing,
never guessing, is the contract.
"""

from dataclasses import dataclass
from pathlib import Path

from kb_engine.importing.urls import normalize_url
from kb_engine.vault import iter_notes

# Keys every inbox note must carry (the import/clip schema, minus the optional
# summary/context/why which are allowed to be empty/absent at capture time).
_REQUIRED_KEYS = ("title", "url", "source", "date_added", "status", "tags")
_INBOX_RELDIR = "Knowledge/inbox"


@dataclass(frozen=True)
class InboxReport:
    n_notes: int
    schema_ok: tuple[str, ...]
    schema_bad: tuple[tuple[str, tuple[str, ...]], ...]  # (path, missing keys)
    missing_why: tuple[str, ...]
    dup_in_inbox: tuple[tuple[str, tuple[str, ...]], ...]  # (norm url, paths)
    dup_vs_knowledge: tuple[tuple[str, str], ...]  # (inbox path, norm url)


def check_inbox(vault: Path) -> InboxReport:
    vault = Path(vault)
    inbox_dir = vault / _INBOX_RELDIR
    schema_ok: list[str] = []
    schema_bad: list[tuple[str, tuple[str, ...]]] = []
    missing_why: list[str] = []
    by_url: dict[str, list[str]] = {}

    notes = list(iter_notes(inbox_dir, base=vault)) if inbox_dir.is_dir() else []
    for note in notes:
        fm = note.frontmatter
        missing = tuple(k for k in _REQUIRED_KEYS if not _present(fm, k))
        if missing:
            schema_bad.append((note.path, missing))
        else:
            schema_ok.append(note.path)
        if not _present(fm, "why"):
            missing_why.append(note.path)
        url = fm.get("url")
        if url:
            by_url.setdefault(normalize_url(str(url)), []).append(note.path)

    dup_in_inbox = tuple(
        (url, tuple(sorted(paths))) for url, paths in sorted(by_url.items()) if len(paths) > 1
    )

    # Already filed = a matching url on a note OUTSIDE the inbox. (Can't reuse
    # existing_urls here: it dedups inbox+filed into one set, hiding the overlap.)
    filed: set[str] = set()
    knowledge = vault / "Knowledge"
    if knowledge.is_dir():
        for other in iter_notes(knowledge, base=vault):
            if other.path.startswith(_INBOX_RELDIR + "/"):
                continue
            other_url = other.frontmatter.get("url")
            if other_url:
                filed.add(normalize_url(str(other_url)))
    dup_vs_knowledge = tuple(
        (paths[0], url) for url, paths in sorted(by_url.items()) if url in filed
    )

    return InboxReport(
        n_notes=len(notes),
        schema_ok=tuple(sorted(schema_ok)),
        schema_bad=tuple(sorted(schema_bad)),
        missing_why=tuple(sorted(missing_why)),
        dup_in_inbox=dup_in_inbox,
        dup_vs_knowledge=dup_vs_knowledge,
    )


def _present(fm, key: str) -> bool:
    """True if the key exists and is non-empty (empty string/list count as absent)."""
    if key not in fm:
        return False
    value = fm.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, dict)):
        return True  # an empty tags list is still a present 'tags' key
    return True
```
Note: `tags` is "present" even when `[]` (an empty list is a valid, present `tags`); only string keys are emptiness-checked. `existing_urls` already returns *normalized* urls, so subtracting `inbox_urls` (also normalized) is correct.

Then add the command to `cli.py` (near `status`); reuse the existing `_emit` helper:
```python
from kb_engine.inbox_check import check_inbox  # with the other kb_engine imports


@main.command("inbox-check")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def inbox_check(cfg: Config, as_json: bool) -> None:
    """Validate Knowledge/inbox/ clips against the schema (report-only, no writes)."""
    report = check_inbox(cfg.vault_path)
    payload = {
        "n_notes": report.n_notes,
        "schema_ok": len(report.schema_ok),
        "schema_bad": [{"note": p, "missing": list(m)} for p, m in report.schema_bad],
        "missing_why": list(report.missing_why),
        "dup_in_inbox": [{"url": u, "notes": list(p)} for u, p in report.dup_in_inbox],
        "dup_vs_knowledge": [{"note": n, "url": u} for n, u in report.dup_vs_knowledge],
    }
    _emit(
        payload,
        as_json,
        f"inbox: {report.n_notes} notes | schema_ok={len(report.schema_ok)} "
        f"schema_bad={len(report.schema_bad)} missing_why={len(report.missing_why)} "
        f"dup_in_inbox={len(report.dup_in_inbox)} dup_vs_knowledge={len(report.dup_vs_knowledge)}",
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_inbox_check.py -v` → PASS. Then `uv run pytest -q` (full suite stays green).

- [ ] **Step 5: Commit**

```bash
git add src/kb_engine/inbox_check.py src/kb_engine/cli.py tests/test_inbox_check.py
git commit -m "feat(kb-engine): inbox-check — validate clip schema + why + dups (report-only)"
```

---

## Task 2: Obsidian Web Clipper template + install doc (assistant-authored)

**Files:**
- Create: `kb-engine/capture/web-clipper-template.json`
- Create: `kb-engine/capture/README-web-clipper.md`

This task has no automated test — its *output contract is Task 1's `inbox-check`*. The template aims to produce notes that pass `inbox-check`; the actual pass/fail is measured in Task 3 against the installed clipper version (which is the real source of truth for the template JSON schema).

- [ ] **Step 1: Author the template JSON**

Target frontmatter (each clip): `title`, `url` (the page URL — `inbox-check`/engine normalize on read), `source` (leave the engine's `infer_source` to set it at process time; clipper sets a literal `article` default so the key is present), `date_added` (clip date `YYYY-MM-DD`), `summary` (empty — filled at process time), `status: inbox`, `context: "Web Clipper"`, `tags: []`, `why` (the prompted intent), `project` (optional). Body = the clipped page content (readability extraction), under a `## Notes` is not required for clips — the clipped content replaces the stub body.

Write `kb-engine/capture/web-clipper-template.json` as a best-effort Obsidian Web Clipper template:
```json
{
  "schemaVersion": "0.1.0",
  "name": "KB Inbox",
  "behavior": "create",
  "noteNameFormat": "{{title|safe_name}}",
  "path": "Knowledge/inbox",
  "noteContentFormat": "{{content|markdown}}",
  "properties": [
    {"name": "title", "value": "{{title}}", "type": "text"},
    {"name": "url", "value": "{{url}}", "type": "text"},
    {"name": "source", "value": "article", "type": "text"},
    {"name": "date_added", "value": "{{date:YYYY-MM-DD}}", "type": "date"},
    {"name": "summary", "value": "", "type": "text"},
    {"name": "status", "value": "inbox", "type": "text"},
    {"name": "context", "value": "Web Clipper", "type": "text"},
    {"name": "tags", "value": "", "type": "multitext"},
    {"name": "why", "value": "{{\"Why are you saving this?\"}}", "type": "text"},
    {"name": "project", "value": "", "type": "text"}
  ]
}
```
NOTE: the `why` value uses Web Clipper's prompt syntax `{{"...?"}}` IF the installed version supports clip-time prompts; if it does not (the pivotal Phase-0a unknown), set `why` to empty and the README records the degraded path (add "why" during `/kb:review`). Property `type`/value syntax may differ across clipper versions — Step 2 reconciles against the real extension.

- [ ] **Step 2: Author the install README**

Write `kb-engine/capture/README-web-clipper.md` covering: install Obsidian Web Clipper (Safari desktop + iOS); set the vault to the iCloud `Main` vault; import `web-clipper-template.json` (or recreate the properties listed above if import differs by version); set the note folder to `Knowledge/inbox`; confirm the `why` prompt appears at clip time (or record that it doesn't → degraded path); one-paragraph explanation of each frontmatter field and the no-loss/why intent. State explicitly: the template is "best-effort"; the **authoritative gate is `kb-engine inbox-check`** on the clipped output.

- [ ] **Step 3: Commit**

```bash
git add capture/web-clipper-template.json capture/README-web-clipper.md
git commit -m "docs(kb): Obsidian Web Clipper template + install guide (capture front door)"
```

---

## Task 3: Capture test checklist (assistant-authored; USER RUNS)

**Files:**
- Create: `kb-engine/capture/CAPTURE-TEST-CHECKLIST.md`

- [ ] **Step 1: Author the checklist**

Write `kb-engine/capture/CAPTURE-TEST-CHECKLIST.md` as a runnable matrix. For each source clip TWICE (once macOS Safari, once iPhone Safari) where practical:

| # | Source | URL to use | Device(s) | Pass = |
|---|--------|------------|-----------|--------|
| 1 | plain article | any blog/news post | Mac + iPhone | content clean, `why` captured |
| 2 | Twitter/X tweet+thread | a tweet URL | Mac + iPhone | tweet text present (not login wall) |
| 3 | GitHub repo | a repo page | Mac | README/desc present |
| 4 | YouTube | a video URL | Mac + iPhone | title/desc present |
| 5 | Reddit thread | a thread URL | Mac | post/comments present (was headless-blocked) |
| 6 | paywalled/JS page | a Substack/doc you can read | Mac | body present (authed) |
| 7 | shortened link | a `t.co`/bit.ly link | Mac | resolves to destination |
| 8 | Instagram | a post URL | Mac | best-effort (allowed to fail) |
| 9 | email link | open a link from Mail → clip | Mac + iPhone | destination clipped |

Then the verification step the user runs after clipping:
```bash
cd /Users/andreym/Documents/dotfiles/kb-engine
VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"
uv run kb-engine --vault "$VAULT" inbox-check --json
```
Record per the report: `schema_bad` must be empty; `missing_why` should be empty (or note the degraded path); `dup_in_inbox`/`dup_vs_knowledge` reviewed. Include a results table for the user to fill (source → device → clean? → why-captured? → notes). Add a cleanup note: delete the test clips from `Knowledge/inbox/` after recording (they're throwaway).

- [ ] **Step 2: Commit**

```bash
git add capture/CAPTURE-TEST-CHECKLIST.md
git commit -m "docs(kb): capture feasibility test checklist (sources x devices)"
```

- [ ] **Step 3: USER RUNS the checklist** *(not an assistant step)*

The user installs the extension (per Task 2 README), clips the test set on Mac + iPhone, runs `inbox-check`, and fills the results table. Assistant then reviews the report + diagnoses any `schema_bad` (adjust template) or content-quality failures. Loop until the matrix is green or degraded paths are explicitly chosen.

---

## Task 4: Minimal kb-engine MCP probe server

**Files:**
- Create: `kb-engine/src/kb_engine/mcp/__init__.py` (empty)
- Create: `kb-engine/src/kb_engine/mcp/probe.py`
- Modify: `kb-engine/pyproject.toml` (add optional `[mcp]` extra with the `mcp` SDK)
- Test: `kb-engine/tests/test_mcp_probe.py`

**Interfaces:**
- Consumes: `kb_engine.store.Store`, `kb_engine.config.Config`, `kb_engine.search.hybrid_search`, `kb_engine.embeddings` builders.
- Produces: pure functions `status_payload(store: Store) -> dict` (`{"notes": int, "chunks": int}`) and `search_payload(store, embedder, query: str, limit: int) -> list[dict]` (`[{"note_path","title","score"}]`). The MCP `kb_status`/`kb_search` tools are thin wrappers; only the payload functions are unit-tested.

- [ ] **Step 1: Write the failing test** (torch-free — uses `FakeEmbedder`)

```python
# kb-engine/tests/test_mcp_probe.py
import numpy as np

from kb_engine.embeddings import FakeEmbedder
from kb_engine.store import Store
from kb_engine.mcp.probe import status_payload, search_payload


def _seed(tmp_path):
    s = Store(tmp_path / "kb.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="Rust Macros", sha256="h", tags=[], summary="declarative macros")
    s.replace_chunks("Knowledge/a.md", [(0, "Rust Macros\n\ndeclarative macros", np.ones(64, np.float32))])
    return s


def test_status_payload_counts(tmp_path):
    s = _seed(tmp_path)
    assert status_payload(s) == {"notes": 1, "chunks": 1}
    s.close()


def test_search_payload_returns_hits(tmp_path):
    s = _seed(tmp_path)
    hits = search_payload(s, FakeEmbedder(dim=64), "macros", limit=5)
    assert hits and hits[0]["note_path"] == "Knowledge/a.md"
    assert set(hits[0]) == {"note_path", "title", "score"}
    s.close()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_mcp_probe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'kb_engine.mcp'`.

- [ ] **Step 3: Implement**

Add the optional extra to `pyproject.toml` (under `[project.optional-dependencies]`, mirroring the existing `ml`/`topics` extras):
```toml
mcp = ["mcp>=1.2,<2.0"]
```

`kb-engine/src/kb_engine/mcp/__init__.py`: empty file.

```python
# kb-engine/src/kb_engine/mcp/probe.py
"""Minimal local MCP probe: prove Cowork can call a kb-engine tool + that a Live
Artifact can refresh from it. Throwaway-grade — the production read/review MCP
is Phase 1. Vault/DB come from KB_VAULT/KB_DB env (MCP servers get no per-call
args). The `mcp` SDK is an optional extra; importing the server requires it, but
the payload functions below are import-light and unit-tested without it.
"""

import os
from pathlib import Path

from kb_engine.config import Config
from kb_engine.embeddings import Embedder, FakeEmbedder, LocalJinaEmbedder
from kb_engine.search import hybrid_search
from kb_engine.store import Store

_DEFAULT_LIMIT = 10


def status_payload(store: Store) -> dict:
    return {"notes": store.count_notes(), "chunks": store.count_chunks()}


def search_payload(
    store: Store, embedder: Embedder, query: str, limit: int = _DEFAULT_LIMIT
) -> list[dict]:
    results = hybrid_search(store, embedder, query, limit=limit)
    return [
        {"note_path": path, "title": store.note_title(path) or path, "score": round(score, 6)}
        for path, score in results
    ]


def _config() -> Config:
    vault = Path(os.environ["KB_VAULT"])
    db = os.environ.get("KB_DB")
    return Config(vault_path=vault, db_path=Path(db) if db else None)


def _embedder(cfg: Config) -> Embedder:
    if os.environ.get("KB_FAKE_EMBED") == "1":
        return FakeEmbedder(dim=cfg.embed_dim)
    return LocalJinaEmbedder(model_name=cfg.model_name, dim=cfg.embed_dim)


def build_server():
    """Construct the FastMCP server (requires the [mcp] extra). Tools are thin
    wrappers over the tested payload functions; kb_status adds a server-edge
    timestamp so a Live Artifact visibly refreshes (not in a tested function)."""
    from datetime import datetime, timezone

    from mcp.server.fastmcp import FastMCP

    server = FastMCP("kb-engine-probe")
    cfg = _config()

    @server.tool()
    def kb_status() -> dict:
        store = Store(cfg.db_path)
        try:
            store.init_schema()
            payload = status_payload(store)
        finally:
            store.close()
        payload["server_time"] = datetime.now(timezone.utc).isoformat()
        return payload

    @server.tool()
    def kb_search(query: str, limit: int = _DEFAULT_LIMIT) -> list[dict]:
        store = Store(cfg.db_path)
        try:
            store.init_schema()
            return search_payload(store, _embedder(cfg), query, limit)
        finally:
            store.close()

    return server


def main() -> None:
    build_server().run()  # stdio transport (Claude Desktop local MCP default)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_mcp_probe.py -v` → PASS (payload functions don't import `mcp`). Then `uv run pytest -q` (full suite green; the `mcp` import is lazy inside `build_server`, so the suite needs no `mcp` install).

- [ ] **Step 5: Smoke-check the server starts** (needs the extra)

Run: `uv run --extra mcp python -c "from kb_engine.mcp.probe import build_server; build_server(); print('ok')"` with `KB_VAULT=/tmp` set.
Expected: prints `ok` (server constructs; no transport yet).

- [ ] **Step 6: Commit**

```bash
git add src/kb_engine/mcp/__init__.py src/kb_engine/mcp/probe.py pyproject.toml tests/test_mcp_probe.py
git commit -m "feat(kb-engine): minimal MCP probe server (kb_status, kb_search)"
```

---

## Task 5: Cowork MCP registration + Live-Artifact refresh test (assistant-authored; USER RUNS)

**Files:**
- Create: `kb-engine/capture/COWORK-MCP-SETUP.md`

- [ ] **Step 1: Author the setup + test doc**

Write `kb-engine/capture/COWORK-MCP-SETUP.md` covering:
1. **Register the probe as a local MCP server** in Claude Desktop/Cowork (the local-MCP config; command =
   `uv run --extra mcp --project /Users/andreym/Documents/dotfiles/kb-engine python -m kb_engine.mcp.probe`,
   env = `KB_VAULT="/Users/andreym/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main"`). Include the exact JSON snippet for the `mcpServers` entry, and where the config file lives.
2. **Connectivity test:** in Cowork, ask it to call `kb_search("rust")` / `kb_status` and confirm real results come back.
3. **Live-Artifact refresh test:** ask Cowork to make a Live Artifact that displays `kb_status` (notes/chunks + `server_time`). Close + reopen it; confirm `server_time` updates → proves the artifact re-queries the custom local MCP on open. **If it does NOT refresh from the custom MCP**, record the fallback: a Cowork *scheduled/on-demand task* regenerates the artifact's data instead.
4. A results section to record: connectivity (Y/N), live refresh (Y/N), chosen refresh mechanism.

- [ ] **Step 2: Commit**

```bash
git add capture/COWORK-MCP-SETUP.md
git commit -m "docs(kb): Cowork MCP registration + Live-Artifact refresh test"
```

- [ ] **Step 3: USER RUNS** *(not an assistant step)*

User registers the MCP, runs the connectivity + refresh tests, records results. Assistant diagnoses any failures.

---

## Task 6: Phase 0 exit gate (joint)

**Files:**
- Modify: `docs/superpowers/specs/2026-06-19-kb-capture-cowork-rich-topics-design.md` (append a "## Phase 0 results" section)

- [ ] **Step 1: Record outcomes + decisions**

Append a "## Phase 0 results (YYYY-MM-DD)" section to the spec capturing: capture matrix outcome per source/device; whether the clipper prompts for `why` (or degraded path chosen); whether the in-browser clip obviated the fetch tier; Cowork↔MCP connectivity; Live-Artifact refresh mechanism (live vs scheduled fallback). These feed Phase 1's plan.

- [ ] **Step 2: Verify exit criteria**

Exit criteria (ALL must hold to start Phase 1):
- Capture matrix green for the must-have sources (article, tweet, github, youtube, paywalled, email-link), or a degraded path explicitly recorded for any miss.
- `kb-engine inbox-check` reports `schema_bad == 0` on the clipped test set.
- The `why` capture path is decided (clip-time prompt **or** review-time fill).
- Cowork reaches the local MCP and calls a tool; the Live-Artifact refresh mechanism is chosen.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-19-kb-capture-cowork-rich-topics-design.md
git commit -m "docs(kb): record Phase 0 capture+Cowork validation results"
```

---

## Notes for the implementer

- **TDD for code tasks (1, 4):** failing test → RED → implement → GREEN → commit; run the full suite (`uv run pytest -q`) before each commit.
- **Tasks 2, 3, 5 are docs/config** the *user* executes (install extension, clip on devices, register MCP). Don't try to clip or install on the user's behalf — build the artifacts, then hand off and verify their results.
- **The output contract is `inbox-check`, not the template JSON** — Web Clipper template schema varies by version, so we measure the clipped *output*, not the template.
- **Keep the engine offline/deterministic:** the only network/time use is in the MCP probe's server-edge glue (`build_server`), never in a tested function. The `mcp` import stays lazy so the test suite needs no `mcp` install.
- **No vault writes from verification** — `inbox-check` is report-only (core invariant: surface, never guess).
