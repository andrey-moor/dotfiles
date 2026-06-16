import json
import os
from datetime import datetime, timezone
from pathlib import Path

import click

from kb_engine.config import Config
from kb_engine.embeddings import Embedder, FakeEmbedder, LocalJinaEmbedder
from kb_engine.models import TopicMember
from kb_engine.search import hybrid_search
from kb_engine.store import Store
from kb_engine.sync import rebuild as rebuild_index
from kb_engine.sync import sync as sync_index
from kb_engine.topics.areas import build_areas
from kb_engine.topics.assignment import assign_notes
from kb_engine.topics.clustering import Clusterer, FakeClusterer, UmapHdbscanClusterer
from kb_engine.topics.discover import discover_topics

DEFAULT_SEARCH_LIMIT = 10
DEFAULT_AREA_THRESHOLD = 0.3
DEFAULT_ASSIGN_HIGH = 0.55
DEFAULT_ASSIGN_LOW = 0.4
_ASSIGNABLE_STATUSES = frozenset({"active", "proposed"})


def _build_embedder(cfg: Config) -> Embedder:
    """Use the deterministic FakeEmbedder when KB_FAKE_EMBED=1, else real jina-v3."""
    if os.environ.get("KB_FAKE_EMBED") == "1":
        return FakeEmbedder(dim=cfg.embed_dim)
    return LocalJinaEmbedder(model_name=cfg.model_name, dim=cfg.embed_dim)


def _build_clusterer() -> Clusterer:
    """Use a deterministic FakeClusterer when KB_FAKE_CLUSTER is set, else real UMAP/HDBSCAN.

    KB_FAKE_CLUSTER is a comma-separated list of int labels (-1 = noise), e.g.
    "0,0,-1". An empty/unset value falls back to the real clusterer.
    """
    raw = os.environ.get("KB_FAKE_CLUSTER", "").strip()
    if raw:
        labels = [int(part) for part in raw.split(",")]
        return FakeClusterer(labels=labels)
    return UmapHdbscanClusterer()


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
    finally:
        store.close()
    _emit(
        {
            "notes": notes,
            "chunks": chunks,
            "db_path": str(cfg.db_path),
            "last_sync": last_sync,
        },
        as_json,
        f"notes={notes} chunks={chunks} db={cfg.db_path} last_sync={last_sync}",
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
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_discover(cfg: Config, as_json: bool) -> None:
    """Cluster note vectors into topics (UMAP→HDBSCAN) and persist them."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate discovering against a never-synced DB
        result = discover_topics(store, _build_clusterer())
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
@click.option(
    "--threshold",
    default=DEFAULT_AREA_THRESHOLD,
    show_default=True,
    type=float,
    help="Cosine distance cut for agglomerative grouping of topic centroids.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_areas(cfg: Config, threshold: float, as_json: bool) -> None:
    """Group discovered topics into areas (agglomerative on centroids)."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate running against a never-synced DB
        areas = build_areas(store.load_topics(), distance_threshold=threshold)
        store.save_areas(areas)
        area_rows = [
            {"slug": area.slug, "label": area.label, "topics": list(area.topic_slugs)}
            for area in areas
        ]
    finally:
        store.close()

    if as_json:
        click.echo(json.dumps({"n_areas": len(area_rows), "areas": area_rows}))
        return
    if not area_rows:
        click.echo("No areas.")
        return
    for row in area_rows:
        topics_list = ", ".join(row["topics"])
        click.echo(f"{row['slug']}  ({len(row['topics'])} topics)  [{topics_list}]")


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
    cfg: Config, high: float, low: float, apply_changes: bool, as_json: bool
) -> None:
    """Assign notes to nearest topic by cosine; dry-run unless ``--apply``."""
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        note_vectors = dict(store.note_vectors())
        assignable = [
            topic
            for topic in store.load_topics()
            if topic.status in _ASSIGNABLE_STATUSES
        ]
        assigned, borderline = assign_notes(note_vectors, assignable, high, low)
        if apply_changes:
            members_by_slug: dict[str, list[TopicMember]] = {}
            for note_path, (slug, score) in assigned.items():
                members_by_slug.setdefault(slug, []).append(
                    TopicMember(note_path=note_path, score=score, source="auto")
                )
            for slug, members in members_by_slug.items():
                store.set_members(slug, members)
        assigned_rows = [
            {"note": note_path, "topic": slug, "score": round(score, 6)}
            for note_path, (slug, score) in sorted(assigned.items())
        ]
        borderline_rows = [
            {"note": note_path, "topic": slug, "score": round(score, 6)}
            for note_path, (slug, score) in borderline
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
        f"assigned={len(assigned_rows)} borderline={len(borderline_rows)} "
        f"unassigned={n_unassigned} applied={apply_changes}"
    )


if __name__ == "__main__":
    main()
