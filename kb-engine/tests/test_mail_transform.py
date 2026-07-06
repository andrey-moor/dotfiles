import pytest

from kb_engine.importing.mail import MailMessage, canonical_url, body_markdown


def _msg(text="", html=None):
    return MailMessage("m@x", "S", "a@b.com", None, "2026-07-01T00:00:00Z", text, html)


def test_canonical_url_extracts_substack_permalink():
    msg = _msg(text="View this post on the web at https://creatoreconomy.so/p/x\n\nbody")
    assert canonical_url(msg) == "https://creatoreconomy.so/p/x"


def test_canonical_url_none_when_absent():
    assert canonical_url(_msg(text="just a body, no permalink")) is None


def test_body_markdown_converts_html():
    pytest.importorskip("markdownify")
    md = body_markdown(_msg(html="<h1>Title</h1><p>Hello <strong>world</strong></p>"))
    assert "# Title" in md and "**world**" in md


def test_body_markdown_falls_back_to_plaintext():
    assert body_markdown(_msg(text="plain only")) == "plain only"


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
