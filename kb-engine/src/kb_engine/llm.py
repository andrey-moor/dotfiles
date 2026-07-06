"""LLM adapter for descriptions: flag-gated, minimal, engine works without it.

Direct Anthropic Messages API via httpx (never Cowork/`claude` headless — D15).
Only descriptions flow through here; decisions stay human-gated (D14).
"""

import os
from typing import Protocol

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
REQUEST_TIMEOUT_S = 60.0


class LLMUnavailable(RuntimeError):
    """No API key configured — callers treat enrichment as skipped."""


class LLM(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str: ...


class FakeLLM:
    """Deterministic test double; records calls."""

    def __init__(self, reply: str = "fake summary.") -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        self.calls.append((system, user))
        return self.reply


class AnthropicLLM:
    def __init__(
        self,
        model: str = "claude-haiku-4-5-20251001",
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMUnavailable("ANTHROPIC_API_KEY not set")
        self.model = model
        self._client = httpx.Client(
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
            headers={"x-api-key": key, "anthropic-version": API_VERSION},
        )

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        resp = self._client.post(
            API_URL,
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        return "".join(
            b.get("text", "") for b in blocks if b.get("type") == "text"
        ).strip()
