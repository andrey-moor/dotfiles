from datetime import date

import numpy as np

from kb_engine.importing.digest import DigestStatus, build_digest, count_proposals
from kb_engine.models import QueueEntry, Topic, TopicMember
from kb_engine.pipeline import StepOutcome
from kb_engine.store import Store

# The pipeline passes date.today(); tests pin a fixed date so the time-based
# sections (This week, Resurfacing) render deterministically.
FIXED = date(2026, 7, 10)


def _section(text: str, name: str) -> str:
    """Return the body of the ``## <name>`` section (up to the next heading)."""
    start = text.index(f"## {name}")
    rest = text[start + len(f"## {name}"):]
    end = rest.find("\n## ")
    return rest if end == -1 else rest[:end]


def _rich_store(tmp_path):
    """A store exercising This-week, Review-queue, Resurfacing, and Synthesize."""
    s = Store(tmp_path / "rich.db")
    s.init_schema()
    s.upsert_note("Knowledge/fresh.md", "Fresh", "h", ["area/ai"],
                  summary="Fresh capture. More.", date_added="2026-07-08")
    s.upsert_note("Knowledge/old.md", "Old", "h", [], date_added="2026-01-05")
    s.replace_review_queue([QueueEntry("Knowledge/q.md", (("rag", 0.52),), "borderline")])
    s.add_manual_topic("rag", "RAG", "rag", np.ones(4, np.float32))
    s.set_members("rag", [
        TopicMember(f"Knowledge/m{i}.md", 0.9, "auto", True) for i in range(5)
    ])
    return s


# --- ## Status (kept) ---------------------------------------------------------


def test_status_header_renders_and_precedes_deterministic_body(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    status = DigestStatus(
        tier="daily",
        ok=False,
        outcomes=(
            StepOutcome("sync", False, "OSError: boom"),
            StepOutcome("import-mail", True, "skipped: no FASTMAIL_API_TOKEN"),
        ),
    )
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[],
                        status=status, today=FIXED)
    assert text.startswith("# KB Digest")
    assert "## Status" in text and "tier: daily" in text and "FAILED" in text
    assert "- sync: OSError: boom" in text
    assert "- import-mail: skipped: no FASTMAIL_API_TOKEN" in text
    assert text.index("## Status") < text.index("## This week")
    store.close()


def test_no_status_header_when_status_absent(tmp_path):
    store = Store(tmp_path / "t.db")
    store.init_schema()
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "## Status" not in text
    assert text.startswith("# KB Digest")
    store.close()


# --- determinism / today gating ----------------------------------------------


def test_body_is_deterministic_for_fixed_inputs(tmp_path):
    store = _rich_store(tmp_path)
    status = DigestStatus(
        tier="weekly", ok=True, outcomes=(StepOutcome("sync", True, "0 added"),)
    )
    a = build_digest(store, vault_path=tmp_path, inbox_count=3,
                     unfiled=["Knowledge/u.md"], status=status, today=FIXED)
    b = build_digest(store, vault_path=tmp_path, inbox_count=3,
                     unfiled=["Knowledge/u.md"], status=status, today=FIXED)
    # Only the Status timestamp is non-deterministic; everything from the first
    # deterministic heading onward is byte-identical.
    assert a[a.index("## This week"):] == b[b.index("## This week"):]
    store.close()


def test_time_sections_absent_without_today(tmp_path):
    store = _rich_store(tmp_path)
    text = build_digest(store, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "## This week" not in text
    assert "## Resurfacing" not in text
    # non-time sections still render
    assert "## Review queue" in text
    assert "## Health" in text
    assert "## Synthesize" in text
    store.close()


# --- ## This week -------------------------------------------------------------


def test_this_week_groups_recent_notes_by_area(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note("Knowledge/a.md", "A", "h", ["area/ai"],
                  summary="Alpha summary. Second sentence.", date_added="2026-07-08")
    s.upsert_note("Knowledge/b.md", "B", "h", [],
                  summary="Beta gist.", date_added="2026-07-05")
    s.upsert_note("Knowledge/old.md", "Old", "h", ["area/ai"],
                  summary="Stale.", date_added="2026-05-01")
    s.record_event("open", top_path="Knowledge/old.md")  # keep old.md out of aging
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED)
    week = _section(text, "This week")
    assert "**area/ai**" in week and "**(no area)**" in week
    assert "- [[Knowledge/a.md]] — Alpha summary" in week  # one-liner = first sentence
    assert "- [[Knowledge/b.md]] — Beta gist" in week
    assert "Knowledge/old.md" not in week  # older than a week → excluded
    assert week.index("**(no area)**") < week.index("**area/ai**")  # sorted keys
    s.close()


def test_this_week_empty_when_no_recent_captures(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note("Knowledge/old.md", "Old", "h", [], date_added="2026-01-01")
    s.record_event("open", top_path="Knowledge/old.md")  # suppress aging nudge
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED)
    assert "_Nothing new this week._" in _section(text, "This week")
    s.close()


def test_this_week_includes_boundary_excludes_older(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note("Knowledge/today.md", "T", "h", [], date_added="2026-07-10")  # delta 0
    s.upsert_note("Knowledge/day7.md", "7", "h", [], date_added="2026-07-03")   # delta 7
    s.upsert_note("Knowledge/day8.md", "8", "h", [], date_added="2026-07-02")   # delta 8
    week = _section(
        build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED),
        "This week",
    )
    assert "Knowledge/today.md" in week and "Knowledge/day7.md" in week
    assert "Knowledge/day8.md" not in week
    s.close()


# --- ## Review queue ----------------------------------------------------------


def test_review_queue_lists_top_entries_with_totals(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.replace_review_queue([
        QueueEntry("Knowledge/a.md", (("rust-learning", 0.52), ("rust-tooling", 0.47)),
                   "borderline"),
        QueueEntry("Knowledge/b.md", (("ui-design", 0.49),), "borderline"),
    ])
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "## Review queue" in text and "## Borderline queue" not in text
    assert "2 awaiting decision" in text
    assert "rust-learning (0.52)" in text
    assert text.index("Knowledge/a.md") < text.index("Knowledge/b.md")  # best first
    assert "Decide 2 borderline" not in text  # old checklist retired
    s.close()


def test_review_queue_truncates_at_ten(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.replace_review_queue([
        QueueEntry(f"Knowledge/n{i:02}.md", ((f"t{i}", 0.5),), "borderline")
        for i in range(12)
    ])
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "12 awaiting decision" in text
    assert "…and 2 more" in text
    assert text.count("] → ") == 10  # only ten entries rendered inline
    s.close()


def test_no_review_queue_section_when_empty(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "## Review queue" not in text
    assert "awaiting decision" not in text
    s.close()


# --- ## Resurfacing -----------------------------------------------------------


def test_resurfacing_surfaces_related_to_recent_work(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    for p in ("Knowledge/seed.md", "Knowledge/near.md", "Knowledge/far.md"):
        s.upsert_note(p, p, "h", [])
    s.replace_chunks("Knowledge/seed.md", [(0, "seed", np.array([1, 0, 0], np.float32))])
    s.replace_chunks("Knowledge/near.md", [(0, "near", np.array([0.98, 0.05, 0], np.float32))])
    s.replace_chunks("Knowledge/far.md", [(0, "far", np.array([0, 0, 1], np.float32))])
    s.record_event("search", query="q", top_path="Knowledge/seed.md")
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED)
    assert "## Resurfacing" in text
    assert "- [[Knowledge/near.md]] — related to what you've been working on" in text
    assert "Knowledge/seed.md" not in _section(text, "Resurfacing")  # seed excluded
    s.close()


def test_resurfacing_surfaces_oldest_unresurfaced_note(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note("Knowledge/oldest.md", "Oldest", "h", [], date_added="2026-02-01")
    s.upsert_note("Knowledge/newer.md", "Newer", "h", [], date_added="2026-04-01")
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED)
    assert "- [[Knowledge/oldest.md]] — captured 2026-02-01, never resurfaced" in text
    s.close()


def test_aging_skips_notes_already_resurfaced_in_events(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note("Knowledge/oldest.md", "Oldest", "h", [], date_added="2026-02-01")
    s.upsert_note("Knowledge/newer.md", "Newer", "h", [], date_added="2026-04-01")
    s.record_event("open", top_path="Knowledge/oldest.md")  # already resurfaced
    resurfacing = _section(
        build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED),
        "Resurfacing",
    )
    assert "captured 2026-04-01, never resurfaced" in resurfacing  # newer surfaces
    assert "Knowledge/oldest.md" not in resurfacing
    s.close()


def test_resurfacing_surfaces_one_year_anniversary(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note("Knowledge/anniv.md", "Anniv", "h", [], date_added="2025-07-10")
    s.record_event("open", top_path="Knowledge/anniv.md")  # exclude from aging
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED)
    assert "- [[Knowledge/anniv.md]] — one year ago today" in text
    s.close()


def test_anniversary_phrase_pluralizes_multiple_years(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note("Knowledge/old.md", "Old", "h", [], date_added="2023-07-10")
    s.record_event("open", top_path="Knowledge/old.md")
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED)
    assert "- [[Knowledge/old.md]] — 3 years ago today" in text
    s.close()


def test_resurfacing_section_omitted_when_no_nudges(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[], today=FIXED)
    assert "## Resurfacing" not in text
    s.close()


# --- ## Health ----------------------------------------------------------------


def test_health_line_reports_all_metrics(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.upsert_note("Knowledge/big.md", "Big", "h", ["area/ai"])
    s.upsert_note("Knowledge/small.md", "Small", "h", [])
    s.replace_chunks("Knowledge/big.md", [(0, "x" * 600, np.ones(4, np.float32))])
    s.replace_chunks("Knowledge/small.md", [(0, "y", np.ones(4, np.float32))])
    rid = s.start_run("pipeline", tier="weekly")
    s.finish_run(rid, ok=True, counts={
        "eval": "recall@5 0.80 (4/5) · MRR 0.75",
        "sync": "1 added · 0 changed · 0 deleted · 5 unchanged · 2 evicted · 0 unreadable",
    })
    text = build_digest(s, vault_path=tmp_path, inbox_count=3,
                        unfiled=["Knowledge/u1.md", "Knowledge/u2.md"])
    assert (
        "recall@5 0.80 · areas 1/2 · content 50% · inbox 3 · "
        "unfiled 2 → [[_system/topics/_unfiled-by-area]] · evicted 2"
    ) in text
    s.close()


def test_health_dashes_when_no_pipeline_run(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert (
        "recall@5 — · areas 0/0 · content 0% · inbox 0 · "
        "unfiled 0 → [[_system/topics/_unfiled-by-area]] · evicted —"
    ) in text
    s.close()


def test_health_reads_last_finished_run_not_current(tmp_path):
    # The finished run holds the real metrics; a later start_run (the in-progress
    # pipeline writing this very digest) has NULL counts. Health must read the
    # finished run, not the current unfinished one, or it renders "—" for both.
    s = Store(tmp_path / "t.db")
    s.init_schema()
    rid = s.start_run("pipeline", tier="weekly")
    s.finish_run(rid, ok=True, counts={
        "eval": "recall@5 1.00 (8/8) · MRR 0.66",
        "sync": "0 added · 0 changed · 0 deleted · 3 unchanged · 0 evicted · 0 unreadable",
    })
    s.start_run("pipeline")  # current run, still in flight (NULL counts)
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "recall@5 1.00" in text
    assert "evicted 0" in text
    assert "recall@5 —" not in text
    assert "evicted —" not in text
    s.close()


def test_health_recall_and_evicted_dash_when_absent(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    rid = s.start_run("pipeline")
    s.finish_run(rid, ok=True, counts={"eval": "skipped: no probes.yaml", "sync": "0 added"})
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "recall@5 —" in text  # eval detail has no recall@5
    assert "evicted —" in text   # sync detail has no 'N evicted'
    s.close()


# --- ## Synthesize ------------------------------------------------------------


def test_synthesize_lists_top_two_candidates(tmp_path):
    (tmp_path / "Knowledge").mkdir()
    s = Store(tmp_path / "t.db")
    s.init_schema()
    for slug, label, n in [("rag", "RAG", 7), ("agents", "Agents", 6), ("small", "Small", 5)]:
        s.add_manual_topic(slug, label, slug, np.ones(4, np.float32))
        s.set_members(slug, [
            TopicMember(f"Knowledge/{slug}{i}.md", 0.9, "auto", True) for i in range(n)
        ])
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "- /kb:synthesize rag — RAG (7 notes)" in text
    assert "- /kb:synthesize agents — Agents (6 notes)" in text
    assert "small" not in _section(text, "Synthesize")  # only the top-2 listed
    assert text.index("rag — RAG") < text.index("agents — Agents")  # biggest first
    s.close()


def test_synthesize_omitted_when_no_candidates(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    text = build_digest(s, vault_path=tmp_path, inbox_count=0, unfiled=[])
    assert "## Synthesize" not in text
    s.close()


# --- count_proposals (still exported for cli status/pipeline) ------------------


def test_count_proposals_counts_discovered_and_proposed(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    s.save_topics(
        [Topic(slug="rust", label="Rust", keywords=("rust",),
               centroid=np.array([1, 0, 0], np.float32), kind="discovered",
               status="proposed")],
        {"rust": [TopicMember("Knowledge/a.md", 0.9, "auto")]},
    )
    s.add_manual_topic("llm", "LLM", "llm", np.array([0, 1, 0], np.float32))
    assert count_proposals(s.load_topics()) == 1  # manual topic is active, not counted
    s.close()


# --- retired sections ---------------------------------------------------------


def test_retired_sections_are_gone(tmp_path):
    store = _rich_store(tmp_path)
    text = build_digest(store, vault_path=tmp_path, inbox_count=3,
                        unfiled=["Knowledge/u.md"], today=FIXED)
    assert "## Summary" not in text
    assert "## Needs review" not in text
    assert "## Unfiled notes" not in text
    assert "## Borderline queue" not in text
    assert "Inbox backlog:" not in text
    store.close()
