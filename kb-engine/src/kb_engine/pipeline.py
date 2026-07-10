"""Deterministic maintenance pipeline: tiered steps, tolerant, digest-always.

Composes the already-tested engine steps into one unattended run. Each step is
isolated so one failure never kills the run; the review digest is written even
when steps fail (in a ``finally``), and every run is recorded in the ``runs``
table.

Tiers:
- ``daily``:  import-mail → enrich → sync → digest
- ``weekly``: import-mail → enrich → backfill → sync → topics → apply-topics → areas → eval → digest

Enrichment (summaries/whys/titles) runs only when ``ANTHROPIC_API_KEY`` is set;
without it the step is a no-op skip so the pipeline stays LLM-free by default.
Note mutation is otherwise limited to ``active`` topics (the gated apply);
everything else is engine-cache plus a regenerable ``_system/kb-digest.md``.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from kb_engine.config import Config
from kb_engine.embeddings import Embedder
from kb_engine.importing.digest import DigestStatus, write_digest
from kb_engine.importing.mail_notes import run_import_mail
from kb_engine.llm import LLM
from kb_engine.store import Store
from kb_engine.sync import sync
from kb_engine.topics.apply import apply_topic_tags
from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.weekly import weekly_topic_pass

_INBOX_RELDIR = Path("Knowledge") / "inbox"
# Vault-relative POSIX prefix of synced inbox notes (store paths use "/").
_INBOX_PREFIX = _INBOX_RELDIR.as_posix() + "/"

# Unattended runs apply only approved topics; proposals stay proposed.
_ACTIVE_ONLY = ("active",)


@dataclass(frozen=True)
class StepOutcome:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PipelineResult:
    tier: str
    ok: bool
    outcomes: tuple[StepOutcome, ...]
    digest_path: Path | None


def count_inbox(vault_path: Path) -> int:
    """Number of markdown stubs in ``Knowledge/inbox/``."""
    inbox = vault_path / _INBOX_RELDIR
    if not inbox.is_dir():
        return 0
    return sum(1 for _ in inbox.glob("*.md"))


def unfiled_notes(store: Store) -> list[str]:
    """Note paths in the store assigned to no topic, sorted.

    Unfiled = filed but topicless; inbox notes are excluded — the inbox
    backlog has its own digest count.
    """
    all_notes = set(store.all_note_shas())
    filed = {
        member.note_path
        for topic in store.load_topics()
        for member in store.topic_members(topic.slug)
    }
    return sorted(
        path for path in all_notes - filed if not path.startswith(_INBOX_PREFIX)
    )


def _sync_step(cfg: Config, store: Store, embedder: Embedder) -> str:
    s = sync(cfg, store, embedder)
    return (
        f"{s.added} added · {s.changed} changed · {s.deleted} deleted · "
        f"{s.unchanged} unchanged · {s.evicted} evicted · {len(s.failures)} unreadable"
    )


def _import_mail_step(cfg: Config, store: Store) -> str:
    token = os.environ.get("FASTMAIL_API_TOKEN")
    if not token:
        return "skipped: no FASTMAIL_API_TOKEN"
    fetched, result = run_import_mail(cfg.vault_path, store, token)
    return f"{result.written} newsletter note(s) written ({fetched} fetched)"


def _enrich_step(cfg: Config) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return "skipped: no ANTHROPIC_API_KEY"
    from kb_engine.enrich import enrich_notes
    from kb_engine.llm import AnthropicLLM

    s = enrich_notes(cfg, AnthropicLLM(model=cfg.llm_model))
    return (
        f"{s.summarized} summarized · {s.whys} whys · {s.titles} titles · "
        f"{s.skipped} skipped · {len(s.failures)} failed"
    )


def _apply_step(cfg: Config, store: Store) -> str:
    r = apply_topic_tags(store, cfg.vault_path, only_status=_ACTIVE_ONLY)
    return (
        f"{r.n_changed} changed · {r.n_tags_added} tags added · "
        f"{len(r.skipped_missing)} missing · {len(r.skipped_outside_vault)} outside-vault"
    )


def _backfill_step(cfg: Config, store: Store) -> str:
    from kb_engine.backfill import backfill_content

    s = backfill_content(cfg, store)
    return f"{s.fetched} fetched · {s.unavailable} unavailable · {s.skipped} skipped"


def _topics_step(cfg: Config, store: Store, clusterer: Clusterer) -> str:
    annotate = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        from kb_engine.llm import AnthropicLLM

        annotate = _build_annotate(AnthropicLLM(model=cfg.llm_model))
    r = weekly_topic_pass(store, clusterer, annotate=annotate)
    return (
        f"{r.reanchored} reanchored · {r.thresholds_set} thresholds · "
        f"{r.assigned} assigned · {r.queued} queued · "
        f"{r.new_topics} new topic(s) · {r.unfiled} unfiled"
    )


def _build_annotate(llm: LLM) -> Callable[[str, tuple], str]:
    """LLM closure that annotates a borderline reason with the model's pick.

    The ``llm`` is injected so the caller owns key-gating (the closure is built
    only when ``ANTHROPIC_API_KEY`` is set, keeping ``weekly_topic_pass``
    LLM-free by default). The pick's score is clamped to [0, 1] before display
    (raw cosines can drift outside it). Any per-call model failure is swallowed
    and the unannotated reason is returned — a cosmetic annotation must never
    abort the topics step after its assignments have committed.
    """
    from kb_engine.topics.classify import annotate_queue_reason

    def annotate(reason: str, candidates: tuple[tuple[str, float], ...]) -> str:
        if not candidates:
            return reason
        system = (
            "Pick the single best-fitting topic slug for a borderline note. "
            "Reply with ONLY the slug."
        )
        user = "Candidates:\n" + "\n".join(f"- {slug}" for slug, _ in candidates)
        try:
            pick = llm.complete(system, user).strip()
            scores = dict(candidates)
            if pick not in scores:
                pick = candidates[0][0]
            confidence = max(0.0, min(1.0, scores[pick]))
            return annotate_queue_reason(reason, pick, confidence)
        except Exception:  # noqa: BLE001 — cosmetic annotation must not abort topics
            return reason

    return annotate


def _areas_step(cfg: Config, store: Store) -> str:
    """Weekly mop-up: classify topicless, area-less notes into a registry area.

    The LLM path is built only when a key is set (mirrors ``_enrich_step``); the
    embedding fallback always runs. Up to 5 assigned ``path→area`` pairs trail
    the counts so they surface in the digest's Status section for spot-veto.
    """
    from kb_engine.topics.classify import assign_areas

    llm = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        from kb_engine.llm import AnthropicLLM

        llm = AnthropicLLM(model=cfg.llm_model)
    s = assign_areas(cfg, store, llm)
    detail = (
        f"{s.assigned} areas assigned · {s.skipped_low_confidence} low-conf · "
        f"{s.no_signal} no-signal"
    )
    if s.assigned_paths:
        detail += " — " + ", ".join(f"{p}→{a}" for p, a in s.assigned_paths[:5])
        if len(s.assigned_paths) > 5:
            detail += " …"
    return detail


def _eval_step(cfg: Config, store: Store, embedder: Embedder) -> str:
    from kb_engine.evaluation import evaluate, load_probes
    from kb_engine.search import hybrid_search

    probes_path = cfg.vault_path / "_system" / "probes.yaml"
    if not probes_path.is_file():
        return "skipped: no probes.yaml"
    probes = load_probes(probes_path)
    ranked = [
        [p for p, _ in hybrid_search(store, embedder, probe.query, limit=5)]
        for probe in probes
    ]
    report = evaluate(ranked, probes, k=5)
    hits = sum(1 for o in report.outcomes if o.hit_rank is not None)
    return f"recall@5 {report.recall:.2f} ({hits}/{len(report.outcomes)}) · MRR {report.mrr:.2f}"


def _run_step(name: str, fn: Callable[[], str], outcomes: list[StepOutcome]) -> None:
    try:
        outcomes.append(StepOutcome(name, True, fn()))
    except Exception as exc:  # noqa: BLE001 — one step must never kill the run
        outcomes.append(StepOutcome(name, False, f"{type(exc).__name__}: {exc}"))


def run_pipeline(
    cfg: Config,
    store: Store,
    embedder: Embedder,
    clusterer: Clusterer,
    tier: str = "weekly",
) -> PipelineResult:
    """Run the tiered maintenance pipeline; write the digest even on failure.

    Every step is wrapped (a failure is captured as a ``StepOutcome`` and never
    aborts the run). The digest is written in a ``finally`` so a review entry
    always exists, and the run is recorded in the ``runs`` table regardless.
    """
    store.init_schema()
    run_id = store.start_run("pipeline", tier=tier)
    outcomes: list[StepOutcome] = []

    _run_step("import-mail", lambda: _import_mail_step(cfg, store), outcomes)
    _run_step("enrich", lambda: _enrich_step(cfg), outcomes)
    if tier == "weekly":
        # Backfill full text BEFORE sync so the appended content gets embedded.
        _run_step("backfill", lambda: _backfill_step(cfg, store), outcomes)
    _run_step("sync", lambda: _sync_step(cfg, store, embedder), outcomes)
    if tier == "weekly":
        _run_step("topics", lambda: _topics_step(cfg, store, clusterer), outcomes)
        _run_step("apply-topics", lambda: _apply_step(cfg, store), outcomes)
        _run_step("areas", lambda: _areas_step(cfg, store), outcomes)
        _run_step("eval", lambda: _eval_step(cfg, store, embedder), outcomes)

    ok = all(o.ok for o in outcomes)
    digest_path: Path | None = None
    try:
        status = DigestStatus(tier=tier, ok=ok, outcomes=tuple(outcomes))
        digest_path = write_digest(cfg, store, status=status)
    finally:
        store.finish_run(
            run_id,
            ok=ok and digest_path is not None,
            counts={o.name: o.detail for o in outcomes},
            errors=[f"{o.name}: {o.detail}" for o in outcomes if not o.ok],
        )
    return PipelineResult(
        tier=tier, ok=ok, outcomes=tuple(outcomes), digest_path=digest_path
    )
