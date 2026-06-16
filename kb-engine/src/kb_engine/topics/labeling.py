import re
from collections import Counter

_SLUG_MAX_LEN = 60
_MIN_TOKEN_LEN = 3
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# A small English stopword set — enough to keep keyword labels meaningful
# without pulling in an NLP dependency.
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
        "with", "as", "by", "at", "from", "is", "are", "was", "were", "be",
        "been", "being", "this", "that", "these", "those", "it", "its", "we",
        "you", "they", "he", "she", "i", "not", "no", "do", "does", "did",
        "has", "have", "had", "can", "will", "would", "should", "could", "may",
        "might", "if", "then", "else", "than", "so", "such", "into", "out",
        "up", "down", "over", "under", "about", "via", "per",
    }
)


def slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric runs with ``-``, collapse, strip, cap length."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    slug = slug.strip("-")
    return slug[:_SLUG_MAX_LEN].strip("-")


def _tokenize(text: str) -> list[str]:
    tokens = (t.lower() for t in _TOKEN_RE.findall(text))
    return [t for t in tokens if len(t) >= _MIN_TOKEN_LEN and t not in _STOPWORDS]


def top_keywords(
    docs_by_cluster: dict[int, list[str]], n: int
) -> dict[int, tuple[str, ...]]:
    """Return the top-``n`` distinctive terms per cluster (c-TF-IDF style).

    Score = term frequency within the cluster ÷ number of clusters containing
    the term. Ties are broken by descending term frequency then term name, for
    deterministic output.
    """
    tf_by_cluster: dict[int, Counter] = {
        cluster_id: Counter(
            token for doc in docs for token in _tokenize(doc)
        )
        for cluster_id, docs in docs_by_cluster.items()
    }

    doc_freq: Counter = Counter()
    for tf in tf_by_cluster.values():
        for term in tf:
            doc_freq[term] += 1

    result: dict[int, tuple[str, ...]] = {}
    for cluster_id, tf in tf_by_cluster.items():
        scored = sorted(
            tf.items(),
            key=lambda item: (-(item[1] / doc_freq[item[0]]), -item[1], item[0]),
        )
        result[cluster_id] = tuple(term for term, _ in scored[:n])
    return result
