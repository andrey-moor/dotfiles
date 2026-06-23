"""Minimal local MCP probe: prove Cowork can call a kb-engine tool + that a Live
Artifact can refresh from it. Throwaway-grade — the production read/review MCP
is Phase 1. Vault/DB come from KB_VAULT/KB_DB env (MCP servers get no per-call
args). The ``mcp`` SDK is an optional extra; the payload functions below are
import-light and unit-tested without it.
"""

import os
from pathlib import Path

from kb_engine.config import Config
from kb_engine.embeddings import Embedder, FakeEmbedder, LocalJinaEmbedder
from kb_engine.search import hybrid_search
from kb_engine.store import Store

_DEFAULT_LIMIT = 10


def status_payload(store: Store) -> dict:
    return {"notes": store.count_notes(), "chunks": store.count_chunks()}


def search_payload(
    store: Store, embedder: Embedder, query: str, limit: int = _DEFAULT_LIMIT
) -> list[dict]:
    results = hybrid_search(store, embedder, query, limit=limit)
    return [
        {"note_path": path, "title": store.note_title(path) or path, "score": round(score, 6)}
        for path, score in results
    ]


def _config() -> Config:
    vault = Path(os.environ["KB_VAULT"])
    db = os.environ.get("KB_DB")
    return Config(vault_path=vault, db_path=Path(db) if db else None)


def _embedder(cfg: Config) -> Embedder:
    if os.environ.get("KB_FAKE_EMBED") == "1":
        return FakeEmbedder(dim=cfg.embed_dim)
    return LocalJinaEmbedder(model_name=cfg.model_name, dim=cfg.embed_dim)


def build_server():
    """Construct the FastMCP server (requires the [mcp] extra). Tools are thin
    wrappers over the tested payload functions; kb_status adds a server-edge
    timestamp so a Live Artifact visibly refreshes (not in a tested function)."""
    from datetime import datetime, timezone

    from mcp.server.fastmcp import FastMCP

    server = FastMCP("kb-engine-probe")
    cfg = _config()

    @server.tool()
    def kb_status() -> dict:
        store = Store(cfg.db_path)
        try:
            store.init_schema()
            payload = status_payload(store)
        finally:
            store.close()
        # New dict (don't mutate status_payload's return — immutability rule).
        return {**payload, "server_time": datetime.now(timezone.utc).isoformat()}

    @server.tool()
    def kb_search(query: str, limit: int = _DEFAULT_LIMIT) -> list[dict]:
        store = Store(cfg.db_path)
        try:
            store.init_schema()
            return search_payload(store, _embedder(cfg), query, limit)
        finally:
            store.close()

    return server


def main() -> None:
    build_server().run()  # stdio transport (Claude Desktop local MCP default)


if __name__ == "__main__":
    main()
