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
