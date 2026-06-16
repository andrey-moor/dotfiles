import numpy as np
from kb_engine.embeddings import FakeEmbedder


def test_fake_embedder_is_deterministic_and_unit_dim():
    e = FakeEmbedder(dim=8)
    a1 = e.embed_passages(["hello"])[0]
    a2 = e.embed_passages(["hello"])[0]
    assert a1.shape == (8,)
    assert np.allclose(a1, a2)              # deterministic
    assert not np.allclose(a1, e.embed_passages(["world"])[0])


def test_fake_query_matches_same_text_passage_closely():
    e = FakeEmbedder(dim=16)
    p = e.embed_passages(["graph memory"])[0]
    q = e.embed_query("graph memory")
    assert float(p @ q) > 0.99             # same text → near-identical vector
