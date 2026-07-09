import frontmatter
import httpx
import pytest

# backfill extracts fetched HTML via trafilatura; skip when the extra is absent.
pytest.importorskip("trafilatura")

from kb_engine.backfill import backfill_candidates, backfill_content
from kb_engine.config import Config
from kb_engine.store import Store

_ARTICLE = (
    "<html><body><article><h1>Regions</h1><p>{body}</p></article></body></html>"
)


@pytest.fixture(autouse=True)
def _no_domain_spacing(monkeypatch):
    # Never sleep between same-domain fetches in tests.
    monkeypatch.setattr("kb_engine.backfill._DOMAIN_SPACING_S", 0.0)


def _cfg(tmp_path):
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    return Config(vault_path=tmp_path, db_path=tmp_path / "kb.db")


def _write(cfg, rel, text):
    p = cfg.vault_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _meta(p):
    # parse (not loads): a note with a `content` frontmatter key would crash loads.
    meta, _ = frontmatter.parse(p.read_text())
    return meta


def test_candidates_selects_stubs_only(tmp_path):
    cfg = _cfg(tmp_path)
    _write(cfg, "Knowledge/stub.md",
           "---\ntitle: Stub\nurl: https://example.com/a\nsource: article\nsummary: ''\n---\nshort")
    _write(cfg, "Knowledge/long.md",
           "---\ntitle: Long\nurl: https://example.com/b\nsource: article\n---\n" + "word " * 200)
    _write(cfg, "Knowledge/nourl.md",
           "---\ntitle: NoUrl\nsource: article\n---\nshort")
    _write(cfg, "Knowledge/tweet.md",
           "---\ntitle: Tweet\nurl: https://x.com/z\nsource: tweet\n---\nshort")
    _write(cfg, "Knowledge/dead.md",
           "---\ntitle: Dead\nurl: https://example.com/d\nsource: article\ncontent: unavailable\n---\nshort")
    _write(cfg, "Knowledge/tried.md",
           "---\ntitle: Tried\nurl: https://example.com/t\nsource: article\ncontent_attempts: 3\n---\nshort")
    _write(cfg, "Knowledge/wiki/syn.md",
           "---\ntitle: Wiki\nurl: https://example.com/w\nsource: article\n---\nshort")
    assert backfill_candidates(cfg) == ["Knowledge/stub.md"]


def test_fetch_success_appends_content_section(tmp_path):
    cfg = _cfg(tmp_path)
    p = _write(cfg, "Knowledge/stub.md",
               "---\ntitle: Stub\nurl: https://example.com/a\nsource: article\nsummary: ''\n---\nshort")
    store = Store(cfg.db_path)

    def handler(request):
        return httpx.Response(200, text=_ARTICLE.format(
            body="The full article paragraph explaining multi-region latency budgets clearly."))

    stats = backfill_content(cfg, store, client=_client(handler))
    store.close()

    assert stats.fetched == 1
    post = frontmatter.loads(p.read_text())
    assert "## Content" in post.content
    assert "full article paragraph" in post.content
    # frontmatter untouched: nothing added on success.
    assert "content_attempts" not in post.metadata
    assert "content" not in post.metadata
    assert post["title"] == "Stub" and post["url"] == "https://example.com/a"


def test_cap_and_truncation_marker(tmp_path):
    cfg = _cfg(tmp_path)
    url = "https://example.com/long"
    p = _write(cfg, "Knowledge/stub.md",
               f"---\ntitle: Stub\nurl: {url}\nsource: article\n---\nshort")
    store = Store(cfg.db_path)
    big = " ".join(f"w{i}e" for i in range(5000))  # 5000 words > 4000-word cap

    def handler(request):
        return httpx.Response(200, text=f"<html><body><article><p>{big}</p></article></body></html>")

    stats = backfill_content(cfg, store, client=_client(handler))
    store.close()

    assert stats.fetched == 1
    body = frontmatter.loads(p.read_text()).content
    assert f"…truncated — full text at {url}" in body  # marker contains the url
    assert "w3999e" in body      # 4000th word (0-indexed) kept
    assert "w4000e" not in body  # 4001st word truncated (word cap, not char cap)


def test_failure_increments_attempts_then_marks_unavailable(tmp_path):
    cfg = _cfg(tmp_path)
    p = _write(cfg, "Knowledge/stub.md",
               "---\ntitle: Stub\nurl: https://example.com/gone\nsource: article\n---\nshort")
    store = Store(cfg.db_path)
    client = _client(lambda request: httpx.Response(404))

    s1 = backfill_content(cfg, store, client=client)
    assert _meta(p)["content_attempts"] == 1
    assert s1.unavailable == 0

    s2 = backfill_content(cfg, store, client=client)
    assert _meta(p)["content_attempts"] == 2
    assert s2.unavailable == 0

    s3 = backfill_content(cfg, store, client=client)
    m = _meta(p)
    assert m["content_attempts"] == 3
    assert m["content"] == "unavailable"
    assert s3.unavailable == 1
    store.close()


def test_per_item_errors_never_abort(tmp_path):
    cfg = _cfg(tmp_path)
    _write(cfg, "Knowledge/a.md",
           "---\ntitle: A\nurl: https://bad.example.com/x\nsource: article\n---\nshort")
    p2 = _write(cfg, "Knowledge/b.md",
                "---\ntitle: B\nurl: https://good.example.com/y\nsource: article\n---\nshort")
    store = Store(cfg.db_path)

    def handler(request):
        if "bad.example.com" in str(request.url):
            raise httpx.ConnectError("boom")
        return httpx.Response(200, text=_ARTICLE.format(
            body="Good article prose about distributed systems and latency budgets."))

    stats = backfill_content(cfg, store, client=_client(handler))
    store.close()

    assert stats.failures == ("Knowledge/a.md",)  # first errored, collected not raised
    assert stats.fetched == 1                      # second still fetched
    assert "## Content" in frontmatter.loads(p2.read_text()).content
