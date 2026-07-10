"""Weekly-review KB digest (v2).

Renders ``_system/kb-digest.md`` — the artifact a human reviews. Sections, in
order: ``## Status`` (the last run, with a render-time timestamp), ``## This
week`` (fresh captures grouped by area), ``## Review queue`` (borderline notes
awaiting a topic decision), ``## Resurfacing`` (three gentle nudges toward old
notes), ``## Health`` (a one-line dashboard), and ``## Synthesize`` (wiki
candidates). Everything below ``## Status`` is deterministic for fixed inputs;
the time-based ``This week``/``Resurfacing`` sections render only when a
``today`` date is supplied, so the standalone ``digest`` command stays
timestamp-free while the pipeline passes ``date.today()``.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from kb_engine.config import Config
from kb_engine.models import Topic
from kb_engine.store import Store
from kb_engine.surface import related_to_note
from kb_engine.synthesis import synthesis_candidates
from kb_engine.topics.render import _one_liner

# Discovered topics in these statuses still need a human to name/approve them.
# (Valid statuses are proposed/active/deprecated — "discovered" is a kind, never
# a status, so it has no place here.)
_PROPOSAL_STATUSES = frozenset({"proposed"})
_MAX_QUEUE_LISTED = 10
_THIS_WEEK_DAYS = 7
_ANNIVERSARY_MIN_DAYS = 90
_RELATED_LIMIT = 10
_SEED_EVENTS = 5
_SEED_CAPTURES = 3
_SYNTH_LISTED = 2
_UNFILED_MOC = "_system/topics/_unfiled-by-area"
_DIGEST_RELPATH = Path("_system") / "kb-digest.md"


@dataclass(frozen=True)
class DigestStatus:
    """A run's outcome, rendered as the digest's leading ``## Status`` section.

    ``outcomes`` is a ``tuple[StepOutcome, ...]`` (each with ``.name``/``.ok``/
    ``.detail``) but is typed loosely as ``tuple`` here to avoid a pipeline<->digest
    import cycle.
    """

    tier: str
    ok: bool
    outcomes: tuple


def _status_section(status: DigestStatus) -> list[str]:
    """Render the leading ``## Status`` block. The timestamp is computed here at
    render time (the only non-deterministic line in the whole digest)."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    state = "✅ ok" if status.ok else "⚠️ FAILED"
    lines = [
        "## Status",
        "",
        f"- Last run: {stamp} · tier: {status.tier} · {state}",
    ]
    lines.extend(f"- {o.name}: {o.detail}" for o in status.outcomes)
    lines.append("")
    return lines


def count_proposals(topics: list[Topic]) -> int:
    """Number of discovered topics still awaiting naming/approval."""
    return sum(
        1
        for t in topics
        if t.kind == "discovered" and t.status in _PROPOSAL_STATUSES
    )


def _count_notes_with_area(store: Store) -> int:
    """Number of distinct notes carrying any ``area/*`` tag (area coverage)."""
    tagged = {
        path
        for tag, paths in store.notes_by_tag().items()
        if tag.startswith("area/")
        for path in paths
    }
    return len(tagged)


def _parse_date(raw: str) -> date | None:
    """Parse an ISO ``date_added`` string; malformed → None (treated as undated)."""
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


# --- ## This week -------------------------------------------------------------


def _areas_by_note(store: Store) -> dict[str, str]:
    """Map each note to its first ``area/*`` tag (for the This-week grouping)."""
    tags_by_note: dict[str, list[str]] = {}
    for tag, paths in store.notes_by_tag().items():
        if tag.startswith("area/"):
            for path in paths:
                tags_by_note.setdefault(path, []).append(tag)
    return {path: sorted(tags)[0] for path, tags in tags_by_note.items()}


def _recent_paths(store: Store, today: date) -> list[str]:
    """Note paths whose ``date_added`` falls within a week before ``today``."""
    return [
        path
        for path, raw in store.note_dates().items()
        if (parsed := _parse_date(raw)) is not None
        and 0 <= (today - parsed).days <= _THIS_WEEK_DAYS
    ]


def _note_line(path: str, summary: str | None) -> str:
    """``- [[path]] — one-liner`` (or link-only when the note has no summary)."""
    if summary:
        return f"- [[{path}]] — {_one_liner(summary)}"
    return f"- [[{path}]]"


def _this_week_section(store: Store, today: date) -> tuple[list[str], set[str]]:
    """Render ``## This week`` grouped by area; return (lines, this-week paths)."""
    recent = _recent_paths(store, today)
    lines = ["## This week", ""]
    if not recent:
        lines.extend(["_Nothing new this week._", ""])
        return lines, set()
    area_of = _areas_by_note(store)
    summaries = store.summaries_for(recent)
    groups: dict[str, list[str]] = {}
    for path in recent:
        groups.setdefault(area_of.get(path, "(no area)"), []).append(path)
    for key in sorted(groups):
        lines.extend([f"**{key}**", ""])
        lines.extend(_note_line(p, summaries.get(p)) for p in sorted(groups[key]))
        lines.append("")
    return lines, set(recent)


# --- ## Review queue ----------------------------------------------------------


def _review_queue_section(queue: list) -> list[str]:
    """Render ``## Review queue`` (totals line + top-10 by confidence + overflow)."""
    if not queue:
        return []
    lines = ["## Review queue", "", f"{len(queue)} awaiting decision", ""]
    for entry in queue[:_MAX_QUEUE_LISTED]:
        options = ", ".join(
            f"{slug} ({score:.2f})" for slug, score in entry.candidates
        )
        lines.append(f"- [[{entry.note_path}]] → {options}")
    if len(queue) > _MAX_QUEUE_LISTED:
        lines.append(f"- …and {len(queue) - _MAX_QUEUE_LISTED} more")
    lines.append("")
    return lines


# --- ## Resurfacing -----------------------------------------------------------


def _newest_captures(store: Store, n: int) -> list[str]:
    """The ``n`` note paths with the most recent ``date_added`` (ties by path)."""
    dated = [
        (parsed, path)
        for path, raw in store.note_dates().items()
        if (parsed := _parse_date(raw)) is not None
    ]
    dated.sort(key=lambda dp: dp[1])                 # stable: path ascending
    dated.sort(key=lambda dp: dp[0], reverse=True)   # then date descending
    return [path for _, path in dated[:n]]


def _resurface_related(store: Store, this_week: set[str], used: set[str]) -> str | None:
    """A note related to recent work (recent search hits + newest captures as seeds)."""
    seeds = list(dict.fromkeys(
        store.event_top_paths(kind="search", limit=_SEED_EVENTS)
        + _newest_captures(store, _SEED_CAPTURES)
    ))
    exclude = set(seeds) | this_week | used
    for seed in seeds:
        for hit in related_to_note(store, seed, limit=_RELATED_LIMIT):
            if hit.note_path not in exclude:
                used.add(hit.note_path)
                return f"- [[{hit.note_path}]] — related to what you've been working on"
    return None


def _resurface_aging(store: Store, used: set[str]) -> str | None:
    """The oldest dated note that has never appeared as an event top_path."""
    resurfaced = set(store.event_top_paths(kind=None, limit=None))
    candidates = [
        (parsed, raw, path)
        for path, raw in store.note_dates().items()
        if path not in resurfaced and path not in used
        and (parsed := _parse_date(raw)) is not None
    ]
    if not candidates:
        return None
    _, raw, path = min(candidates, key=lambda c: (c[0], c[2]))
    used.add(path)
    return f"- [[{path}]] — captured {raw}, never resurfaced"


def _anniversary_phrase(then: date, today: date) -> str:
    years = today.year - then.year
    return "one year ago today" if years == 1 else f"{years} years ago today"


def _resurface_anniversary(store: Store, today: date, used: set[str]) -> str | None:
    """A dated note whose month/day == today's and is ≥90 days old (oldest first)."""
    candidates = []
    for path, raw in store.note_dates().items():
        parsed = _parse_date(raw)
        if (
            path not in used
            and parsed is not None
            and parsed.month == today.month
            and parsed.day == today.day
            and (today - parsed).days >= _ANNIVERSARY_MIN_DAYS
        ):
            candidates.append((parsed, path))
    if not candidates:
        return None
    parsed, path = min(candidates, key=lambda c: (c[0], c[1]))
    used.add(path)
    return f"- [[{path}]] — {_anniversary_phrase(parsed, today)}"


def _resurfacing_section(store: Store, today: date, this_week: set[str]) -> list[str]:
    """Render ``## Resurfacing`` — up to three unique nudges; omitted when none."""
    used: set[str] = set()
    picks = [
        _resurface_related(store, this_week, used),
        _resurface_aging(store, used),
        _resurface_anniversary(store, today, used),
    ]
    lines = [line for line in picks if line]
    if not lines:
        return []
    return ["## Resurfacing", "", *lines, ""]


# --- ## Health ----------------------------------------------------------------


def _parse_metric(text: str, pattern: str) -> str:
    """First capture group of ``pattern`` in ``text``, or an em-dash when absent."""
    match = re.search(pattern, text or "")
    return match.group(1) if match else "—"


def _health_section(
    store: Store, inbox_count: int, unfiled: list[str], n_with_area: int, n_total: int
) -> list[str]:
    """Render the single-line ``## Health`` dashboard."""
    run = store.last_run("pipeline")
    counts = run["counts"] if run else {}
    recall = _parse_metric(counts.get("eval", ""), r"recall@5 ([0-9.]+)")
    evicted = _parse_metric(counts.get("sync", ""), r"(\d+) evicted")
    with_content, total = store.content_coverage()
    pct = round(100 * with_content / total) if total else 0
    line = (
        f"recall@5 {recall} · areas {n_with_area}/{n_total} · content {pct}% · "
        f"inbox {inbox_count} · unfiled {len(unfiled)} → "
        f"[[{_UNFILED_MOC}]] · evicted {evicted}"
    )
    return ["## Health", "", line, ""]


# --- ## Synthesize ------------------------------------------------------------


def _synthesize_section(store: Store, vault_path: Path) -> list[str]:
    """Render ``## Synthesize`` — the top-2 wiki candidates; omitted when none."""
    candidates = synthesis_candidates(store, vault_path)[:_SYNTH_LISTED]
    if not candidates:
        return []
    lines = ["## Synthesize", ""]
    lines.extend(
        f"- /kb:synthesize {c.slug} — {c.label} ({c.size} notes)" for c in candidates
    )
    lines.append("")
    return lines


def build_digest(
    store: Store,
    vault_path: Path,
    inbox_count: int,
    unfiled: list[str],
    status: DigestStatus | None = None,
    today: date | None = None,
) -> str:
    """Render the weekly-review digest as markdown.

    ``inbox_count`` and ``unfiled`` (topicless note paths) are computed by the
    caller so this stays pure and testable. ``status`` prepends the ``## Status``
    block (its timestamp is the only non-deterministic line). The time-based
    ``This week`` and ``Resurfacing`` sections render only when ``today`` is
    given; every other section is deterministic for fixed inputs.
    """
    n_with_area = _count_notes_with_area(store)
    n_total = store.count_notes()

    lines: list[str] = ["# KB Digest", ""]
    if status is not None:
        lines.extend(_status_section(status))
    this_week: set[str] = set()
    if today is not None:
        week_lines, this_week = _this_week_section(store, today)
        lines.extend(week_lines)
    lines.extend(_review_queue_section(store.load_review_queue()))
    if today is not None:
        lines.extend(_resurfacing_section(store, today, this_week))
    lines.extend(_health_section(store, inbox_count, unfiled, n_with_area, n_total))
    lines.extend(_synthesize_section(store, vault_path))

    return "\n".join(lines).rstrip() + "\n"


def write_digest(
    cfg: Config,
    store: Store,
    status: DigestStatus | None = None,
    today: date | None = None,
) -> Path:
    """Render the digest and write it to ``<vault>/_system/kb-digest.md``.

    The file-writing wrapper the pipeline calls. Inbox/unfiled counts come from
    the pipeline helpers, imported lazily to avoid a pipeline<->digest cycle.
    Returns the absolute path written.
    """
    from kb_engine.pipeline import count_inbox, unfiled_notes

    text = build_digest(
        store,
        vault_path=cfg.vault_path,
        inbox_count=count_inbox(cfg.vault_path),
        unfiled=unfiled_notes(store),
        status=status,
        today=today,
    )
    digest_path = cfg.vault_path / _DIGEST_RELPATH
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(text)
    return digest_path
