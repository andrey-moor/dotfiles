import numpy as np

from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store
from kb_engine.synthesis import synthesis_candidates


def test_candidates_are_topics_over_threshold_without_wiki(tmp_path):
    (tmp_path / "Knowledge" / "wiki").mkdir(parents=True)
    s = Store(tmp_path / "t.db")
    s.init_schema()
    # NOTE: save_topics replaces discovered each call, so seed in one call:
    big = Topic(
        slug="rag",
        label="RAG",
        keywords=("rag",),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    small = Topic(
        slug="niche",
        label="Niche",
        keywords=("niche",),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics(
        [big, small],
        {
            "rag": [TopicMember(f"Knowledge/r{i}.md", 0.9, "auto") for i in range(6)],
            "niche": [TopicMember("Knowledge/n.md", 0.9, "auto")],
        },
    )
    cands = synthesis_candidates(s, tmp_path, min_members=5)
    assert [c.slug for c in cands] == ["rag"]  # rag has 6, niche has 1


def test_existing_wiki_excludes_candidate(tmp_path):
    (tmp_path / "Knowledge" / "wiki").mkdir(parents=True)
    (tmp_path / "Knowledge" / "wiki" / "rag.md").write_text("---\ntype: wiki\n---\n# RAG")
    s = Store(tmp_path / "t.db")
    s.init_schema()
    big = Topic(
        slug="rag",
        label="RAG",
        keywords=("rag",),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    s.save_topics(
        [big],
        {"rag": [TopicMember(f"Knowledge/r{i}.md", 0.9, "auto") for i in range(6)]},
    )
    assert synthesis_candidates(s, tmp_path, min_members=5) == []  # wiki/rag.md exists
