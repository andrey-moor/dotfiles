import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import click

from kb_engine.config import Config
from kb_engine.importing.digest import build_digest
from kb_engine.importing.inbox import existing_urls, import_urls
from kb_engine.importing.things import read_things_tasks
from kb_engine.importing.urls import normalize_url
from kb_engine.embeddings import Embedder, FakeEmbedder, LocalJinaEmbedder
from kb_engine.models import TopicMember
from kb_engine.pipeline import count_inbox, run_pipeline, unfiled_notes
from kb_engine.search import hybrid_search
from kb_engine.store import SLUG_PATTERN, Store, is_valid_slug
from kb_engine.surface import related_to_note, related_to_query
from kb_engine.synthesis import synthesis_candidates
from kb_engine.sync import rebuild as rebuild_index
from kb_engine.sync import sync as sync_index
from kb_engine.topics.areas import build_areas
from kb_engine.topics.assignment import assign_notes
from kb_engine.topics.clustering import Clusterer, FakeClusterer, UmapHdbscanClusterer
from kb_engine.topics.discover import discover_topics
from kb_engine.topics.sticky import sticky_discover
from kb_engine.topics.apply import apply_topic_tags
from kb_engine.topics.render import render_topics
from kb_engine.topics.taxonomy import diff_taxonomy, parse_taxonomy_tags

DEFAULT_SEARCH_LIMIT = 10
DEFAULT_SYNTHESIS_MIN = 5
DEFAULT_AREA_THRESHOLD = 0.3
DEFAULT_ASSIGN_HIGH = 0.55
DEFAULT_ASSIGN_LOW = 0.4
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
    if bool(query) == bool(to_note):
        raise click.UsageError("Pass exactly one of --query or --to.")
    store = Store(cfg.db_path)
    try:
        store.init_schema()  # tolerate a never-synced DB
        if query:
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
@click.option(
    "--sticky",
    is_flag=True,
    help="Assign notes to existing active topics first, cluster only the residual.",
)
@click.option(
    "--high",
    default=DEFAULT_ASSIGN_HIGH,
    show_default=True,
    type=float,
    help="Cosine threshold for assigning a note to an existing topic (--sticky).",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_discover(cfg: Config, sticky: bool, high: float, as_json: bool) -> None:
    """Cluster note vectors into topics (UMAP→HDBSCAN) and persist them.

    With ``--sticky``, notes scoring ``>= --high`` against an existing active
    topic are kept on that topic and only the residual is clustered into new
    proposals.
    """
    store = Store(cfg.db_path)
    if sticky:
        try:
            store.init_schema()
            sticky_result = sticky_discover(store, _build_clusterer(), high=high)
        finally:
            store.close()
        payload = {
            "sticky": True,
            "n_assigned_existing": sticky_result.n_assigned_existing,
            "n_new_topics": sticky_result.n_new_topics,
            "n_unfiled": sticky_result.n_unfiled,
        }
        _emit(
            payload,
            as_json,
            f"Sticky discover: assigned_existing={sticky_result.n_assigned_existing} "
            f"new_topics={sticky_result.n_new_topics} "
            f"unfiled={sticky_result.n_unfiled}",
        )
        return
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
            db, status=status, areas=list(areas) or None, projects=list(projects) or None
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
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def pipeline(cfg: Config, as_json: bool) -> None:
    """Run the deterministic maintenance pipeline (sync → apply → discover → digest).

    LLM-free and safe to run unattended: it embeds new/changed notes, applies
    ``topic/<slug>`` tags for *active* topics only (proposals stay proposed, so
    nothing is silently mis-tagged), clusters the residual into new proposals,
    and writes ``_system/kb-digest.md``. This is what the weekly launchd agent runs.
    """
    store = Store(cfg.db_path)
    try:
        result = run_pipeline(
            cfg, store, _build_embedder(cfg), _build_clusterer()
        )
    finally:
        store.close()
    _emit(
        {
            "synced": result.synced,
            "applied": result.applied,
            "proposals": result.proposals,
            "inbox": result.inbox,
            "unfiled": result.unfiled,
            "digest_path": result.digest_path,
        },
        as_json,
        f"Pipeline: synced={result.synced} applied={result.applied} "
        f"proposals={result.proposals} inbox={result.inbox} "
        f"unfiled={result.unfiled} -> {result.digest_path}",
    )


if __name__ == "__main__":
    main()
