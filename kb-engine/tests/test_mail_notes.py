from pathlib import Path

import frontmatter

from kb_engine.importing.mail import MailMessage
from kb_engine.importing.mail_notes import import_mail


def _msg(mid, subject, sender="peteryang@substack.com", text="body text", html=None):
    return MailMessage(mid, subject, sender, "<l>", "2026-07-01T00:00:00Z", text, html)


def _read(vault: Path):
    return [frontmatter.load(str(p)) for p in sorted((vault / "Knowledge/inbox").glob("*.md"))]


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
    inbox = tmp_path / "Knowledge/inbox"; inbox.mkdir(parents=True)
    (inbox / "clip.md").write_text(frontmatter.dumps(frontmatter.Post(
        "clip", title="c", url="https://creatoreconomy.so/p/x", status="inbox")) + "\n")
    msg = _msg("m3@x", "Same Post", text="View this post on the web at https://creatoreconomy.so/p/x")
    res = import_mail(tmp_path, [msg], date_added="2026-07-01")
    assert res.written == 0 and res.skipped_existing_url == 1


def test_within_batch_dedup(tmp_path):
    """Two messages with the same canonical URL in one batch → written==1, skipped_dup_in_batch==1."""
    text = "View this post on the web at https://example.com/post/1\nbody"
    msg1 = _msg("id1@x", "Post One", text=text)
    msg2 = _msg("id2@x", "Post One Duplicate", text=text)
    res = import_mail(tmp_path, [msg1, msg2], date_added="2026-07-01")
    assert res.written == 1
    assert res.skipped_dup_in_batch == 1


def test_dedup_against_caller_supplied_seen(tmp_path):
    from kb_engine.importing.mail_notes import import_mail
    msg = _msg("m9@x", "Already Filed", text="View this post on the web at https://ex.com/p/z")
    res = import_mail(tmp_path, [msg], date_added="2026-07-01",
                      extra_seen_msgids=frozenset({"m9@x"}))
    assert res.written == 0 and res.skipped_existing_msgid == 1
