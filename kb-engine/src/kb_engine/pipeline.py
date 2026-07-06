"""Deterministic maintenance pipeline: tiered steps, tolerant, digest-always.

Composes the already-tested engine steps into one unattended run. Each step is
isolated so one failure never kills the run; the review digest is written even
when steps fail (in a ``finally``), and every run is recorded in the ``runs``
table.

Tiers:
- ``daily``:  sync → import-mail → digest
- ``weekly``: sync → import-mail → apply-topics → discover → eval → digest

Note mutation happens only for ``active`` topics (the gated apply); everything
else is engine-cache plus a regenerable ``_system/kb-digest.md``. Safe to run
unattended (LLM-free).
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from kb_engine.config import Config
from kb_engine.embeddings import Embedder
from kb_engine.importing.digest import DigestStatus, write_digest
from kb_engine.importing.mail_notes import run_import_mail
from kb_engine.store import Store
from kb_engine.sync import sync
from kb_engine.topics.apply import apply_topic_tags
from kb_engine.topics.clustering import Clusterer
from kb_engine.topics.sticky import sticky_discover

_INBOX_RELDIR = Path("Knowledge") / "inbox"

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
    """Note paths in the store assigned to no topic, sorted."""
    all_notes = set(store.all_note_shas())
    filed = {
        member.note_path
        for topic in store.load_topics()
        for member in store.topic_members(topic.slug)
    }
    return sorted(all_notes - filed)


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


def _apply_step(cfg: Config, store: Store) -> str:
    r = apply_topic_tags(store, cfg.vault_path, only_status=_ACTIVE_ONLY)
    return (
        f"{r.n_changed} changed · {r.n_tags_added} tags added · "
        f"{len(r.skipped_missing)} missing · {len(r.skipped_outside_vault)} outside-vault"
    )


def _discover_step(cfg: Config, store: Store, clusterer: Clusterer) -> str:
    r = sticky_discover(store, clusterer)
    return (
        f"{r.n_assigned_existing} assigned · {r.n_new_topics} new topic(s) · "
        f"{r.n_unfiled} unfiled"
    )


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

    _run_step("sync", lambda: _sync_step(cfg, store, embedder), outcomes)
    _run_step("import-mail", lambda: _import_mail_step(cfg, store), outcomes)
    if tier == "weekly":
        _run_step("apply-topics", lambda: _apply_step(cfg, store), outcomes)
        _run_step("discover", lambda: _discover_step(cfg, store, clusterer), outcomes)
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
