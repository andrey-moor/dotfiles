import numpy as np

from kb_engine.topics.discover import build_topics


def test_build_topics_centroids_labels_and_noise():
    paths = ["Knowledge/a.md", "Knowledge/b.md", "Knowledge/c.md"]
    vecs = np.array([[1, 0], [0.9, 0.1], [0, 1]], np.float32)
    texts = {
        "Knowledge/a.md": "rust macros",
        "Knowledge/b.md": "rust borrow",
        "Knowledge/c.md": "llm prompt",
    }
    labels = np.array([0, 0, -1])  # c is noise
    topics, members, unfiled = build_topics(paths, vecs, texts, labels)
    assert len(topics) == 1  # one real cluster (label 0)
    t = topics[0]
    assert t.centroid.shape == (2,) and np.linalg.norm(t.centroid) > 0
    assert "rust" in t.keywords
    assert {m.note_path for m in members[t.slug]} == {"Knowledge/a.md", "Knowledge/b.md"}
    assert unfiled == ["Knowledge/c.md"]  # noise -> unfiled
    # member score = cosine of note vec to centroid
    assert all(0.0 <= m.score <= 1.0001 for m in members[t.slug])
