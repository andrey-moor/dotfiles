import json

import httpx
import pytest

from kb_engine.llm import AnthropicLLM, FakeLLM, LLMUnavailable


def test_fake_llm_records_calls_and_replies():
    llm = FakeLLM(reply="a summary")
    out = llm.complete("sys", "user text")
    assert out == "a summary"
    assert llm.calls == [("sys", "user text")]


def test_anthropic_llm_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMUnavailable):
        AnthropicLLM()


def test_anthropic_llm_request_shape_and_text_extraction(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": "first "},
                    {"type": "tool_use", "id": "x", "name": "n", "input": {}},
                    {"type": "text", "text": "second"},
                ]
            },
        )

    llm = AnthropicLLM(api_key="test-key", transport=httpx.MockTransport(handler))
    out = llm.complete("the system", "the user", max_tokens=99)
    assert out == "first second"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    p = captured["payload"]
    assert p["model"].startswith("claude-")
    assert p["max_tokens"] == 99
    assert p["system"] == "the system"
    assert p["messages"] == [{"role": "user", "content": "the user"}]


def test_anthropic_llm_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"type": "rate_limit_error"}})

    llm = AnthropicLLM(api_key="k", transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        llm.complete("s", "u")
