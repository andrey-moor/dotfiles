"""Core commands: sync, search, log-event, eval, status, rebuild."""
import json
from datetime import datetime, timezone

import click

from kb_engine.config import Config
from kb_engine.evaluation import ProbeError, evaluate, load_probes
from kb_engine.search import hybrid_search
from kb_engine.store import Store
from kb_engine.sync import rebuild as rebuild_index
from kb_engine.sync import sync as sync_index

from kb_engine.commands._shared import DEFAULT_SEARCH_LIMIT, _build_embedder, _emit


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def sync(cfg: Config, as_json: bool) -> None:
    """Incrementally embed new/changed notes and drop deleted ones."""
    store = Store(cfg.db_path)
    try:
        stats = sync_index(cfg, store, _build_embedder(cfg))
    finally:
        store.close()
    _emit(
        {"added": stats.added, "changed": stats.changed, "deleted": stats.deleted},
        as_json,
        f"Synced: added={stats.added} changed={stats.changed} deleted={stats.deleted}",
    )


@click.command()
@click.argument("query")
@click.option("--limit", default=DEFAULT_SEARCH_LIMIT, show_default=True, type=int)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def search(cfg: Config, query: str, limit: int, as_json: bool) -> None:
    """Hybrid (semantic + keyword) search over Knowledge/."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate searching a never-synced DB (no tables yet)
        results = hybrid_search(store, _build_embedder(cfg), query, limit=limit)
        hits = [
            {
                "note_path": path,
                "title": store.note_title(path) or path,
                "score": round(score, 6),
            }
            for path, score in results
        ]
        store.record_event(
            "search",
            query=query,
            top_path=results[0][0] if results else None,
            hit_rank=1 if results else None,
        )
    finally:
        store.close()

    if as_json:
        click.echo(json.dumps({"hits": hits}))
        return
    if not hits:
        click.echo("No results.")
        return
    for hit in hits:
        click.echo(f"{hit['score']:.4f}  {hit['title']}  ({hit['note_path']})")


@click.command("log-event")
@click.option("--kind", type=click.Choice(["open", "capture"]), required=True)
@click.option("--path", "note_path", required=True, help="Vault-relative note path.")
@click.pass_obj
def log_event(cfg: Config, kind: str, note_path: str) -> None:
    """Record a local telemetry event (used by the kb skill)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        store.record_event(kind, top_path=note_path)
    finally:
        store.close()
    click.echo("ok")


@click.command("eval")
@click.option("--k", default=5, show_default=True, type=int, help="Rank cutoff for recall/MRR.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.pass_obj
def eval_cmd(cfg: Config, k: int, as_json: bool) -> None:
    """Run retrieval probes from _system/probes.yaml; report recall@k and MRR."""
    probes_path = cfg.vault_path / "_system" / "probes.yaml"
    if not probes_path.is_file():
        raise click.UsageError(f"no probes file at {probes_path}")
    try:
        probes = load_probes(probes_path)
    except ProbeError as exc:
        raise click.UsageError(str(exc)) from exc
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate evaluating a never-synced DB (no tables yet)
        embedder = _build_embedder(cfg)
        ranked = [
            [path for path, _score in hybrid_search(store, embedder, p.query, limit=k)]
            for p in probes
        ]
    finally:
        store.close()
    report = evaluate(ranked, probes, k=k)
    if as_json:
        click.echo(
            json.dumps(
                {
                    "k": report.k,
                    "recall": report.recall,
                    "mrr": report.mrr,
                    "probes": [
                        {"query": o.query, "hit_rank": o.hit_rank}
                        for o in report.outcomes
                    ],
                }
            )
        )
        return
    hits = sum(1 for o in report.outcomes if o.hit_rank is not None)
    click.echo(
        f"recall@{report.k} {report.recall:.2f} ({hits}/{len(report.outcomes)}) "
        f"· MRR {report.mrr:.2f}"
    )
    for o in report.outcomes:
        mark = f"#{o.hit_rank}" if o.hit_rank else "MISS"
        click.echo(f"  [{mark:>4}] {o.query}")


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def status(cfg: Config, as_json: bool) -> None:
    """Show cache stats: note/chunk counts, DB path, last sync time."""
    db_exists = cfg.db_path.exists()
    last_sync = (
        datetime.fromtimestamp(cfg.db_path.stat().st_mtime, tz=timezone.utc).isoformat()
        if db_exists
        else None
    )
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        notes = store.count_notes()
        chunks = store.count_chunks()
        last = store.last_run("pipeline")
    finally:
        store.close()

    if as_json:
        click.echo(
            json.dumps(
                {
                    "notes": notes,
                    "chunks": chunks,
                    "db_path": str(cfg.db_path),
                    "last_sync": last_sync,
                    "last_run": last,
                }
            )
        )
        return

    click.echo(f"notes={notes} chunks={chunks} db={cfg.db_path} last_sync={last_sync}")
    if last is None:
        click.echo("last pipeline run: never")
    else:
        state = "running" if last["finished_at"] is None else ("ok" if last["ok"] else "FAILED")
        click.echo(f"last pipeline run: {last['started_at']}Z ({last['tier'] or '-'}) — {state}")


@click.command()
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def rebuild(cfg: Config, as_json: bool) -> None:
    """Drop the entire cache and re-embed the vault from scratch."""
    store = Store(cfg.db_path)
    try:
        stats = rebuild_index(cfg, store, _build_embedder(cfg))
    finally:
        store.close()
    _emit(
        {"added": stats.added, "changed": stats.changed, "deleted": stats.deleted},
        as_json,
        f"Rebuilt: added={stats.added} changed={stats.changed} deleted={stats.deleted}",
    )
