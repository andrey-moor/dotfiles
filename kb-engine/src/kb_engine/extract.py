"""Shared HTML -> Markdown extraction (trafilatura), lazy-imported.

The single trafilatura call used by both the mail importer (newsletter bodies)
and backfill (fetched article pages). trafilatura is an optional dependency (the
``[mail]`` extra), so the import is lazy — the engine runs without it and each
caller decides how to handle its absence: mail falls back to plain text /
markdownify, backfill records a clean per-item failure.

Tables are excluded (``include_tables=False``): newsletter and article layouts
often wrap the whole body in a single-cell table that trafilatura would
otherwise render as a degenerate Markdown table wrapping the entire article.
"""


def html_to_markdown(html: str) -> str | None:
    """Extract the main content of ``html`` as Markdown, or ``None`` if empty.

    Lazy-imports trafilatura (optional ``[mail]`` extra) — raises ``ImportError``
    when the extra is absent, so a caller can tell "not installed" apart from
    "nothing extracted" (``None``). Returns the stripped Markdown, or ``None``
    when trafilatura extracts nothing (empty or garbage HTML).
    """
    import trafilatura  # lazy (optional [mail] extra)

    extracted = trafilatura.extract(
        html,
        output_format="markdown",
        include_links=True,
        include_images=False,
        include_tables=False,
    )
    if extracted and extracted.strip():
        return extracted.strip()
    return None
