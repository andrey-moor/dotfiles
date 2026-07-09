import pytest

# The shared extractor is trafilatura-backed; skip when the [mail] extra is absent
# (matches the mail-transform test idiom).
pytest.importorskip("trafilatura")

from kb_engine.extract import html_to_markdown

_ARTICLE = (
    "<html><body><article>"
    "<h1>Multi-Region Latency</h1>"
    "<p>The real article paragraph explains latency across regions in clear prose.</p>"
    "<p>A second substantive paragraph continues the explanation with more detail.</p>"
    "</article></body></html>"
)


def test_html_to_markdown_returns_article_text_without_table_pipes():
    md = html_to_markdown(_ARTICLE)
    assert md is not None
    assert "real article paragraph" in md
    assert "|" not in md  # tables excluded — no degenerate single-cell pipe wrapper


def test_html_to_markdown_returns_none_on_empty_or_garbage():
    assert html_to_markdown("") is None
    assert html_to_markdown("<html><body></body></html>") is None
    assert html_to_markdown("!!! not real markup at all ???") is None
