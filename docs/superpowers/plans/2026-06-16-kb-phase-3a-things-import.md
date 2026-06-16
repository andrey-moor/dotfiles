# KB Phase 3a — Things Import & Digest Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development with TDD.

**Goal:** Two deterministic engine commands: (1) `import-things` — read the local Things 3 SQLite read-only, extract URLs from open URL-bearing tasks, dedup (within-batch + against existing vault note URLs), and write proper-schema `inbox/` stubs (filterable, with `--dry-run`); (2) `digest` — compute a deterministic state summary (inbox backlog, borderline assignments, new topic proposals, unfiled) and write `_system/kb-digest.md`. Both feed the Phase-3b scheduled pipeline.

**Architecture:** New `kb_engine/importing/` package (`import` is reserved). Things is read by **copying the DB (+ `-wal`/`-shm`) to a temp file** then opening read-only — safe while Things is running. URL extraction/normalization/source-inference reuse the schema from Phase 1 (`vault`/`config`). Inbox stubs match the KB schema the Phase-0 normalization produced. `digest` reads the store + vault and renders an idempotent markdown report into `_system/` (outside `Knowledge/`, never embedded).

**Tech Stack:** unchanged (stdlib `sqlite3`, `python-frontmatter`, `re`). No new deps.

## Testing strategy
`import-things` is unit-tested against a **fixture Things SQLite** (minimal `TMTask`/`TMArea` schema + sample rows) built in `tmp_path` — no dependency on the real app. Inbox writing + dedup tested in a tmp vault. `digest` tested with a seeded store + tmp vault. All deterministic. Coverage ≥80%.

## Things schema (grounded against the real DB)
`TMTask(type INTEGER, status INTEGER, trashed INTEGER, title TEXT, notes TEXT, area TEXT→TMArea.uuid, project TEXT→TMTask.uuid, ...)`; `TMArea(uuid, title)`. Relevant filter: `trashed=0 AND type=0 AND status=0` (0=open; 3=completed, 2=canceled). URLs live in `title` and/or `notes`.

## File structure (additions)
```
src/kb_engine/importing/
  __init__.py
  urls.py        # extract_urls(text), normalize_url(u), infer_source(u)
  things.py      # read_things_tasks(db_path, status, areas, projects) -> list[ThingsTask]
  inbox.py       # existing_urls(vault), write_inbox_stub(...), import_urls(...) (dedup+write)
  digest.py      # build_digest(store, vault) -> text ; write to _system/kb-digest.md
cli.py           # + import-things, + digest
tests/ test_urls.py test_things_import.py test_inbox.py test_digest.py
```

---

### Task 1: URL helpers

**Files:** `importing/__init__.py`, `importing/urls.py`, `tests/test_urls.py`

- [ ] **Step 1: Failing tests**
```python
from kb_engine.importing.urls import extract_urls, normalize_url, infer_source

def test_extract_urls_from_mixed_text():
    assert extract_urls("read https://x.com/a/status/1 and http://b.org/p") == \
        ["https://x.com/a/status/1", "http://b.org/p"]
    assert extract_urls("no links here") == []

def test_normalize_url_strips_tracking_and_trailing_slash():
    assert normalize_url("https://e.com/p/?utm_source=x#frag") == "https://e.com/p"
    assert normalize_url("https://e.com/p") == "https://e.com/p"

def test_infer_source():
    assert infer_source("https://github.com/a/b") == "github"
    assert infer_source("https://x.com/u/status/1") == "tweet"
    assert infer_source("https://example.com/post") == "article"
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `extract_urls(text)` (regex `https?://[^\s)>\]]+`, strip trailing punctuation `.,;)`); `normalize_url` (drop `utm_*`/`fbclid` query params + `#fragment`, strip trailing `/`); `infer_source(url)` (host table from Phase-1 schema: github/tweet/youtube/paper/newsletter/podcast/article).
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): URL extraction/normalize/source helpers`

---

### Task 2: Things reader (fixture-tested)

**Files:** `importing/things.py`, `tests/test_things_import.py`

- [ ] **Step 1: Failing test** — build a fixture Things DB
```python
import sqlite3
from kb_engine.importing.things import read_things_tasks, ThingsTask

def _fixture_things(tmp_path):
    db = tmp_path/"main.sqlite"; c = sqlite3.connect(db)
    c.executescript('''
      CREATE TABLE TMArea(uuid TEXT, title TEXT);
      CREATE TABLE TMTask(type INT, status INT, trashed INT, title TEXT, notes TEXT, area TEXT, project TEXT);
      INSERT INTO TMArea VALUES('A1','Reading');
      INSERT INTO TMTask VALUES(0,0,0,'Cool article','see https://e.com/p','A1',NULL);   -- open, url in notes
      INSERT INTO TMTask VALUES(0,0,0,'https://github.com/a/b',NULL,NULL,NULL);          -- open, url in title
      INSERT INTO TMTask VALUES(0,3,0,'done link','https://done.com',NULL,NULL);          -- completed → excluded
      INSERT INTO TMTask VALUES(0,0,1,'trashed','https://t.com',NULL,NULL);               -- trashed → excluded
      INSERT INTO TMTask VALUES(0,0,0,'no url task','just text',NULL,NULL);               -- no url → excluded
      INSERT INTO TMTask VALUES(1,0,0,'a project','https://proj.com',NULL,NULL);          -- type=project → excluded
    ''')
    c.commit(); c.close(); return db

def test_read_things_open_url_tasks(tmp_path):
    tasks = read_things_tasks(_fixture_things(tmp_path), status="open")
    urls = sorted(u for t in tasks for u in t.urls)
    assert urls == ["https://e.com/p", "https://github.com/a/b"]   # only open + url-bearing + type=0 + untrashed
    assert any(t.area == "Reading" for t in tasks)

def test_read_things_area_filter(tmp_path):
    tasks = read_things_tasks(_fixture_things(tmp_path), status="open", areas=["Reading"])
    assert all(t.area == "Reading" for t in tasks) and len(tasks) == 1
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `ThingsTask(title, notes, area, project, urls)` (frozen; `urls` = tuple from `extract_urls(title)+extract_urls(notes)`). `read_things_tasks(db_path, status="open", areas=None, projects=None) -> list[ThingsTask]`:
  - **Copy** `db_path` (+ `-wal`/`-shm` if present) to a temp file, open `sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)` (safe while Things runs); always clean up the temp copy.
  - Query `type=0 AND trashed=0`, status filter (`open`→`status=0`, `completed`→`3`, `all`→no filter); join `TMArea` for area title; resolve project title via self-join. Keep only tasks with ≥1 extracted URL. Apply area/project name filters if given.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): Things SQLite reader (read-only, fixture-tested)`

---

### Task 3: Inbox dedup + stub writer

**Files:** `importing/inbox.py`, `tests/test_inbox.py`

- [ ] **Step 1: Failing tests**
```python
from kb_engine.importing.inbox import existing_urls, import_urls

def test_existing_urls_scans_vault(tmp_path):
    k = tmp_path/"Knowledge"; (k/"inbox").mkdir(parents=True)
    (k/"a.md").write_text("---\ntitle: A\nurl: https://e.com/p\n---\nbody")
    assert "https://e.com/p" in existing_urls(tmp_path)

def test_import_urls_writes_stubs_and_dedups(tmp_path):
    (tmp_path/"Knowledge"/"inbox").mkdir(parents=True)
    (tmp_path/"Knowledge"/"a.md").write_text("---\ntitle: A\nurl: https://dup.com/x\n---\nb")
    items = [("https://new.com/p","New Title"), ("https://dup.com/x","Dup"),
             ("https://new.com/p","New again")]   # 2nd is existing, 3rd is in-batch dup
    res = import_urls(tmp_path, items)
    assert res.written == 1 and res.skipped_existing == 1 and res.skipped_dup_in_batch == 1
    import frontmatter, glob
    stub = glob.glob(str(tmp_path/"Knowledge"/"inbox"/"*.md"))[0]
    fm = frontmatter.load(stub)
    assert fm["url"] == "https://new.com/p" and fm["status"] == "inbox" and fm["source"] == "article"
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `existing_urls(vault) -> set[str]` (normalize_url over all `Knowledge/**/*.md` frontmatter `url`); `import_urls(vault, items, date_added=None) -> ImportResult(written, skipped_existing, skipped_dup_in_batch)`:
  - For each `(url, title)`: `n = normalize_url(url)`; skip if in `existing_urls` (→skipped_existing) or already seen this batch (→skipped_dup_in_batch); else write a stub to `Knowledge/inbox/<slug>.md` (slug from title or url path, dedupe filename with `-N`) with frontmatter `{title, url:n, source:infer_source(n), date_added (passed or "" — caller stamps), summary:"", status:"inbox", context:"Imported from Things", tags:[]}` and body `## Notes\n\nPending processing.`. (Date is injected by the caller, not computed in-engine, to keep it deterministic/testable.)
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): inbox stub writer + URL dedup`

---

### Task 4: `import-things` CLI

**Files:** `cli.py`, `tests/test_cli.py`

- [ ] **Step 1: Failing test** — point `--things-db` at a fixture, assert dry-run reports counts and real run writes stubs.
- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `import-things [--things-db PATH] [--status open|completed|all] [--area NAME (repeatable)] [--project NAME (repeatable)] [--date YYYY-MM-DD] [--dry-run] [--json]`:
  - Default `--things-db` = the standard path glob `~/Library/Group Containers/*ThingsMac*/**/main.sqlite` (first match); error clearly if not found.
  - `read_things_tasks` → flatten to `(url, title)` items (title = task title, or the URL if title is itself a URL) → `--dry-run` reports `{n_tasks, n_urls, would_write, would_skip_existing}` + a small sample, **without writing**; else `import_urls` (stamping `--date` or today via the CLI, not the engine core) and report `{written, skipped_existing, skipped_dup_in_batch}`.
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): import-things CLI (dry-run default-safe)`

---

### Task 5: `digest`

**Files:** `importing/digest.py`, `cli.py`, `tests/test_digest.py`

- [ ] **Step 1: Failing test**
```python
def test_build_digest_reports_state(tmp_path):
    # seed: store with 1 proposed topic + some members; vault with N inbox stubs
    ...
    from kb_engine.importing.digest import build_digest
    text = build_digest(store, vault_path=tmp_path, inbox_count=5, unfiled=["Knowledge/x.md"])
    assert "Inbox" in text and "5" in text
    assert "proposed" in text.lower()
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** `build_digest(store, vault_path, inbox_count, unfiled) -> str` — a deterministic markdown report: inbox backlog count, # `discovered`/`proposed` topics awaiting naming/approval (from `load_topics`), # topics, # areas, unfiled count, and a "needs review" checklist. No timestamps in the body (idempotent); a `generated_for` date is passed in by the caller if wanted. CLI `digest [--json]` writes `<vault>/_system/kb-digest.md` and prints a one-line summary (or JSON `{inbox, proposals, topics, areas, unfiled, digest_path}`).
- [ ] **Step 4: Run → pass; commit** `feat(kb-engine): deterministic digest report`

---

### Task 6: Coverage + README + real dry-run

- [ ] **Step 1:** `uv run pytest --cov`; ≥80% on `urls`/`things`/`inbox`/`digest`. Edge tests: Things DB missing, task with multiple URLs (multiple stubs), filename collision suffixing, empty digest.
- [ ] **Step 2:** README — "Importing from Things" + "Digest" sections; document `import-things` flags + that it's dry-run-reportable and dedups; note the open-tasks default.
- [ ] **Step 3:** Real **dry-run** against the actual Things DB (READ-ONLY, writes nothing):
  ```bash
  cd kb-engine && uv run kb-engine --vault "<Main>" import-things --status open --dry-run --json
  ```
  Report the real counts (expected ~435 open URL tasks; how many would be new vs already in the KB). Do NOT do a real write-import in this task — that's a deliberate, separately-reported step.
- [ ] **Step 4: Commit** `test(kb-engine): 3a coverage + README + real dry-run`

## Self-review
- **Spec coverage (§7.1):** Things local extraction ✓ (T2), URL normalize + content-hash/URL dedup ✓ (T1,T3), proper-schema inbox stubs ✓ (T3), dry-run-safe ✓ (T4), filterable (open default, area/project) ✓. The scheduled pipeline + review flow = **3b**.
- **Safety:** Things DB opened read-only via temp copy; `import-things` dry-run by default-reportable; real writes only land in `inbox/` (reviewable stubs).
- **Determinism:** dates injected by the CLI layer, not the engine core, so all logic is unit-testable.
- **No placeholders / type consistency:** `ThingsTask`, `read_things_tasks`, `existing_urls`, `import_urls`/`ImportResult`, `build_digest` consistent across tasks.
```
