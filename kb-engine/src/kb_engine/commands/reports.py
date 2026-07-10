import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

import click

from kb_engine.config import Config
from kb_engine.dedup import DEFAULT_DEDUP_THRESHOLD, near_duplicates
from kb_engine.doctor import run_checks
from kb_engine.importing.digest import build_digest
from kb_engine.pipeline import count_inbox, unfiled_notes
from kb_engine.store import Store
from kb_engine.surface import related_to_note, related_to_query
from kb_engine.synthesis import synthesis_candidates

from kb_engine.commands._shared import DEFAULT_SEARCH_LIMIT, _build_embedder, _emit

DEFAULT_SYNTHESIS_MIN = 5

# count_inbox / unfiled_notes live in kb_engine.pipeline (imported above) so the
# digest command and the pipeline share one definition.
_DIGEST_RELPATH = Path("_system") / "kb-digest.md"


@click.command("synthesis-candidates")
@click.option(
    "--min",
    "min_members",
    default=DEFAULT_SYNTHESIS_MIN,
    show_default=True,
    type=int,
    help="Minimum member count for a topic to be a synthesis candidate.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def synthesis_candidates_cmd(cfg: Config, min_members: int, as_json: bool) -> None:
    """List topics with >=N members and no wiki article (synthesis targets)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate running against a never-synced DB
        cands = synthesis_candidates(store, cfg.vault_path, min_members=min_members)
        rows = [{"slug": c.slug, "label": c.label, "size": c.size} for c in cands]
    finally:
        store.close()

    if as_json:
        click.echo(json.dumps({"candidates": rows}))
        return
    if not rows:
        click.echo("No synthesis candidates.")
        return
    for row in rows:
        click.echo(f"{row['slug']}  ({row['size']} notes)  {row['label']}")


@click.command("dedup-report")
@click.option(
    "--threshold",
    default=DEFAULT_DEDUP_THRESHOLD,
    show_default=True,
    type=float,
    help="Min cosine for a pair to count as a near-duplicate.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def dedup_report(cfg: Config, threshold: float, as_json: bool) -> None:
    """Report near-duplicate note pairs (gist-vector cosine >= threshold).

    Read-only. Merging is a human decision — see /kb:review's merge flow."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        pairs = near_duplicates(store, threshold=threshold)
    finally:
        store.close()
    if as_json:
        click.echo(json.dumps({
            "threshold": threshold,
            "pairs": [
                {"a": p.a, "b": p.b, "cosine": round(p.cosine, 6)} for p in pairs
            ],
        }))
        return
    if not pairs:
        click.echo(f"No pairs >= {threshold}.")
        return
    for p in pairs:
        click.echo(f"{p.cosine:.4f}  {p.a}  <->  {p.b}")
    click.echo(f"{len(pairs)} pair(s) >= {threshold}")


@click.command()
@click.option("--query", "query", default=None, help="Free-text context to surface notes for.")
@click.option(
    "--to",
    "to_note",
    default=None,
    help="Vault-relative note path to surface related notes for.",
)
@click.option("--limit", default=DEFAULT_SEARCH_LIMIT, show_default=True, type=int)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def related(
    cfg: Config, query: str | None, to_note: str | None, limit: int, as_json: bool
) -> None:
    """Surface KB notes relevant to a query (--query) or a note (--to)."""
    # Distinguish "not provided" (None) from an empty string so that
    # `--query "" --to X` is rejected rather than silently running the --to branch.
    if (query is None) == (to_note is None):
        raise click.UsageError("Pass exactly one of --query or --to.")
    if query is not None and not query.strip():
        raise click.UsageError("--query must not be empty.")
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate a never-synced DB
        if query is not None:
            results = related_to_query(store, _build_embedder(cfg), query, limit=limit)
        else:
            results = related_to_note(store, to_note, limit=limit)
        hits = [
            {"note_path": h.note_path, "title": h.title, "score": round(h.score, 6)}
            for h in results
        ]
    finally:
        store.close()

    if as_json:
        click.echo(json.dumps({"hits": hits}))
        return
    if not hits:
        click.echo("No related notes.")
        return
    for hit in hits:
        click.echo(f"{hit['score']:.4f}  {hit['title']}  ({hit['note_path']})")


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def doctor(cfg: Config, as_json: bool) -> None:
    """Run health checks so the KB can never look healthier than it is.

    Prints one ``✅/⚠️/❌ name — detail`` line per check (❌ = failed hard check,
    ⚠️ = failed warn check). A hard failure — missing vault/db, a corrupt cache,
    or a stale/FAILED digest — sets exit code 1; warn failures never do.
    """
    checks = run_checks(cfg)
    if as_json:
        click.echo(json.dumps([asdict(c) for c in checks]))
    else:
        for c in checks:
            mark = "✅" if c.ok else ("❌" if c.severity == "hard" else "⚠️")
            click.echo(f"{mark} {c.name} — {c.detail}")
    if any(not c.ok and c.severity == "hard" for c in checks):
        sys.exit(1)


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def digest(cfg: Config, as_json: bool) -> None:
    """Write the KB state digest to ``_system/kb-digest.md``.

    Sections: This week, Review queue, Resurfacing, Health, and Synthesize.
    Passes ``today`` so the time-based This week/Resurfacing sections render
    (matching the pipeline's digest). Idempotent within a day — the body is keyed
    off ``today`` with no finer timestamp, so re-running the same day rewrites an
    identical file.
    """
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate a never-synced DB
        inbox_count = count_inbox(cfg.vault_path)
        unfiled = unfiled_notes(store)
        text = build_digest(
            store,
            vault_path=cfg.vault_path,
            inbox_count=inbox_count,
            unfiled=unfiled,
            today=date.today(),
        )
        topics = store.load_topics()
        n_proposals = sum(
            1 for t in topics if t.kind == "discovered" and t.status == "proposed"
        )
        n_topics = len(topics)
        n_areas = len(store.load_areas())
    finally:
        store.close()

    digest_path = cfg.vault_path / _DIGEST_RELPATH
    digest_path.parent.mkdir(parents=True, exist_ok=True)
    digest_path.write_text(text)
    rel = _DIGEST_RELPATH.as_posix()

    _emit(
        {
            "inbox": inbox_count,
            "proposals": n_proposals,
            "topics": n_topics,
            "areas": n_areas,
            "unfiled": len(unfiled),
            "digest_path": rel,
        },
        as_json,
        f"Digest: inbox={inbox_count} proposals={n_proposals} "
        f"topics={n_topics} areas={n_areas} unfiled={len(unfiled)} -> {rel}",
    )
