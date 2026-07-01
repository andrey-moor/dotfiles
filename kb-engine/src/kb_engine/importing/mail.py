"""Fetch `Knowledge Base`-labeled mail over JMAP -> MailMessage, and transform
the body. httpx/markdownify are lazy (optional [mail] extra); the reader logic
runs against an injected JMAP call executor so tests need no network."""

import re
from collections.abc import Callable
from dataclasses import dataclass

CORE = "urn:ietf:params:jmap:core"
MAIL = "urn:ietf:params:jmap:mail"

_HTTP_TIMEOUT_S = 30

# A JMAP "call": methodCalls -> methodResponses (the JMAP wire shape).
Call = Callable[[list], list]


def _result(resp: list, method: str) -> dict:
    """Unwrap a JMAP method response; raise a clear error if it's an error response."""
    if resp[0] == "error":
        raise ValueError(f"JMAP {method} failed: {resp[1].get('type', 'unknown')}")
    return resp[1]


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
    mboxes = _result(call([["Mailbox/get", {"accountId": account_id, "properties": ["id", "name"]}, "0"]])[0], "Mailbox/get")["list"]
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
    return [_to_message(e) for e in _result(responses[1], "Email/get")["list"]]


def _part_text(email: dict, part_list_key: str) -> str | None:
    """Join the bodyValues referenced by textBody/htmlBody; None if none."""
    values = email.get("bodyValues") or {}
    parts = email.get(part_list_key) or []
    chunks = [values[p["partId"]]["value"] for p in parts if p.get("partId") in values]
    return "\n".join(chunks) if chunks else None


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
    """The email body as Markdown: HTML->md via markdownify when an HTML part
    exists (fuller + structured), else the plain-text part verbatim."""
    if msg.html_body:
        from markdownify import markdownify  # lazy (optional [mail] extra)

        return markdownify(msg.html_body, heading_style="ATX").strip()
    return msg.text_body.strip()


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


def connect(token: str) -> tuple[str, "Call"]:
    """Open a JMAP session with a Fastmail API token; return (account_id, call).
    `call` posts methodCalls to the session apiUrl and returns methodResponses."""
    import httpx  # lazy (optional [mail] extra)

    client = httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=_HTTP_TIMEOUT_S)
    session = client.get("https://api.fastmail.com/jmap/session")
    session.raise_for_status()
    data = session.json()
    api_url, account_id = data["apiUrl"], data["primaryAccounts"][MAIL]

    def call(method_calls: list) -> list:
        r = client.post(api_url, json={"using": [CORE, MAIL], "methodCalls": method_calls})
        r.raise_for_status()
        return r.json()["methodResponses"]

    return account_id, call
