"""Real-model integration test for kb-engine.

Loads the actual `jinaai/jina-embeddings-v3` model and asserts that semantic
search ranks a topically-relevant note above an unrelated one — the proof that
the engine fixes the review's failing keyword query
("how do I give my AI agent persistent memory").

Skipped by default (and excluded from the default `-m 'not integration'`
addopts). Run explicitly with:

    KB_RUN_INTEGRATION=1 uv run pytest tests/test_integration_real_model.py \
        -m integration -v

Requires the `[ml]` extra (`uv sync --extra ml`).
"""

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("KB_RUN_INTEGRATION") != "1", reason="set KB_RUN_INTEGRATION=1"
)
def test_real_jina_ranks_semantically(tmp_path):
    from kb_engine.embeddings import LocalJinaEmbedder
    from kb_engine.search import semantic_search
    from kb_engine.store import Store

    embedder = LocalJinaEmbedder()
    store = Store(tmp_path / "t.db")
    store.init_schema()

    docs = {
        "Knowledge/mem.md": "giving an AI assistant long-term memory",
        "Knowledge/fan.md": "replacing a bathroom exhaust fan",
    }
    for path, text in docs.items():
        store.upsert_note(path=path, title=path, sha256="h", tags=[])
        store.replace_chunks(
            path, [(0, text, embedder.embed_passages([text])[0])]
        )

    hits = semantic_search(
        store, embedder, "how do I give my AI agent persistent memory", limit=2
    )

    # The review's failing keyword query now ranks the memory note first.
    assert hits[0][0] == "Knowledge/mem.md"
