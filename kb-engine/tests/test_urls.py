from kb_engine.importing.urls import extract_urls, infer_source, normalize_url


def test_extract_urls_from_mixed_text():
    assert extract_urls("read https://x.com/a/status/1 and http://b.org/p") == [
        "https://x.com/a/status/1",
        "http://b.org/p",
    ]
    assert extract_urls("no links here") == []


def test_extract_urls_strips_trailing_punctuation():
    # Trailing sentence punctuation and a closing paren are not part of the URL.
    assert extract_urls("see (https://e.com/p).") == ["https://e.com/p"]
    assert extract_urls("link https://e.com/p, next") == ["https://e.com/p"]


def test_extract_urls_handles_none_and_empty():
    assert extract_urls(None) == []
    assert extract_urls("") == []


def test_normalize_url_strips_tracking_and_trailing_slash():
    assert normalize_url("https://e.com/p/?utm_source=x#frag") == "https://e.com/p"
    assert normalize_url("https://e.com/p") == "https://e.com/p"


def test_normalize_url_keeps_meaningful_query_params():
    # A non-tracking query param (e.g. a video id) is preserved.
    assert normalize_url("https://youtube.com/watch?v=abc&utm_medium=x") == (
        "https://youtube.com/watch?v=abc"
    )


def test_normalize_url_lowercases_host_only():
    # Host is case-insensitive; the path is left untouched.
    assert normalize_url("https://Example.COM/Path") == "https://example.com/Path"


def test_infer_source():
    assert infer_source("https://github.com/a/b") == "github"
    assert infer_source("https://x.com/u/status/1") == "tweet"
    assert infer_source("https://example.com/post") == "article"


def test_normalize_url_preserves_nonstandard_port():
    assert normalize_url("https://Example.com:8443/p/") == "https://example.com:8443/p"


def test_infer_source_known_hosts():
    assert infer_source("https://twitter.com/u/status/1") == "tweet"
    assert infer_source("https://www.youtube.com/watch?v=abc") == "youtube"
    assert infer_source("https://youtu.be/abc") == "youtube"
    assert infer_source("https://arxiv.org/abs/2401.00001") == "paper"
    assert infer_source("https://foo.substack.com/p/bar") == "newsletter"
    # gist.github.com resolves to github via the github.com suffix match
    assert infer_source("https://gist.github.com/x/y") == "github"
