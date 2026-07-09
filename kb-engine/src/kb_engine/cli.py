import json
import sys
import os
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import click

from kb_engine.backfill import DEFAULT_LIMIT as DEFAULT_BACKFILL_LIMIT
from kb_engine.backfill import backfill_content
from kb_engine.config import Config
from kb_engine.dedup import DEFAULT_DEDUP_THRESHOLD, near_duplicates
from kb_engine.doctor import run_checks
from kb_engine.importing.digest import build_digest, count_proposals
from kb_engine.importing.inbox import existing_urls, import_urls
from kb_engine.importing.mail_notes import (
    DEFAULT_KB_LABEL,
    DEFAULT_MAIL_LIMIT,
    run_import_mail,
)
from kb_engine.importing.things import read_things_tasks
from kb_engine.importing.urls import normalize_url
from kb_engine.embeddings import Embedder, FakeEmbedder, LocalJinaEmbedder
from kb_engine.evaluation import ProbeError, evaluate, load_probes
from kb_engine.models import TopicMember
from kb_engine.pipeline import count_inbox, run_pipeline, unfiled_notes
from kb_engine.search import hybrid_search
from kb_engine.store import SLUG_PATTERN, Store, is_valid_slug
from kb_engine.surface import related_to_note, related_to_query
from kb_engine.synthesis import synthesis_candidates
from kb_engine.sync import rebuild as rebuild_index
from kb_engine.sync import sync as sync_index
from kb_engine.topics.anchoring import reanchor_topics
from kb_engine.topics.thresholds import derive_thresholds, persist_thresholds
from kb_engine.topics.areas_registry import seed_areas
from kb_engine.topics.assignment import (
    DEFAULT_ASSIGN_HIGH,
    DEFAULT_ASSIGN_LOW,
    DEFAULT_ASSIGN_SECONDARY,
    assign_notes,
)
from kb_engine.topics.clustering import Clusterer, FakeClusterer, UmapHdbscanClusterer
from kb_engine.topics.discover import discover_topics
from kb_engine.topics.suggest import suggest_from_residual
from kb_engine.filing import apply_dispositions
from kb_engine.inbox_check import check_inbox
from kb_engine.topics.apply import apply_topic_tags
from kb_engine.topics.render import render_topics
from kb_engine.topics.taxonomy import diff_taxonomy, parse_taxonomy_tags

DEFAULT_SEARCH_LIMIT = 10
DEFAULT_SYNTHESIS_MIN = 5
# DEFAULT_ASSIGN_HIGH / SECONDARY / LOW are imported from topics.assignment (above).
# DEFAULT_KB_LABEL / DEFAULT_MAIL_LIMIT live in kb_engine.importing.mail_notes
# (imported above) so the import-mail flags and the pipeline share one default.
_SUGGEST_MIN_CLUSTER_SIZE = 2  # surface two-note mini-themes below the adaptive floor
_ASSIGNABLE_STATUSES = frozenset({"active", "proposed"})
_TAXONOMY_RELPATH = Path("_system") / "_taxonomy.md"
DEFAULT_APPLY_STATUS = "active"

# Standard Things 3 SQLite location on macOS.
_THINGS_DB_GLOB = "Library/Group Containers/*ThingsMac*/**/main.sqlite"
_IMPORT_SAMPLE_SIZE = 5

_DIGEST_RELPATH = Path("_system") / "kb-digest.md"

# count_inbox / unfiled_notes live in kb_engine.pipeline (imported above) so the
# digest command and the pipeline share one definition.


def _default_things_db() -> Path | None:
    """Resolve the live Things DB under $HOME, or None.

    The standard glob also matches dated copies under ``Backups/``; those are
    skipped so the *live* database is chosen. Only if nothing but a backup
    exists is a backup returned (better than nothing).
    """
    matches = sorted(Path.home().glob(_THINGS_DB_GLOB))
    live = [m for m in matches if "Backups" not in m.parts]
    chosen = live or matches
    return chosen[0] if chosen else None


def _task_items(tasks: list) -> list[tuple[str, str]]:
    """Flatten Things tasks to ``(url, title)`` items.

    Each URL on a task gets its own item. The title is the task title, unless
    the title is itself a URL (a bare-link task), in which case the URL is used
    as the title so the stub names from the link.
    """
    items: list[tuple[str, str]] = []
    for task in tasks:
        title = task.title.strip()
        title_is_url = title.lower().startswith(("http://", "https://"))
        for url in task.urls:
            items.append((url, url if title_is_url else (title or url)))
    return items


def _build_embedder(cfg: Config) -> Embedder:
    """Use the deterministic FakeEmbedder when KB_FAKE_EMBED=1, else real jina-v3."""
    if os.environ.get("KB_FAKE_EMBED") == "1":
        return FakeEmbedder(dim=cfg.embed_dim)
    return LocalJinaEmbedder(model_name=cfg.model_name, dim=cfg.embed_dim)


def _build_clusterer(
    cluster_selection_method: str = "leaf", min_cluster_size: int | None = None
) -> Clusterer:
    """Use a deterministic FakeClusterer when KB_FAKE_CLUSTER is set, else real UMAP/HDBSCAN.

    KB_FAKE_CLUSTER is a comma-separated list of int labels (-1 = noise), e.g.
    "0,0,-1". An empty/unset value falls back to the real clusterer.
    ``cluster_selection_method`` is "leaf" (finer topics) or "eom" (broader).
    ``min_cluster_size`` overrides the adaptive ladder when set (must be >= 2).
    """
    raw = os.environ.get("KB_FAKE_CLUSTER", "").strip()
    if raw:
        labels = [int(part) for part in raw.split(",")]
        return FakeClusterer(labels=labels)
    return UmapHdbscanClusterer(
        cluster_selection_method=cluster_selection_method,
        min_cluster_size=min_cluster_size,
    )


def _emit(payload: dict, as_json: bool, human: str) -> None:
    if as_json:
        click.echo(json.dumps(payload))
    else:
        click.echo(human)


@click.group()
@click.option(
    "--vault",
    "vault",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Path to the Obsidian vault root.",
)
@click.option(
    "--db",
    "db",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="SQLite cache path (defaults to ~/.local/state/kb-engine/kb-engine.db).",
)
@click.pass_context
def main(ctx: click.Context, vault: Path, db: Path | None) -> None:
    """kb-engine — local embedding + hybrid search for an Obsidian KB."""
    ctx.obj = Config(vault_path=vault, db_path=db)


@main.command()
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


@main.command()
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


@main.command("log-event")
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


@main.command("eval")
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


@main.command("synthesis-candidates")
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


@main.command("dedup-report")
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


@main.command()
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


@main.command()
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


@main.command()
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


@main.command("inbox-check")
@click.option(
    "--check-filed",
    is_flag=True,
    help="Also flag inbox urls already filed elsewhere (slow: scans all of Knowledge/).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def inbox_check(cfg: Config, check_filed: bool, as_json: bool) -> None:
    """Validate Knowledge/inbox/ clips against the schema (report-only, no writes)."""
    report = check_inbox(cfg.vault_path, check_filed=check_filed)
    payload = {
        "n_notes": report.n_notes,
        "schema_ok": len(report.schema_ok),
        "schema_bad": [{"note": p, "missing": list(m)} for p, m in report.schema_bad],
        "missing_why": list(report.missing_why),
        "dup_in_inbox": [{"url": u, "notes": list(p)} for u, p in report.dup_in_inbox],
        "dup_vs_knowledge": [{"note": n, "url": u} for n, u in report.dup_vs_knowledge],
    }
    _emit(
        payload,
        as_json,
        f"inbox: {report.n_notes} notes | schema_ok={len(report.schema_ok)} "
        f"schema_bad={len(report.schema_bad)} missing_why={len(report.missing_why)} "
        f"dup_in_inbox={len(report.dup_in_inbox)} dup_vs_knowledge={len(report.dup_vs_knowledge)}",
    )


@main.command()
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


@main.group()
def topics() -> None:
    """Discover and inspect topics over the KB's embeddings."""


@topics.command("discover")
@click.option(
    "--coarse",
    is_flag=True,
    help="Use excess-of-mass clustering (fewer, broader topics). Default is leaf (finer, more coherent).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_discover(cfg: Config, coarse: bool, as_json: bool) -> None:
    """Cluster note vectors into topics (UMAP→HDBSCAN) and persist them.

    Clustering uses leaf selection by default (finer topics); pass ``--coarse``
    for excess-of-mass (fewer, broader clusters).
    """
    method = "eom" if coarse else "leaf"
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate discovering against a never-synced DB
        result = discover_topics(store, _build_clusterer(method))
        topic_rows = [
            {
                "slug": topic.slug,
                "label": topic.label,
                "keywords": list(topic.keywords),
                "size": len(result.members_by_slug.get(topic.slug, [])),
            }
            for topic in result.topics
        ]
    finally:
        store.close()

    if as_json:
        click.echo(
            json.dumps(
                {
                    "n_topics": result.n_topics,
                    "n_unfiled": result.n_unfiled,
                    "topics": topic_rows,
                }
            )
        )
        return
    if not topic_rows:
        click.echo(f"No topics discovered. unfiled={result.n_unfiled}")
        return
    for row in topic_rows:
        keywords = ", ".join(row["keywords"])
        click.echo(f"{row['slug']}  ({row['size']} notes)  [{keywords}]")
    click.echo(f"unfiled={result.n_unfiled}")


@topics.command("areas")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_areas(cfg: Config, as_json: bool) -> None:
    """List the areas registry with each area's member topics."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        areas = store.load_areas()
    finally:
        store.close()
    rows = [
        {
            "slug": a.slug, "label": a.label, "description": a.description,
            "topics": list(a.topic_slugs),
        }
        for a in areas
    ]
    if as_json:
        click.echo(json.dumps({"areas": rows}))
        return
    if not rows:
        click.echo("No areas. Run `kb-engine topics seed-areas` first.")
        return
    for row in rows:
        topics_list = ", ".join(row["topics"]) or "—"
        click.echo(f"{row['slug']:10} {row['label']:14} [{topics_list}]")


@topics.command("seed-areas")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_seed_areas(cfg: Config, as_json: bool) -> None:
    """Seed the 9-area registry (idempotent full replace)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        n = seed_areas(store)
    finally:
        store.close()
    _emit({"seeded": n}, as_json, f"Seeded {n} areas.")


@topics.command("set-area")
@click.argument("topic_slug")
@click.argument("area_slug")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_set_area(cfg: Config, topic_slug: str, area_slug: str, as_json: bool) -> None:
    """Assign TOPIC_SLUG to AREA_SLUG (both must exist)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        if topic_slug not in {t.slug for t in store.load_topics()}:
            raise click.ClickException(f"no such topic: {topic_slug}")
        if area_slug not in {a.slug for a in store.load_areas()}:
            raise click.ClickException(f"no such area: {area_slug} (seed-areas first?)")
        store.set_topic_area(topic_slug, area_slug)
    finally:
        store.close()
    _emit(
        {"topic": topic_slug, "area": area_slug},
        as_json,
        f"{topic_slug} -> {area_slug}",
    )


@topics.command("diff-taxonomy")
@click.option(
    "--taxonomy",
    "taxonomy_path",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Taxonomy file (default <vault>/_system/_taxonomy.md).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_diff_taxonomy(
    cfg: Config, taxonomy_path: Path | None, as_json: bool
) -> None:
    """Diff discovered topics against the existing _taxonomy.md (Jaccard set math).

    Reports, per existing tag, the ranked aligned topics; topics with no aligned
    tag (``new_topics`` — structure the data found); and tags with no aligned
    topic (``orphan_tags``). A missing taxonomy file is treated as greenfield, so
    every discovered topic is reported as new.
    """
    path = taxonomy_path or (cfg.vault_path / _TAXONOMY_RELPATH)
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        notes_by_tag = store.notes_by_tag()
        if path.exists():
            declared = parse_taxonomy_tags(path)
            existing = {
                tag: notes_by_tag[tag] for tag in declared if tag in notes_by_tag
            }
        else:
            existing = {}
        topic_members = {
            topic.slug: {m.note_path for m in store.topic_members(topic.slug)}
            for topic in store.load_topics()
        }
        diff = diff_taxonomy(existing, topic_members)
    finally:
        store.close()

    mapping_rows = {
        tag: [{"topic": slug, "overlap": round(overlap, 6)} for slug, overlap in ranked]
        for tag, ranked in diff.mapping.items()
    }
    payload = {
        "mapping": mapping_rows,
        "new_topics": diff.new_topics,
        "orphan_tags": diff.orphan_tags,
        "covered_topics": diff.covered_topics,
    }
    if as_json:
        click.echo(json.dumps(payload))
        return
    click.echo(
        f"tags={len(mapping_rows)} covered_topics={len(diff.covered_topics)} "
        f"new_topics={len(diff.new_topics)} orphan_tags={len(diff.orphan_tags)}"
    )
    for tag, ranked in mapping_rows.items():
        best = ranked[0] if ranked else None
        aligned = f"{best['topic']} ({best['overlap']:.2f})" if best else "—"
        click.echo(f"  {tag} -> {aligned}")
    if diff.new_topics:
        click.echo(f"new (no aligned tag): {', '.join(diff.new_topics)}")
    if diff.orphan_tags:
        click.echo(f"orphan tags (no aligned topic): {', '.join(diff.orphan_tags)}")


@topics.command("render")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_render(cfg: Config, as_json: bool) -> None:
    """Render topic/area MOCs to _system/topics/ + proposals into _taxonomy.md.

    Idempotent and render-not-append: rewrites the MOC files and splices the
    proposal table between stable markers, preserving the rest of the taxonomy.
    """
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        result = render_topics(store, cfg.vault_path)
    finally:
        store.close()
    _emit(
        {
            "n_topics": result.n_topics,
            "n_areas": result.n_areas,
            "index_path": result.index_path,
            "taxonomy_path": result.taxonomy_path,
        },
        as_json,
        f"Rendered {result.n_topics} topics, {result.n_areas} areas -> "
        f"{result.index_path}",
    )


@topics.command("apply")
@click.option(
    "--status",
    default=DEFAULT_APPLY_STATUS,
    show_default=True,
    help="Only apply topics with this status (proposed topics stay unapplied).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_apply(cfg: Config, status: str, as_json: bool) -> None:
    """Write ``topic/<slug>`` tags into member notes' frontmatter (gated, idempotent).

    This is the only command that mutates notes; running it IS the gate. By
    default only ``active`` topics apply, so discovered proposals stay proposed
    until confirmed. Re-running is a no-op.
    """
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        result = apply_topic_tags(store, cfg.vault_path, only_status=(status,))
    finally:
        store.close()
    _emit(
        {
            "status": status,
            "n_changed": result.n_changed,
            "n_tags_added": result.n_tags_added,
            "skipped_missing": list(result.skipped_missing),
            "skipped_outside_vault": list(result.skipped_outside_vault),
        },
        as_json,
        f"Applied status={status}: changed={result.n_changed} "
        f"tags_added={result.n_tags_added} "
        f"skipped_missing={len(result.skipped_missing)} "
        f"skipped_outside_vault={len(result.skipped_outside_vault)}",
    )


@topics.command("add")
@click.argument("slug")
@click.option("--label", required=True, help="Human-readable topic label.")
@click.option("--description", required=True, help="Description embedded as the anchor.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_add(
    cfg: Config, slug: str, label: str, description: str, as_json: bool
) -> None:
    """Add a manual topic anchored by an embedding of its label + description."""
    if not is_valid_slug(slug):
        raise click.BadParameter(
            f"slug {slug!r} must match {SLUG_PATTERN} "
            "(lowercase letters/digits, internal hyphens — it becomes a filename)",
            param_hint="SLUG",
        )
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        centroid = _build_embedder(cfg).embed_query(f"{label}. {description}")
        try:
            store.add_manual_topic(slug, label, description, centroid)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        store.close()
    _emit(
        {"slug": slug, "label": label, "kind": "manual", "status": "active"},
        as_json,
        f"Added manual topic {slug} ({label}).",
    )


@topics.command("list")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_list(cfg: Config, as_json: bool) -> None:
    """List all topics (manual first, then discovered) with member counts."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        # Manual topics first, then discovered; within each, by slug.
        loaded = sorted(
            store.load_topics(), key=lambda t: (t.kind != "manual", t.slug)
        )
        rows = [
            {
                "slug": topic.slug,
                "label": topic.label,
                "kind": topic.kind,
                "status": topic.status,
                "size": len(store.topic_members(topic.slug)),
            }
            for topic in loaded
        ]
    finally:
        store.close()

    if as_json:
        click.echo(json.dumps({"topics": rows}))
        return
    if not rows:
        click.echo("No topics.")
        return
    for row in rows:
        click.echo(
            f"{row['slug']}  [{row['kind']}/{row['status']}]  ({row['size']} notes)"
        )


@topics.command("assign")
@click.option("--high", default=DEFAULT_ASSIGN_HIGH, show_default=True, type=float)
@click.option(
    "--secondary",
    default=DEFAULT_ASSIGN_SECONDARY,
    show_default=True,
    type=float,
    help="Min cosine for a SECONDARY (cross-link) topic.",
)
@click.option("--low", default=DEFAULT_ASSIGN_LOW, show_default=True, type=float)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    help="Persist high-confidence assignments (dry-run reports only by default).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_assign(
    cfg: Config,
    high: float,
    secondary: float,
    low: float,
    apply_changes: bool,
    as_json: bool,
) -> None:
    """Assign notes to a primary topic + up to 2 secondaries; dry-run unless ``--apply``."""
    # Validate the threshold ordering at the CLI boundary so a bad flag combo
    # surfaces as a clean usage error, not the library ValueError's traceback.
    if secondary > high:
        raise click.UsageError(f"--secondary ({secondary}) must be <= --high ({high})")
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        note_vectors = dict(store.note_vectors())
        assignable = [
            topic
            for topic in store.load_topics()
            if topic.status in _ASSIGNABLE_STATUSES
        ]
        assigned, borderline = assign_notes(
            note_vectors, assignable, high, secondary, low
        )
        if apply_changes:
            members_by_slug: dict[str, list[TopicMember]] = {}
            for note_path, members in assigned.items():
                for member in members:
                    members_by_slug.setdefault(member.slug, []).append(
                        TopicMember(
                            note_path=note_path,
                            score=member.score,
                            source="auto",
                            is_primary=member.is_primary,
                        )
                    )
            for slug, members in members_by_slug.items():
                store.set_members(slug, members)
        assigned_rows = [
            {
                "note": note_path,
                "topic": member.slug,
                "score": round(member.score, 6),
                "is_primary": member.is_primary,
            }
            for note_path, members in sorted(assigned.items())
            for member in members
        ]
        borderline_rows = [
            {
                "note": note_path,
                "topic": candidates[0][0],
                "score": round(candidates[0][1], 6),
                "candidates": [
                    {"topic": slug, "score": round(score, 6)}
                    for slug, score in candidates
                ],
            }
            for note_path, candidates in borderline
        ]
        n_unassigned = len(note_vectors) - len(assigned) - len(borderline)
    finally:
        store.close()

    if as_json:
        click.echo(
            json.dumps(
                {
                    "assigned": assigned_rows,
                    "borderline": borderline_rows,
                    "unassigned": n_unassigned,
                    "applied": apply_changes,
                }
            )
        )
        return
    click.echo(
        f"assigned={len(assigned)} borderline={len(borderline_rows)} "
        f"unassigned={n_unassigned} applied={apply_changes}"
    )


@topics.command("suggest")
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    help="Persist suggestions as proposed topics (dry-run reports only by default).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_suggest(cfg: Config, apply_changes: bool, as_json: bool) -> None:
    """Cluster the unfiled residual (min_cluster_size=2) into latent topic proposals.

    Re-clusters only notes that are in NO topic, surfacing coherent mini-themes
    below the normal cluster floor. Dry-run by default; ``--apply`` persists them
    as ``proposed`` discovered topics (which replaces any existing discovered
    proposals — promote ones you want to keep to active first).
    """
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        note_vectors = dict(store.note_vectors())
        # notes_without_topic() (one query) is the unfiled set; in_topic is its
        # complement among notes that have vectors.
        in_topic = set(note_vectors) - set(store.notes_without_topic())
        texts_by_path = store.note_texts()
        result = suggest_from_residual(
            note_vectors, in_topic,
            _build_clusterer(min_cluster_size=_SUGGEST_MIN_CLUSTER_SIZE), texts_by_path,
        )
        if apply_changes:
            store.save_topics(list(result.topics), result.members_by_slug)
        rows = [
            {
                "slug": topic.slug,
                "label": topic.label,
                "keywords": list(topic.keywords),
                "size": len(result.members_by_slug.get(topic.slug, [])),
            }
            for topic in result.topics
        ]
    finally:
        store.close()

    if as_json:
        click.echo(json.dumps({
            "n_topics": result.n_topics,
            "n_unfiled": result.n_unfiled,
            "topics": rows,
            "applied": apply_changes,
        }))
        return
    if not rows:
        click.echo(f"No latent topics. unfiled={result.n_unfiled} applied={apply_changes}")
        return
    for row in rows:
        keywords = ", ".join(row["keywords"])
        click.echo(f"{row['slug']}  ({row['size']} notes)  [{keywords}]")
    click.echo(f"unfiled={result.n_unfiled} applied={apply_changes}")


@topics.command("reanchor")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_reanchor(cfg: Config, as_json: bool) -> None:
    """Recompute manual-topic anchors from member vectors (>=3 members)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        result = reanchor_topics(store)
    finally:
        store.close()
    _emit(
        {
            "reanchored": list(result.reanchored),
            "kept_label": list(result.kept_label),
        },
        as_json,
        f"Re-anchored {len(result.reanchored)} topic(s); "
        f"{len(result.kept_label)} kept label anchor.",
    )


@topics.command("thresholds")
@click.option("--dry-run", is_flag=True, help="Report only; do not persist.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_thresholds(cfg: Config, dry_run: bool, as_json: bool) -> None:
    """Derive per-topic assignment thresholds from member-sim distributions.

    high = max(0.45, p25 of member cosines to the current anchor);
    secondary = high - 0.08. Persists unless --dry-run."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        stats = derive_thresholds(store)
        if not dry_run:
            persist_thresholds(store, stats)
    finally:
        store.close()
    rows = [
        {
            "slug": s.slug, "n_members": s.n_members,
            "p25": round(s.p25, 4), "p50": round(s.p50, 4), "p75": round(s.p75, 4),
            "high": round(s.high, 4), "secondary": round(s.secondary, 4),
        }
        for s in stats
    ]
    if as_json:
        click.echo(json.dumps({"persisted": not dry_run, "topics": rows}))
        return
    for r in rows:
        click.echo(
            f"{r['slug']:40} n={r['n_members']:>3} p25={r['p25']:.3f} "
            f"p50={r['p50']:.3f} p75={r['p75']:.3f} -> high={r['high']:.3f} "
            f"secondary={r['secondary']:.3f}"
        )
    click.echo(
        f"{len(rows)} topic(s) {'reported (dry-run)' if dry_run else 'persisted'}"
    )


@topics.command("confirm")
@click.argument("slug")
@click.argument("note_path")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_confirm(cfg: Config, slug: str, note_path: str, as_json: bool) -> None:
    """Confirm NOTE_PATH into topic SLUG as its human-decided primary.

    The /kb:review queue verb: writes a source='user' primary membership,
    clears any auto primaries for the note, and removes its queue row.
    Run `topics apply` afterwards to write the tag into the note."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        known = {t.slug for t in store.load_topics()}
        if slug not in known:
            raise click.ClickException(f"no such topic: {slug}")
        if store.note_sha(note_path) is None:
            raise click.ClickException(f"note not in the index: {note_path}")
        score = 1.0
        dequeued = False
        for entry in store.load_review_queue():
            if entry.note_path == note_path:
                score = next(
                    (s for cand, s in entry.candidates if cand == slug), 1.0
                )
                dequeued = True
                break
        store.clear_auto_primaries(note_path)
        store.set_members(
            slug,
            [TopicMember(note_path=note_path, score=score, source="user",
                         is_primary=True)],
        )
        store.remove_from_review_queue(note_path)
    finally:
        store.close()
    _emit(
        {"slug": slug, "note": note_path, "score": round(score, 6),
         "source": "user", "dequeued": dequeued},
        as_json,
        f"Confirmed {note_path} -> {slug} (score {score:.2f}).",
    )


@main.command("import-mail")
@click.option("--label", default=DEFAULT_KB_LABEL, show_default=True, help="Fastmail label to ingest.")
@click.option("--limit", default=DEFAULT_MAIL_LIMIT, show_default=True, type=int)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def import_mail_cmd(cfg: Config, label: str, limit: int, as_json: bool) -> None:
    """Ingest `<label>`-tagged newsletters from Fastmail (JMAP) into the inbox."""
    token = os.environ.get("FASTMAIL_API_TOKEN")
    if not token:
        raise click.UsageError("FASTMAIL_API_TOKEN is not set (store it in 1Password/Nix, export for the run).")
    store = Store(cfg.db_path)
    try:
        fetched, result = run_import_mail(cfg.vault_path, store, token, label, limit)
    except ValueError as e:
        raise click.ClickException(str(e))
    finally:
        store.close()
    payload = {
        "fetched": fetched,
        "written": result.written,
        "skipped_existing_url": result.skipped_existing_url,
        "skipped_existing_msgid": result.skipped_existing_msgid,
        "skipped_dup_in_batch": result.skipped_dup_in_batch,
    }
    _emit(payload, as_json,
          f"mail: fetched {fetched} | wrote {result.written} | "
          f"skipped url={result.skipped_existing_url} msgid={result.skipped_existing_msgid} "
          f"batch={result.skipped_dup_in_batch}")


@main.command("backfill-content")
@click.option("--limit", default=DEFAULT_BACKFILL_LIMIT, show_default=True, type=int)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def backfill_content_cmd(cfg: Config, limit: int, as_json: bool) -> None:
    """Fetch full text for thin captures and append a ## Content section."""
    store = Store(cfg.db_path)
    try:
        stats = backfill_content(cfg, store, limit=limit)
    finally:
        store.close()
    _emit(
        {
            "fetched": stats.fetched,
            "unavailable": stats.unavailable,
            "skipped": stats.skipped,
            "failures": list(stats.failures),
        },
        as_json,
        f"Backfill: {stats.fetched} fetched · {stats.unavailable} unavailable · "
        f"{stats.skipped} skipped ({len(stats.failures)} failed)",
    )


@main.command("import-things")
@click.option(
    "--things-db",
    "things_db",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Things SQLite path (default: the standard ThingsMac location).",
)
@click.option(
    "--status",
    default="open",
    show_default=True,
    type=click.Choice(["open", "completed", "all"]),
    help="Which task status to import.",
)
@click.option(
    "--area", "areas", multiple=True, help="Only this area (repeatable)."
)
@click.option(
    "--project", "projects", multiple=True, help="Only this project (repeatable)."
)
@click.option(
    "--exclude-area",
    "exclude_areas",
    multiple=True,
    help="Drop tasks in this area (repeatable, applied on top of --area).",
)
@click.option(
    "--exclude-project",
    "exclude_projects",
    multiple=True,
    help="Drop tasks in this project (repeatable, applied on top of --project).",
)
@click.option(
    "--date",
    "date_added",
    default=None,
    help="date_added to stamp on stubs (default: today). YYYY-MM-DD.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be imported without writing anything.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def import_things(
    cfg: Config,
    things_db: Path | None,
    status: str,
    areas: tuple[str, ...],
    projects: tuple[str, ...],
    exclude_areas: tuple[str, ...],
    exclude_projects: tuple[str, ...],
    date_added: str | None,
    dry_run: bool,
    as_json: bool,
) -> None:
    """Import open URL-bearing Things tasks into ``Knowledge/inbox/`` stubs.

    Reads Things read-only (via a temp copy, safe while Things runs), extracts
    URLs, dedups against existing vault note URLs and within the batch, and
    writes proper-schema inbox stubs. ``--dry-run`` reports counts and a small
    sample without writing.
    """
    db = things_db or _default_things_db()
    if db is None:
        raise click.ClickException(
            "Things DB not found. Pass --things-db PATH "
            f"(looked for ~/{_THINGS_DB_GLOB})."
        )
    try:
        tasks = read_things_tasks(
            db,
            status=status,
            areas=list(areas) or None,
            projects=list(projects) or None,
            exclude_areas=list(exclude_areas) or None,
            exclude_projects=list(exclude_projects) or None,
        )
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    items = _task_items(tasks)

    if dry_run:
        existing = existing_urls(cfg.vault_path)
        seen: set[str] = set()
        would_write = would_skip_existing = would_skip_dup_in_batch = 0
        for url, _title in items:
            normalized = normalize_url(url)
            if normalized in existing:
                would_skip_existing += 1
            elif normalized in seen:
                would_skip_dup_in_batch += 1
            else:
                seen.add(normalized)
                would_write += 1
        sample = [
            {"url": normalize_url(url), "title": title}
            for url, title in items[:_IMPORT_SAMPLE_SIZE]
        ]
        _emit(
            {
                "dry_run": True,
                "things_db": str(db),
                "status": status,
                "n_tasks": len(tasks),
                "n_urls": len(items),
                "would_write": would_write,
                "would_skip_existing": would_skip_existing,
                "would_skip_dup_in_batch": would_skip_dup_in_batch,
                "sample": sample,
            },
            as_json,
            f"[dry-run] tasks={len(tasks)} urls={len(items)} "
            f"would_write={would_write} would_skip_existing={would_skip_existing} "
            f"would_skip_dup_in_batch={would_skip_dup_in_batch}",
        )
        return

    stamp = date_added or date.today().isoformat()
    result = import_urls(cfg.vault_path, items, date_added=stamp)
    _emit(
        {
            "dry_run": False,
            "written": result.written,
            "skipped_existing": result.skipped_existing,
            "skipped_dup_in_batch": result.skipped_dup_in_batch,
        },
        as_json,
        f"Imported: written={result.written} "
        f"skipped_existing={result.skipped_existing} "
        f"skipped_dup_in_batch={result.skipped_dup_in_batch}",
    )


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def digest(cfg: Config, as_json: bool) -> None:
    """Write a deterministic KB state digest to ``_system/kb-digest.md``.

    Reports inbox backlog, topic proposals awaiting review, topic/area counts,
    and unfiled notes. Idempotent — the body has no timestamps, so re-running
    rewrites an identical file.
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


@main.command()
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


@main.command("file")
@click.option(
    "--from",
    "from_path",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="JSON file with dispositions (default: read from stdin).",
)
@click.option(
    "--apply",
    "apply_changes",
    is_flag=True,
    help="Apply dispositions (default: dry-run, writes nothing).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def file_cmd(cfg: Config, from_path: Path | None, apply_changes: bool, as_json: bool) -> None:
    """Apply inbox dispositions: move notes from inbox/ to Knowledge/.

    Reads a JSON array of dispositions from ``--from <path>`` or stdin.
    Each disposition: ``{"filename": str, "status": str, "tags": list, "summary": str}``.
    Valid statuses: ``reference``, ``archived``.

    Dry-run by default; pass ``--apply`` to actually move files.
    """
    if from_path is not None:
        raw = from_path.read_text()
    else:
        raw = sys.stdin.read()

    try:
        dispositions = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Invalid JSON: {exc}") from exc

    if not isinstance(dispositions, list):
        raise click.ClickException("Dispositions must be a JSON array.")

    dry_run = not apply_changes
    result = apply_dispositions(cfg.vault_path, dispositions, dry_run=dry_run)

    _emit(
        {
            "filed": result.n_filed,
            "archived": result.n_archived,
            "skipped_missing": list(result.skipped_missing),
            "skipped_collision": list(result.skipped_collision),
            "skipped_invalid": list(result.skipped_invalid),
            "dry_run": dry_run,
        },
        as_json,
        (
            f"[dry-run] " if dry_run else ""
        ) + (
            f"filed={result.n_filed} archived={result.n_archived} "
            f"skipped_missing={len(result.skipped_missing)} "
            f"skipped_collision={len(result.skipped_collision)} "
            f"skipped_invalid={len(result.skipped_invalid)}"
        ),
    )


if __name__ == "__main__":
    main()
