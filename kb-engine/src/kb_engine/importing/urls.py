"""URL extraction, normalization, and source inference.

Pure functions, no I/O — shared by the Things reader and the inbox writer. The
source table mirrors the Phase-1 normalization schema (github/tweet/youtube/
paper/newsletter/podcast/article).
"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# A URL runs until whitespace or a closing bracket; trailing sentence
# punctuation is trimmed separately (it is usually not part of the link).
_URL_RE = re.compile(r"https?://[^\s)>\]]+")
_TRAILING_PUNCT = ".,;:!?)]}>\"'"

# Query params that only track provenance and carry no addressing meaning.
_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref_src",
    }
)

# Host suffix -> source kind. Checked longest-suffix-first so "youtu.be" and
# "x.com" don't shadow each other. ".substack.com" matches any subdomain.
_SOURCE_BY_HOST_SUFFIX: tuple[tuple[str, str], ...] = (
    ("github.com", "github"),
    ("gist.github.com", "github"),
    ("twitter.com", "tweet"),
    ("x.com", "tweet"),
    ("nitter.net", "tweet"),
    ("youtube.com", "youtube"),
    ("youtu.be", "youtube"),
    ("arxiv.org", "paper"),
    ("aclanthology.org", "paper"),
    ("openreview.net", "paper"),
    (".substack.com", "newsletter"),
    ("substack.com", "newsletter"),
    ("buttondown.email", "newsletter"),
    ("podcasts.apple.com", "podcast"),
    ("overcast.fm", "podcast"),
    ("pca.st", "podcast"),
)

DEFAULT_SOURCE = "article"


def extract_urls(text: str | None) -> list[str]:
    """Return http(s) URLs found in ``text``, in order, trailing punctuation stripped."""
    if not text:
        return []
    return [match.group(0).rstrip(_TRAILING_PUNCT) for match in _URL_RE.finditer(text)]


def normalize_url(url: str) -> str:
    """Canonicalize a URL for dedup.

    Lowercases the host (case-insensitive), drops tracking query params and the
    fragment, and strips a trailing slash from the path. Non-tracking query
    params (e.g. a video id) are preserved in their original order.
    """
    parts = urlsplit(url.strip())
    host = parts.hostname or ""
    netloc = host.lower()
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, netloc, path, urlencode(kept), ""))


def infer_source(url: str) -> str:
    """Classify a URL by host into a source kind (defaults to ``article``)."""
    host = (urlsplit(url).hostname or "").lower()
    for suffix, source in _SOURCE_BY_HOST_SUFFIX:
        if suffix.startswith("."):
            if host.endswith(suffix):
                return source
        elif host == suffix or host.endswith("." + suffix):
            return source
    return DEFAULT_SOURCE
