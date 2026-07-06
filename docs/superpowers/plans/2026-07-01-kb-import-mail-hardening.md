# KB `import-mail` Hardening — Body Cleaning + Fast Dedup Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the two gaps the live run exposed so `import-mail` is usable on the real iCloud vault: **G1** clean newsletter body (strip email-layout tables/chrome/tracking pixels) and **G2** fast dedup (no whole-`Knowledge/` filesystem walk).

**Architecture:** G1 — `body_markdown` extracts main content via **trafilatura** (HTML→clean Markdown), falling back to text/plain then raw markdownify. G2 — the SQLite cache gains `url` + `message_id` columns populated on sync; `import-mail` dedups against the **cache (fast SQL)** unioned with a small **`Knowledge/inbox/`-only scan** (for just-written, unsynced notes), replacing the whole-`Knowledge/` walk. Read-only token preserved; no mailbox mutation.

**Tech:** `trafilatura` added to the `[mail]` extra (lazy-imported). Tests network-free (HTML fixtures; `tmp_path` DB).

**Working dir:** `/Users/andreym/Documents/dotfiles/kb-engine`. Branch: `feat/kb-capture-cowork-topics`.

**Grounding:** SQLite `notes` table today is `(path TEXT PRIMARY KEY, title, sha256, tags, summary)`. `Store.upsert_note(...)` in `src/kb_engine/store.py` (~line 103) is called by the sync path — the implementer must find that caller and thread the new fields through. `inbox.py`'s `existing_urls` normalizes with `normalize_url` on read; keep that convention.

---

## Task 1: Clean newsletter body via trafilatura (G1)

**Files:**
- Modify: `pyproject.toml` — `[mail]` extra gains `trafilatura>=1.6`.
- Modify: `src/kb_engine/importing/mail.py` — rewrite `body_markdown`.
- Test: `tests/test_mail_transform.py` — add a table-heavy fixture.

**New `body_markdown`:**
```python
def body_markdown(msg: MailMessage) -> str:
    """The email body as clean Markdown. Newsletter emails are table-based with
    tracking pixels + boilerplate, so we extract the main content with trafilatura
    (lazy, optional [mail] extra); fall back to the plain-text part, then to raw
    markdownify of the HTML."""
    if msg.html_body:
        try:
            import trafilatura  # lazy (optional [mail] extra)

            extracted = trafilatura.extract(
                msg.html_body, output_format="markdown", include_links=True, include_images=False
            )
            if extracted and extracted.strip():
                return extracted.strip()
        except Exception:
            pass  # fall through to the simpler paths
    if msg.text_body.strip():
        return msg.text_body.strip()
    if msg.html_body:
        from markdownify import markdownify

        return markdownify(msg.html_body, heading_style="ATX").strip()
    return ""
```

- [ ] **Step 1: Write the failing test** (add to `tests/test_mail_transform.py`; keep the existing tests):
```python
def test_body_markdown_strips_email_table_chrome():
    import pytest
    pytest.importorskip("trafilatura")
    html = (
        "<html><body>"
        "<img src='https://track.example/pixel.gif?token=abc'/>"
        "<table><tr><td></td><td></td></tr></table>"
        "<div><p>The real article paragraph with a clear sentence about latency.</p>"
        "<p>A second substantive paragraph explaining the architecture in detail.</p></div>"
        "<table><tr><td>Unsubscribe</td><td>Get the app</td></tr></table>"
        "</body></html>"
    )
    md = body_markdown(MailMessage("m@x", "S", "a@b.com", None, "2026-07-01T00:00:00Z", "", html))
    assert "real article paragraph" in md
    assert "|" not in md            # no leftover Markdown tables
    assert "pixel.gif" not in md    # tracking pixel stripped
```
(`_msg` in that file has no `html` slot beyond the existing helper — construct the `MailMessage` inline as above.)

- [ ] **Step 2: Run to verify it fails** — `uv run --extra mail pytest tests/test_mail_transform.py -v` → the new test FAILS (raw markdownify keeps tables/pixels).

- [ ] **Step 3: Implement** — add `trafilatura>=1.6` to the `[mail]` extra; replace `body_markdown`.

- [ ] **Step 4: Run to verify** — `uv run --extra mail pytest tests/test_mail_transform.py -q` → PASS; then base `uv run pytest -q` green (trafilatura lazy; the base suite's markdown test already `importorskip`s).

- [ ] **Step 5: Commit** — `git add pyproject.toml src/kb_engine/importing/mail.py tests/test_mail_transform.py && git commit -m "feat(kb-engine): extract clean newsletter body with trafilatura"` (if 1P is down, stage only and report).

---

## Task 2: Cache `url` + `message_id` in the store, populated on sync (G2a)

**Files:**
- Modify: `src/kb_engine/store.py` — schema (add 2 columns + migration), `upsert_note`, two query methods.
- Modify: the sync caller of `upsert_note` (find it — likely in `cli.py`'s `sync` or a `pipeline`/`indexer` module) to pass `url` + `message_id` from each note's frontmatter.
- Test: `tests/test_store_dedup.py` (new).

**Interfaces:**
- `notes` schema gains `url TEXT, message_id TEXT`. `init_schema` must add them to existing DBs too: after the `CREATE TABLE IF NOT EXISTS`, run idempotent `ALTER TABLE notes ADD COLUMN url TEXT` / `... message_id TEXT` guarded by a check of `PRAGMA table_info(notes)` (skip if present). The cache is rebuildable, so this migration only needs to not crash on an old DB.
- `Store.upsert_note(...)` gains keyword params `url: str | None = None, message_id: str | None = None` (default None so existing callers/tests keep working) and writes them.
- `Store.existing_urls() -> set[str]`: `SELECT url FROM notes WHERE url IS NOT NULL AND url != ''`, returned **normalized** via `normalize_url` (import from `kb_engine.importing.urls`) to match `inbox.py`.
- `Store.existing_message_ids() -> set[str]`: `SELECT message_id FROM notes WHERE message_id IS NOT NULL AND message_id != ''`.

- [ ] **Step 1: Write the failing test:**
```python
# tests/test_store_dedup.py
from kb_engine.store import Store


def test_store_indexes_url_and_message_id(tmp_path):
    s = Store(tmp_path / "kb.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h1", tags=[], summary="",
                  url="https://example.com/x/", message_id="m1@host")
    s.upsert_note(path="Knowledge/b.md", title="B", sha256="h2", tags=[], summary="")  # no url/msgid
    assert s.existing_urls() == {"https://example.com/x"}     # normalized (trailing slash dropped)
    assert s.existing_message_ids() == {"m1@host"}
    s.close()
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_store_dedup.py -v` → FAIL.

- [ ] **Step 3: Implement** — read `store.py`'s current `upsert_note` (match its exact existing signature/params — it currently takes `path, title, sha256, tags, summary`), add the schema columns + migration, add the two params, add the two query methods. Then find the sync caller of `upsert_note` (grep `upsert_note`) and pass `url=note.frontmatter.get("url")`, `message_id=note.frontmatter.get("message_id")` (or the equivalent for how that caller accesses frontmatter).

- [ ] **Step 4: Run to verify** — `uv run pytest tests/test_store_dedup.py -q` → PASS; full `uv run pytest -q` green (existing `upsert_note` callers still work via the defaults).

- [ ] **Step 5: Commit** — `... && git commit -m "feat(kb-engine): index url + message_id in the note cache"` (stage-only if 1P down).

---

## Task 3: `import-mail` dedups via cache + inbox scan (G2b)

**Files:**
- Modify: `src/kb_engine/importing/mail_notes.py` — drop the whole-`Knowledge/` walk; scan `inbox/` only; accept caller-supplied "seen" sets.
- Modify: `src/kb_engine/cli.py` `import_mail_cmd` — open the store, union cache sets with the inbox scan.
- Test: `tests/test_mail_notes.py` — dedup against caller-supplied seen sets.

**Interfaces:**
- Replace `existing_urls_and_msgids(vault)` (whole-Knowledge) with `inbox_urls_and_msgids(vault) -> tuple[set[str], set[str]]` that walks ONLY `vault/Knowledge/inbox/` (small, fast; same per-note frontmatter read, normalized urls).
- `import_mail(vault, messages, date_added=None, extra_seen_urls=frozenset(), extra_seen_msgids=frozenset())`: dedup set = `inbox_urls_and_msgids(vault)` unioned with the `extra_seen_*` the caller passes. Default empty extras → inbox-only dedup (keeps existing tests green: their clip/idempotency cases live in the inbox).
- `import_mail_cmd` (cli.py): open `Store(cfg.db_path)`, `extra_seen_urls = store.existing_urls()`, `extra_seen_msgids = store.existing_message_ids()`, pass to `import_mail`, close the store. (Import `Store` at module top.) Wrap store-open failures so a missing/rebuildable cache degrades to inbox-only dedup with a `log`/note rather than crashing.

- [ ] **Step 1: Write the failing test** (add to `tests/test_mail_notes.py`):
```python
def test_dedup_against_caller_supplied_seen(tmp_path):
    from kb_engine.importing.mail_notes import import_mail
    msg = _msg("m9@x", "Already Filed", text="View this post on the web at https://ex.com/p/z")
    res = import_mail(tmp_path, [msg], date_added="2026-07-01",
                      extra_seen_msgids=frozenset({"m9@x"}))
    assert res.written == 0 and res.skipped_existing_msgid == 1
```
And confirm the existing dedup tests still pass with the new signature.

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_mail_notes.py -v` → the new test FAILS.

- [ ] **Step 3: Implement** — the `inbox_urls_and_msgids` helper + the `import_mail` signature/dedup change; wire `import_mail_cmd` to supply the cache sets. Keep `existing_message_ids`/`existing_urls_and_msgids` only if still referenced; otherwise remove the now-dead whole-Knowledge helper.

- [ ] **Step 4: Run to verify** — `uv run pytest tests/test_mail_notes.py tests/test_cli_import_mail.py -q` → PASS; full `uv run pytest -q` + `uv run --extra mail pytest -q` green.

- [ ] **Step 5: Commit** — `... && git commit -m "perf(kb-engine): dedup import-mail via cache + inbox scan (no whole-vault walk)"`.

---

## Task 4: Final review + verify
- [ ] `uv run pytest -q` and `uv run --extra mail pytest -q` both green.
- [ ] Dispatch a code reviewer over Tasks 1–3 (trafilatura fallback chain; store migration correctness on an existing DB; dedup completeness = cache ∪ inbox; no whole-Knowledge walk remains; read-only preserved).
- [ ] (Manual, gated) re-run the live validation against the REAL vault: `FASTMAIL_API_TOKEN=… uv run --extra mail kb-engine --vault "$VAULT" import-mail --limit 3 --json` — confirm it completes fast (no hang) and the written note bodies are clean. (Needs the pipeline to have `sync`ed first so the cache is populated.)

## Notes for the implementer
- **Deterministic/offline tests:** no network; trafilatura runs on fixture HTML; store tests use `tmp_path`.
- **Migration safety:** the cache is rebuildable — the `ALTER TABLE` guard must not crash on either a fresh or an existing DB.
- **Dedup completeness:** cache (filed, synced notes) ∪ inbox scan (just-written, unsynced). `import-mail` should run after `sync` in the pipeline so the cache is fresh (note this; don't build auto-sync into import-mail).
- **1P may be flaky:** if `git commit` fails, `git add` the task's files and report; the controller batch-commits.
- **Deferred:** two-phase fetch (ids→dedup→bodies-for-new-only) as a later efficiency win; per-sender sponsor-block trimming.
