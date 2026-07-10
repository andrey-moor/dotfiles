"""The ``pipeline`` command — run the full KB pipeline for a tier (daily/weekly)."""
import json

import click

from kb_engine.config import Config
from kb_engine.importing.digest import count_proposals
from kb_engine.pipeline import count_inbox, run_pipeline, unfiled_notes
from kb_engine.store import Store

from kb_engine.commands._shared import _build_clusterer, _build_embedder


@click.command()
@click.option(
    "--tier",
    type=click.Choice(["daily", "weekly"]),
    default="weekly",
    show_default=True,
    help="daily = import-mail + enrich + sync + digest; weekly adds apply/discover + eval.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def pipeline(cfg: Config, tier: str, as_json: bool) -> None:
    """Run the tolerant tiered maintenance pipeline; the digest is always written.

    Each step is isolated so one failure never aborts the run; the review digest
    (``_system/kb-digest.md``, with a status header) is written even on failure
    and every run is recorded. ``--tier daily`` runs import-mail → enrich → sync →
    digest; ``--tier weekly`` also applies *active* topics, clusters the residual
    into proposals, and runs a retrieval eval. Enrichment only runs with
    ``ANTHROPIC_API_KEY`` set; otherwise it skips, keeping the run LLM-free.
    """
    store = Store(cfg.db_path)
    try:
        result = run_pipeline(
            cfg, store, _build_embedder(cfg), _build_clusterer(), tier=tier
        )
        # Review-queue counts (same helpers the digest renders from) — consumed
        # by the launchd runner to size its "N to review" notification.
        counts = {
            "inbox": count_inbox(cfg.vault_path),
            "proposals": count_proposals(store.load_topics()),
            "unfiled": len(unfiled_notes(store)),
            "queue": len(store.load_review_queue()),
        }
    finally:
        store.close()

    if as_json:
        click.echo(
            json.dumps(
                {
                    "tier": result.tier,
                    "ok": result.ok,
                    "outcomes": [
                        {"name": o.name, "ok": o.ok, "detail": o.detail}
                        for o in result.outcomes
                    ],
                    "counts": counts,
                    "digest_path": (
                        str(result.digest_path) if result.digest_path else None
                    ),
                }
            )
        )
        return

    for o in result.outcomes:
        mark = "✅" if o.ok else "⚠️"
        click.echo(f"{mark} {o.name} — {o.detail}")
    state = "ok" if result.ok else "FAILED"
    digest = result.digest_path if result.digest_path is not None else "(none)"
    click.echo(f"pipeline[{result.tier}]: {state} — digest {digest}")
