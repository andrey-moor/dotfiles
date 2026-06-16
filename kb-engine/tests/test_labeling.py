from kb_engine.topics.labeling import slugify, top_keywords


def test_slugify():
    assert slugify("AI Agents & Tools") == "ai-agents-tools"


def test_top_keywords_finds_distinctive_terms():
    docs_by_cluster = {
        0: ["rust macros borrow checker", "rust lifetimes borrow"],
        1: ["prompt engineering llm", "llm prompting tokens"],
    }
    kw = top_keywords(docs_by_cluster, n=2)
    assert "rust" in kw[0] and "borrow" in kw[0]
    assert "llm" in kw[1] or "prompt" in kw[1]
