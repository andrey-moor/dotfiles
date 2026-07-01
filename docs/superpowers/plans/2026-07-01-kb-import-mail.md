# KB `import-mail` — Email Capture Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `kb-engine import-mail`, an engine-native email capture channel that ingests `Knowledge Base`-labeled Fastmail newsletters over JMAP into `Knowledge/inbox/` **body-notes**, deduped by canonical URL + Message-ID.

**Architecture:** A new `importing/mail.py` (JMAP reader + transform) and `importing/mail_notes.py` (body-note writer), wired by an `import-mail` CLI command — mirroring the existing `importing/things.py` + `import_urls` + `import-things` pattern. The deterministic core stays offline/testable: `httpx` (JMAP) and `markdownify` (HTML→Markdown) live behind a new optional `[mail]` extra and are lazy-imported; the tested logic runs against an **injected JMAP call executor** and JSON fixtures, never the network. Read-only Fastmail token → dedup via a `message_id` frontmatter field (no Fastmail writes / label swaps).

**Tech stack:** Python `kb_engine`; JMAP over `httpx`; `markdownify` for HTML→Markdown (both behind `[mail]`, lazy). Tests: pytest, network-free.

**Working dir for all commands:** `/Users/andreym/Documents/dotfiles/kb-engine` (run `uv run pytest -q` there). Branch: `feat/kb-capture-cowork-topics`. Spec: `docs/superpowers/specs/2026-06-19-kb-capture-cowork-rich-topics-design.md` (Capture front doors → Email).

## Global constraints
- **Offline/deterministic core:** no real network or `now()` in tested functions. The JMAP call executor is injectable; `date_added` is caller-stamped (mirrors `import_urls`).
- **Least privilege:** read-only Fastmail token. Dedup by `message_id` persisted in note frontmatter — no Fastmail mutations / label swaps.
- **Nothing lost / no silent guess:** every labeled message becomes a note (or a *reported* dedup skip). A message with no canonical URL still becomes a note keyed by `url: mail:<message-id>` so it stays reachable + dedupable.
- **Uniform channel contract:** reuse `existing_urls` / `normalize_url` and the shared `importing/notes.py` helpers; the `import-mail` CLI mirrors `import-things` (`--json` / `pass_obj` Config / shared `_emit`).
- **Secret handling:** token from `FASTMAIL_API_TOKEN` env (sourced from 1Password/Nix in ops); never hardcoded or committed; validated-present at command start; never logged.

## Inbox note schema for email (superset of the clip schema)
`title` (subject), `url` (canonical URL, else `mail:<message-id>`), `source` (`infer_source(url)` else `newsletter`), `date_added` (caller-stamped), `summary` (empty), `status: inbox`, `context` (`Email · <sender>`), `tags: []`, `message_id`, `list_id` (or omitted), `why` (empty — review backfill), `project` (empty). Body = the HTML→Markdown email content (not a stub).

## File structure
| File | Task | Responsibility |
|------|------|----------------|
| `src/kb_engine/importing/notes.py` (new) | 1 | Shared note-writing primitives `slug_for`, `next_free_path` (extracted from `inbox.py`; DRY across channels) |
| `src/kb_engine/importing/inbox.py` (modify) | 1 | Use the shared helpers (no behavior change) |
| `pyproject.toml` (modify) | 2 | `[mail]` optional extra: `httpx`, `markdownify` |
| `src/kb_engine/importing/mail.py` (new) | 2,3 | JMAP reader `fetch_labeled` → `MailMessage`; transforms `canonical_url`, `body_markdown` |
| `src/kb_engine/importing/mail_notes.py` (new) | 4 | `import_mail(vault, messages, date_added)` → body-notes + url/msgid dedup |
| `src/kb_engine/cli.py` (modify) | 5 | `import-mail` command |
| `capture/README-import-mail.md` (new) | 5 | Ops: token, label, secret storage, run |
| `tests/importing/test_*` | each | unit tests (fixtures, no network) |

**Who does what:** all tasks are assistant-built + unit-tested with fixtures (no token needed). A live end-to-end run awaits the token being minted into 1Password/Nix (a separate ops step) and is exercised by an env-gated integration check (Task 5, Step 6).

---

## Task 1: Extract shared note-writing helpers (`importing/notes.py`)

**Files:**
- Create: `src/kb_engine/importing/notes.py`
- Modify: `src/kb_engine/importing/inbox.py` (import from `notes`, drop the local copies)
- Test: `tests/importing/test_notes.py`

**Interfaces (moved verbatim from `inbox.py`, made public):**
```python
# src/kb_engine/importing/notes.py
"""Shared note-writing primitives used by every capture channel (DRY)."""

from pathlib import Path

from kb_engine.topics.labeling import slugify

INBOX_RELDIR = "Knowledge/inbox"
_FALLBACK_SLUG = "untitled"


def slug_for(title: str, url: str) -> str:
    """Slug from the title; fall back to the URL path, then a constant.

    A title that is itself a URL carries no naming signal, so it is treated as
    absent and the URL path is used instead.
    """
    from urllib.parse import urlsplit

    if title.strip().lower().startswith(("http://", "https://")):
        slug = ""
    else:
        slug = slugify(title)
    if not slug:
        parts = urlsplit(url)
        slug = slugify(parts.path.strip("/")) or slugify(parts.hostname or "")
    return slug or _FALLBACK_SLUG


def next_free_path(inbox_dir: Path, slug: str, taken: set[str]) -> Path:
    """Return ``<slug>.md`` if free, else ``<slug>-2.md``, ``<slug>-3.md``, …."""
    candidate = slug
    if candidate in taken or (inbox_dir / f"{candidate}.md").exists():
        suffix = 2
        while f"{slug}-{suffix}" in taken or (inbox_dir / f"{slug}-{suffix}.md").exists():
            suffix += 1
        candidate = f"{slug}-{suffix}"
    taken.add(candidate)
    return inbox_dir / f"{candidate}.md"
```

- [ ] **Step 1: Write the failing test**
```python
# tests/importing/test_notes.py
from pathlib import Path

from kb_engine.importing.notes import slug_for, next_free_path


def test_slug_for_prefers_title():
    assert slug_for("Rust Macros", "https://example.com/x") == "rust-macros"


def test_slug_for_falls_back_to_url_path_when_title_is_a_url():
    assert slug_for("https://example.com/cool-post", "https://example.com/cool-post") == "cool-post"


def test_next_free_path_disambiguates(tmp_path):
    taken: set[str] = set()
    p1 = next_free_path(tmp_path, "a", taken)
    p1.write_text("x")
    p2 = next_free_path(tmp_path, "a", taken)
    assert p1.name == "a.md" and p2.name == "a-2.md"
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/importing/test_notes.py -v` → FAIL (`No module named 'kb_engine.importing.notes'`).

- [ ] **Step 3: Implement** — create `notes.py` as above. Then in `inbox.py`: `from kb_engine.importing.notes import slug_for, next_free_path`, delete the local `_slug_for` / `_next_free_path` / `_slug_from_url` / `_FALLBACK_SLUG`, and replace calls `_slug_for(...)`→`slug_for(...)`, `_next_free_path(...)`→`next_free_path(...)`.

- [ ] **Step 4: Run to verify** — `uv run pytest tests/importing/test_notes.py -q` → PASS, then the **full suite** `uv run pytest -q` (inbox tests still green — behavior unchanged).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "refactor(kb-engine): extract shared note helpers (importing/notes.py)"`

---

## Task 2: JMAP reader — `fetch_labeled` → `MailMessage`

**Files:**
- Modify: `pyproject.toml` (add `[mail]` extra)
- Create: `src/kb_engine/importing/mail.py`
- Test: `tests/importing/test_mail_reader.py`

**Interfaces:**
```python
# src/kb_engine/importing/mail.py
"""Fetch `Knowledge Base`-labeled mail over JMAP → MailMessage, and transform
the body. httpx/markdownify are lazy (optional [mail] extra); the reader logic
runs against an injected JMAP call executor so tests need no network."""

from collections.abc import Callable
from dataclasses import dataclass

CORE = "urn:ietf:params:jmap:core"
MAIL = "urn:ietf:params:jmap:mail"

# A JMAP "call": methodCalls -> methodResponses (the wire shape from the spike).
Call = Callable[[list], list]


@dataclass(frozen=True)
class MailMessage:
    message_id: str
    subject: str
    sender: str            # from[0].email ("" if absent)
    list_id: str | None
    received_at: str
    text_body: str
    html_body: str | None


def fetch_labeled(call: Call, account_id: str, label: str, limit: int) -> list[MailMessage]:
    """Resolve the mailbox named `label`, query the `limit` newest messages, and
    return them as MailMessage. Raises ValueError if the label mailbox is absent."""
    mboxes = call([["Mailbox/get", {"accountId": account_id, "properties": ["id", "name"]}, "0"]])[0][1]["list"]
    match = [m for m in mboxes if m["name"].lower() == label.lower()]
    if not match:
        raise ValueError(f"no Fastmail label named {label!r}")
    mailbox_id = match[0]["id"]
    responses = call([
        ["Email/query", {"accountId": account_id, "filter": {"inMailbox": mailbox_id},
                         "sort": [{"property": "receivedAt", "isAscending": False}], "limit": limit}, "0"],
        ["Email/get", {"accountId": account_id,
                       "#ids": {"resultOf": "0", "name": "Email/query", "path": "/ids"},
                       "properties": ["subject", "from", "receivedAt", "messageId",
                                      "textBody", "htmlBody", "bodyValues", "header:List-Id:asText"],
                       "fetchTextBodyValues": True, "fetchHTMLBodyValues": True}, "1"],
    ])
    return [_to_message(e) for e in responses[1][1]["list"]]


def _part_text(email: dict, part_list_key: str) -> str | None:
    """Join the bodyValues referenced by textBody/htmlBody; None if none."""
    values = email.get("bodyValues") or {}
    parts = email.get(part_list_key) or []
    chunks = [values[p["partId"]]["value"] for p in parts if p.get("partId") in values]
    return "\n".join(chunks) if chunks else None


def _to_message(email: dict) -> MailMessage:
    return MailMessage(
        message_id=(email.get("messageId") or [""])[0] or "",
        subject=email.get("subject") or "",
        sender=(email.get("from") or [{}])[0].get("email", ""),
        list_id=email.get("header:List-Id:asText"),
        received_at=email.get("receivedAt") or "",
        text_body=_part_text(email, "textBody") or "",
        html_body=_part_text(email, "htmlBody"),
    )
```

- [ ] **Step 1: Write the failing test** (a fake `call` returns fixture JMAP responses):
```python
# tests/importing/test_mail_reader.py
from kb_engine.importing.mail import fetch_labeled, MailMessage


def _fake_call(responses_by_method):
    def call(method_calls):
        return [[mc[0], responses_by_method[mc[0]], mc[2]] for mc in method_calls]
    return call


def test_fetch_labeled_parses_messages():
    call = _fake_call({
        "Mailbox/get": {"list": [{"id": "MB1", "name": "Knowledge Base"}, {"id": "MB2", "name": "Inbox"}]},
        "Email/query": {"ids": ["E1"]},
        "Email/get": {"list": [{
            "messageId": ["m-1@substack.com"], "subject": "Deep Dive",
            "from": [{"email": "peteryang@substack.com"}], "receivedAt": "2026-07-01T00:00:00Z",
            "header:List-Id:asText": "<peteryang.substack.com>",
            "textBody": [{"partId": "1"}], "htmlBody": [{"partId": "2"}],
            "bodyValues": {"1": {"value": "plain body"}, "2": {"value": "<p>rich body</p>"}},
        }]},
    })
    msgs = fetch_labeled(call, "acct", "Knowledge Base", 5)
    assert msgs == [MailMessage(
        message_id="m-1@substack.com", subject="Deep Dive", sender="peteryang@substack.com",
        list_id="<peteryang.substack.com>", received_at="2026-07-01T00:00:00Z",
        text_body="plain body", html_body="<p>rich body</p>",
    )]


def test_fetch_labeled_missing_label_raises():
    call = _fake_call({"Mailbox/get": {"list": [{"id": "MB2", "name": "Inbox"}]}})
    try:
        fetch_labeled(call, "acct", "Knowledge Base", 5)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "Knowledge Base" in str(e)
```
Note: the fake `call` ignores back-references and just maps each method name to a canned result — enough to exercise parsing.

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/importing/test_mail_reader.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement** `mail.py` (reader portion above). Add to `pyproject.toml` under `[project.optional-dependencies]`: `mail = ["httpx>=0.27", "markdownify>=0.11"]`.

- [ ] **Step 4: Run to verify** — module test PASS; `uv run pytest -q` full suite green (no `httpx`/`markdownify` imported by the reader — they're only used by the live-connect + transform helpers added next).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(kb-engine): JMAP reader for the mail capture channel"`

---

## Task 3: Transforms — `canonical_url` + `body_markdown`

**Files:**
- Modify: `src/kb_engine/importing/mail.py` (add transforms)
- Test: `tests/importing/test_mail_transform.py`

**Interfaces:**
```python
# add to src/kb_engine/importing/mail.py
import re

_SUBSTACK_CANONICAL = re.compile(r"[Vv]iew this post on the web at (https?://\S+)")


def canonical_url(msg: MailMessage) -> str | None:
    """Best-effort canonical permalink. Substack puts it near the top of the
    body as 'View this post on the web at <url>'. Returns None if not found —
    the caller then falls back to a mail:<message-id> url (nothing is lost).
    (Every wraps links in a base64 tracking redirect; decoding it is a future
    refinement — for now Every ingests body-first with no canonical URL.)"""
    m = _SUBSTACK_CANONICAL.search(msg.text_body) or (
        _SUBSTACK_CANONICAL.search(msg.html_body) if msg.html_body else None
    )
    return m.group(1).rstrip(").") if m else None


def body_markdown(msg: MailMessage) -> str:
    """The email body as Markdown: HTML→md via markdownify when an HTML part
    exists (fuller + structured), else the plain-text part verbatim."""
    if msg.html_body:
        from markdownify import markdownify  # lazy (optional [mail] extra)

        return markdownify(msg.html_body, heading_style="ATX").strip()
    return msg.text_body.strip()
```

- [ ] **Step 1: Write the failing test**
```python
# tests/importing/test_mail_transform.py
from kb_engine.importing.mail import MailMessage, canonical_url, body_markdown


def _msg(text="", html=None):
    return MailMessage("m@x", "S", "a@b.com", None, "2026-07-01T00:00:00Z", text, html)


def test_canonical_url_extracts_substack_permalink():
    msg = _msg(text="View this post on the web at https://creatoreconomy.so/p/x\n\nbody")
    assert canonical_url(msg) == "https://creatoreconomy.so/p/x"


def test_canonical_url_none_when_absent():
    assert canonical_url(_msg(text="just a body, no permalink")) is None


def test_body_markdown_converts_html():
    md = body_markdown(_msg(html="<h1>Title</h1><p>Hello <strong>world</strong></p>"))
    assert "# Title" in md and "**world**" in md


def test_body_markdown_falls_back_to_plaintext():
    assert body_markdown(_msg(text="plain only")) == "plain only"
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/importing/test_mail_transform.py -v` → FAIL.

- [ ] **Step 3: Implement** the transforms above. `test_body_markdown_converts_html` needs the extra: run these tests with `uv run --extra mail pytest tests/importing/test_mail_transform.py -q`.

- [ ] **Step 4: Run to verify** — with `--extra mail`, module tests PASS. Base suite `uv run pytest -q` stays green (markdownify import is lazy inside `body_markdown`; not touched unless an HTML test runs — the plaintext test doesn't import it).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(kb-engine): mail transforms (canonical URL + HTML→Markdown body)"`

---

## Task 4: Body-note writer — `import_mail` with url + Message-ID dedup

**Files:**
- Create: `src/kb_engine/importing/mail_notes.py`
- Test: `tests/importing/test_mail_notes.py`

**Interfaces:**
```python
# src/kb_engine/importing/mail_notes.py
"""Write Knowledge/inbox/ body-notes for fetched mail, deduped by normalized
URL (vault-wide) and by Message-ID (email notes carry a message_id field)."""

from dataclasses import dataclass
from pathlib import Path

import frontmatter

from kb_engine.importing.inbox import existing_urls
from kb_engine.importing.mail import MailMessage, body_markdown, canonical_url
from kb_engine.importing.notes import next_free_path, slug_for
from kb_engine.importing.urls import infer_source, normalize_url
from kb_engine.vault import iter_notes

_KNOWLEDGE = "Knowledge"
_INBOX = "inbox"


@dataclass(frozen=True)
class MailImportResult:
    written: int
    skipped_existing_url: int
    skipped_existing_msgid: int
    skipped_dup_in_batch: int


def existing_message_ids(vault: Path) -> set[str]:
    knowledge = Path(vault) / _KNOWLEDGE
    if not knowledge.is_dir():
        return set()
    ids: set[str] = set()
    for note in iter_notes(knowledge, base=vault):
        mid = note.frontmatter.get("message_id")
        if mid:
            ids.add(str(mid))
    return ids


def _url_for(msg: MailMessage) -> tuple[str, bool]:
    """(url, has_canonical). Canonical permalink normalized for dedup, else a
    synthetic mail:<message-id> so the note stays reachable + dedupable."""
    canon = canonical_url(msg)
    if canon:
        return normalize_url(canon), True
    return f"mail:{msg.message_id}", False


def import_mail(vault: Path, messages: list[MailMessage], date_added: str | None = None) -> MailImportResult:
    vault = Path(vault)
    inbox_dir = vault / _KNOWLEDGE / _INBOX
    inbox_dir.mkdir(parents=True, exist_ok=True)
    stamp = date_added or ""

    seen_urls = existing_urls(vault)
    seen_msgids = existing_message_ids(vault)
    batch_urls: set[str] = set()
    taken: set[str] = set()
    written = skip_url = skip_msgid = skip_batch = 0

    for msg in messages:
        if msg.message_id and msg.message_id in seen_msgids:
            skip_msgid += 1
            continue
        url, has_canon = _url_for(msg)
        if url in seen_urls:
            skip_url += 1
            continue
        if url in batch_urls:
            skip_batch += 1
            continue
        batch_urls.add(url)
        if msg.message_id:
            seen_msgids.add(msg.message_id)
        metadata = {
            "title": msg.subject or "(untitled)",
            "url": url,
            "source": infer_source(url) if has_canon else "newsletter",
            "date_added": stamp,
            "summary": "",
            "status": _INBOX,
            "context": f"Email · {msg.sender}",
            "tags": [],
            "message_id": msg.message_id,
            "why": "",
            "project": "",
        }
        if msg.list_id:
            metadata["list_id"] = msg.list_id
        path = next_free_path(inbox_dir, slug_for(msg.subject, url), taken)
        path.write_text(frontmatter.dumps(frontmatter.Post(body_markdown(msg), **metadata)) + "\n")
        written += 1

    return MailImportResult(written, skip_url, skip_msgid, skip_batch)
```

- [ ] **Step 1: Write the failing test**
```python
# tests/importing/test_mail_notes.py
from pathlib import Path

import frontmatter

from kb_engine.importing.mail import MailMessage
from kb_engine.importing.mail_notes import import_mail, existing_message_ids


def _msg(mid, subject, sender="peteryang@substack.com", text="body text", html=None):
    return MailMessage(mid, subject, sender, "<l>", "2026-07-01T00:00:00Z", text, html)


def _read(vault: Path):
    return [frontmatter.load(p) for p in sorted((vault / "Knowledge/inbox").glob("*.md"))]


def test_import_writes_body_note_with_schema(tmp_path):
    msg = _msg("m1@x", "Deep Dive", text="View this post on the web at https://creatoreconomy.so/p/x\n\nreal body")
    res = import_mail(tmp_path, [msg], date_added="2026-07-01")
    assert res.written == 1
    note = _read(tmp_path)[0]
    assert note["status"] == "inbox" and note["source"] == "newsletter"
    assert note["url"] == "https://creatoreconomy.so/p/x"
    assert note["message_id"] == "m1@x" and note["context"] == "Email · peteryang@substack.com"
    assert note["why"] == "" and "real body" in note.content


def test_no_canonical_uses_mail_scheme_url(tmp_path):
    res = import_mail(tmp_path, [_msg("m2@x", "No Link", text="just body")], date_added="2026-07-01")
    assert res.written == 1
    assert _read(tmp_path)[0]["url"] == "mail:m2@x"


def test_dedup_by_message_id(tmp_path):
    msg = _msg("dup@x", "One", text="body")
    import_mail(tmp_path, [msg], date_added="2026-07-01")
    res = import_mail(tmp_path, [msg], date_added="2026-07-02")  # same message_id already filed
    assert res.written == 0 and res.skipped_existing_msgid == 1


def test_dedup_by_url_against_existing_clip(tmp_path):
    # A web clip already carries this URL; the newsletter of the same post is a dup.
    inbox = tmp_path / "Knowledge/inbox"; inbox.mkdir(parents=True)
    (inbox / "clip.md").write_text(frontmatter.dumps(frontmatter.Post(
        "clip", title="c", url="https://creatoreconomy.so/p/x", status="inbox")) + "\n")
    msg = _msg("m3@x", "Same Post", text="View this post on the web at https://creatoreconomy.so/p/x")
    res = import_mail(tmp_path, [msg], date_added="2026-07-01")
    assert res.written == 0 and res.skipped_existing_url == 1
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/importing/test_mail_notes.py -v` → FAIL.

- [ ] **Step 3: Implement** `mail_notes.py` as above.

- [ ] **Step 4: Run to verify** — module PASS (plaintext bodies → no markdownify import needed), then `uv run pytest -q` full suite green.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(kb-engine): mail body-note writer with URL + Message-ID dedup"`

---

## Task 5: `import-mail` CLI command + live connect + ops doc

**Files:**
- Modify: `src/kb_engine/importing/mail.py` (add `connect` — the only httpx code)
- Modify: `src/kb_engine/cli.py` (add `import-mail`)
- Create: `capture/README-import-mail.md`
- Test: `tests/importing/test_mail_connect.py` (unit) + `tests/test_cli_import_mail.py` (fake-fetch smoke)

**`connect` (live JMAP session; the only real-network code, lazy httpx):**
```python
# add to src/kb_engine/importing/mail.py
def connect(token: str) -> tuple[str, "Call"]:
    """Open a JMAP session with a Fastmail API token; return (account_id, call).
    `call` posts methodCalls to the session apiUrl and returns methodResponses."""
    import httpx  # lazy (optional [mail] extra)

    client = httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30)
    session = client.get("https://api.fastmail.com/jmap/session")
    session.raise_for_status()
    data = session.json()
    api_url, account_id = data["apiUrl"], data["primaryAccounts"][MAIL]

    def call(method_calls: list) -> list:
        r = client.post(api_url, json={"using": [CORE, MAIL], "methodCalls": method_calls})
        r.raise_for_status()
        return r.json()["methodResponses"]

    return account_id, call
```

**CLI command (mirrors `import-things`; `date_added` stamped as today via `date.today()` in the glue, not a tested fn):**
```python
# in cli.py, near the other import commands
import os
from datetime import date

from kb_engine.importing.mail import connect, fetch_labeled
from kb_engine.importing.mail_notes import import_mail

DEFAULT_KB_LABEL = "Knowledge Base"
DEFAULT_MAIL_LIMIT = 50


@main.command("import-mail")
@click.option("--label", default=DEFAULT_KB_LABEL, show_default=True, help="Fastmail label to ingest.")
@click.option("--limit", default=DEFAULT_MAIL_LIMIT, show_default=True, type=int)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def import_mail_cmd(cfg: Config, label: str, limit: int, as_json: bool) -> None:
    """Ingest `<label>`-tagged newsletters from Fastmail (JMAP) into the inbox."""
    token = os.environ.get("FASTMAIL_API_TOKEN")
    if not token:
        raise click.UsageError("FASTMAIL_API_TOKEN is not set (store it in 1Password/Nix, export for the run).")
    account_id, call = connect(token)
    messages = fetch_labeled(call, account_id, label, limit)
    result = import_mail(cfg.vault_path, messages, date_added=date.today().isoformat())
    payload = {
        "fetched": len(messages),
        "written": result.written,
        "skipped_existing_url": result.skipped_existing_url,
        "skipped_existing_msgid": result.skipped_existing_msgid,
        "skipped_dup_in_batch": result.skipped_dup_in_batch,
    }
    _emit(payload, as_json,
          f"mail: fetched {len(messages)} | wrote {result.written} | "
          f"skipped url={result.skipped_existing_url} msgid={result.skipped_existing_msgid} "
          f"batch={result.skipped_dup_in_batch}")
```

- [ ] **Step 1: Write the failing tests**
```python
# tests/importing/test_mail_connect.py
from kb_engine.importing import mail


def test_connect_is_exposed():
    # Import-only contract: connect exists and is callable (network not invoked here).
    assert callable(mail.connect)
```
```python
# tests/test_cli_import_mail.py
import os

from click.testing import CliRunner

import kb_engine.cli as cli
from kb_engine.importing.mail import MailMessage


def test_import_mail_wires_fetch_to_writer(tmp_path, monkeypatch):
    monkeypatch.setenv("FASTMAIL_API_TOKEN", "tok")
    monkeypatch.setattr(cli, "connect", lambda token: ("acct", None))
    monkeypatch.setattr(cli, "fetch_labeled", lambda call, acct, label, limit: [
        MailMessage("m@x", "Hi", "a@b.com", None, "2026-07-01T00:00:00Z", "body", None)])
    result = CliRunner().invoke(cli.main, ["--vault", str(tmp_path), "import-mail", "--json"])
    assert result.exit_code == 0, result.output
    assert '"written": 1' in result.output
    assert (tmp_path / "Knowledge/inbox").exists()


def test_import_mail_requires_token(tmp_path, monkeypatch):
    monkeypatch.delenv("FASTMAIL_API_TOKEN", raising=False)
    result = CliRunner().invoke(cli.main, ["--vault", str(tmp_path), "import-mail"])
    assert result.exit_code != 0 and "FASTMAIL_API_TOKEN" in result.output
```
Confirm the `--vault` global option name against `cli.py`'s group; adjust the invoke args if the flag differs.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_cli_import_mail.py -v` → FAIL.

- [ ] **Step 3: Implement** `connect` in `mail.py` and the `import-mail` command in `cli.py` (imports at module top with the other `importing` imports).

- [ ] **Step 4: Run to verify** — `uv run pytest tests/importing/test_mail_connect.py tests/test_cli_import_mail.py -q` → PASS; full `uv run pytest -q` green.

- [ ] **Step 5: Write the ops doc** `capture/README-import-mail.md`: minting a **read-only** Fastmail API token; storing it in 1Password + exposing `FASTMAIL_API_TOKEN` via Nix for the scheduled run; the `Knowledge Base` label + allowlist rule (cross-link the spec); `uv run --extra mail kb-engine --vault "$VAULT" import-mail --json`; note it's read-only (Message-ID dedup, no label mutation) and idempotent (re-runs skip already-filed).

- [ ] **Step 6: Live smoke (manual, gated)** — with the real token exported: `uv run --extra mail kb-engine --vault "$VAULT" import-mail --limit 3 --json`, then `inbox-check --json` on the result. Record counts. (Not a CI test — requires the token; the env-gated integration check lives behind the same flag as other live checks.)

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat(kb-engine): import-mail command (JMAP email capture channel)"`

---

## Task 6: Final review + wire-up notes
- [ ] Run the whole suite: `uv run pytest -q` (all green) and `uv run --extra mail pytest -q` (mail HTML path green).
- [ ] Dispatch a final code reviewer over Tasks 1–5 (uniformity vs `import-things`, secret handling, dedup correctness, no network in tested code).
- [ ] Update `.superpowers/sdd/progress.md` (email channel: import-mail built).
- [ ] Leave the live-run/backfill (Task 5 Step 6) for when the token is in 1Password/Nix.

## Notes for the implementer
- **TDD every code task:** failing test → implement → green → commit; run `uv run pytest -q` before each commit. HTML-path tests need `--extra mail`.
- **Keep the network at the edge:** only `connect()` touches httpx; only `body_markdown()` touches markdownify — both lazy. All tested logic uses an injected `call` / fixtures.
- **Uniformity is the point:** `mail.py`+`mail_notes.py` mirror `things.py`+`inbox.py`; `import-mail` mirrors `import-things`. Reuse `existing_urls`/`normalize_url`/`slug_for`/`next_free_path` — do not reimplement.
- **Never** log/commit the token; read it from env; fail fast if absent.
- **Deferred (not this plan):** Every base64 canonical decode; per-sender footer/promo trimming; label-swap on ingest (would need a read-write token); the one-time backlog backfill.
