from kb_engine.embeddings import FakeEmbedder
from kb_engine.search import hybrid_search, rrf_fuse, semantic_search
from kb_engine.store import Store


def _store_with(tmp_path, docs):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    e = FakeEmbedder(dim=32)
    for path, txt in docs.items():
        s.upsert_note(path=path, title=path, sha256="h", tags=[])
        s.replace_chunks(path, [(0, txt, e.embed_passages([txt])[0])])
    return s, e


def test_rrf_fuse_rewards_agreement():
    sem = [("a", 0.9), ("b", 0.5)]
    kw = [("b", 10.0), ("a", 1.0)]
    fused = rrf_fuse([sem, kw], k=60)
    assert {p for p, _ in fused} == {"a", "b"}
    assert len(fused) == 2


def test_semantic_search_ranks_nearest(tmp_path):
    s, e = _store_with(
        tmp_path,
        {
            "Knowledge/mem.md": "long term memory",
            "Knowledge/rust.md": "rust macros",
        },
    )
    hits = semantic_search(s, e, "long term memory", limit=2)
    assert hits[0][0] == "Knowledge/mem.md"


def test_semantic_search_keeps_best_chunk_per_note(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    e = FakeEmbedder(dim=32)
    query_text = "graph memory"
    # Two chunks: one a near-perfect match, one unrelated. Note should appear once,
    # scored by its best chunk.
    s.upsert_note(path="Knowledge/multi.md", title="Multi", sha256="h", tags=[])
    s.replace_chunks(
        "Knowledge/multi.md",
        [
            (0, "totally unrelated rust macros", e.embed_passages(["totally unrelated rust macros"])[0]),
            (1, query_text, e.embed_passages([query_text])[0]),
        ],
    )
    hits = semantic_search(s, e, query_text, limit=5)
    paths = [p for p, _ in hits]
    assert paths.count("Knowledge/multi.md") == 1
    assert hits[0][1] > 0.99  # best (identical) chunk drives the score


def test_hybrid_search_scopes_to_knowledge_including_inbox(tmp_path):
    # Phase-3 change: inbox notes ARE returned (findability by indexing); the
    # Knowledge/ scope filter still drops paths outside Knowledge/.
    # The two in-scope notes carry DISTINCT text so the deterministic
    # FakeEmbedder gives them distinct vectors — identical text would collapse
    # to one cosine-1.0 twin under the >0.97 near-dup suppression, which is not
    # what this scoping test is exercising. Both still match the "memory" query.
    s, e = _store_with(
        tmp_path,
        {
            "Knowledge/mem.md": "long term memory for agents",
            "Knowledge/inbox/raw.md": "persistent memory recall in llm systems",
            "Other/note.md": "long term memory for agents",
        },
    )
    hits = hybrid_search(s, e, "memory", limit=10)
    paths = {p for p, _ in hits}
    assert "Knowledge/mem.md" in paths
    assert "Knowledge/inbox/raw.md" in paths
    assert "Other/note.md" not in paths


def test_hybrid_search_fuses_semantic_and_keyword(tmp_path):
    s, e = _store_with(
        tmp_path,
        {
            "Knowledge/mem.md": "long term memory for agents",
            "Knowledge/rust.md": "rust macros and traits",
        },
    )
    hits = hybrid_search(s, e, "memory", limit=10)
    assert hits and hits[0][0] == "Knowledge/mem.md"


def test_hybrid_search_suppresses_near_dup_twin(tmp_path, real_vectors):
    """Of two >0.97 twins, only the better-ranked survives; a distinct note stays."""
    twins = real_vectors.by_group("neardup:0")
    other = real_vectors.by_group("unfiled")[:1]
    store = Store(tmp_path / "t.db")
    store.init_schema()
    for path, vec in twins + other:
        scoped = f"Knowledge/{path.split('/')[-1]}"
        store.upsert_note(scoped, scoped, f"sha-{scoped}", [])
        store.replace_chunks(scoped, [(0, "shared token text", vec)])

    class OneTwinEmbedder:
        dim = 1024
        def embed_query(self, text):
            return twins[0][1]
        def embed_passages(self, texts):
            return [twins[0][1] for _ in texts]

    results = hybrid_search(store, OneTwinEmbedder(), "shared token", limit=10)
    paths = [p for p, _ in results]
    twin_hits = [p for p in paths if p in {
        f"Knowledge/{t.split('/')[-1]}" for t, _ in twins
    }]
    assert len(twin_hits) == 1, f"expected one surviving twin, got {twin_hits}"
    store.close()


def test_hybrid_search_keeps_distinct_notes(tmp_path, real_vectors):
    """Sub-threshold notes are never suppressed."""
    # by_group("topic:")[:4] would include BOTH members of the ai-agents group
    # (their cosine is 0.98 > 0.97), so one would be wrongly suppressed. Pick one
    # member from each of four distinct topic: groups so every pair is < 0.97.
    distinct = [
        real_vectors.by_group("topic:claude-code-tips")[0],
        real_vectors.by_group("topic:ai-agents")[0],
        real_vectors.by_group("topic:app-dev-mobile")[0],
        real_vectors.by_group("topic:prompt-engineering")[0],
    ]
    vecs = [v for _, v in distinct]
    assert all(
        float(vecs[i] @ vecs[j]) < 0.97
        for i in range(len(vecs))
        for j in range(i + 1, len(vecs))
    )
    store = Store(tmp_path / "t.db")
    store.init_schema()
    for path, vec in distinct:
        scoped = f"Knowledge/{path.split('/')[-1]}"
        store.upsert_note(scoped, scoped, f"sha-{scoped}", [])
        store.replace_chunks(scoped, [(0, "shared token text", vec)])

    class FirstVecEmbedder:
        dim = 1024
        def embed_query(self, text):
            return distinct[0][1]
        def embed_passages(self, texts):
            return [distinct[0][1] for _ in texts]

    results = hybrid_search(store, FirstVecEmbedder(), "shared token", limit=10)
    assert len(results) == 4
    store.close()
