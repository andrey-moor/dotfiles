"""The ``topics`` command group — discover, govern, assign, and render the topic/area model."""
import json
from pathlib import Path

import click

from kb_engine.config import Config
from kb_engine.models import TopicMember
from kb_engine.store import SLUG_PATTERN, Store, is_valid_slug
from kb_engine.topics.anchoring import reanchor_topics
from kb_engine.topics.apply import apply_topic_tags
from kb_engine.topics.areas_registry import seed_areas
from kb_engine.topics.assignment import (
    DEFAULT_ASSIGN_HIGH,
    DEFAULT_ASSIGN_LOW,
    DEFAULT_ASSIGN_SECONDARY,
    assign_notes,
)
from kb_engine.topics.cutover import apply_cutover
from kb_engine.topics.discover import discover_topics
from kb_engine.topics.migration import (
    build_migration_proposal,
    parse_migration_proposal,
    render_migration_proposal,
)
from kb_engine.topics.render import render_topics
from kb_engine.topics.suggest import suggest_from_residual
from kb_engine.topics.taxonomy import diff_taxonomy, parse_taxonomy_tags
from kb_engine.topics.thresholds import derive_thresholds, persist_thresholds

from kb_engine.commands._shared import _build_clusterer, _build_embedder, _emit

# DEFAULT_ASSIGN_HIGH / SECONDARY / LOW are imported from topics.assignment (above).
_SUGGEST_MIN_CLUSTER_SIZE = 2  # surface two-note mini-themes below the adaptive floor
_ASSIGNABLE_STATUSES = frozenset({"active", "proposed"})
_TAXONOMY_RELPATH = Path("_system") / "_taxonomy.md"
DEFAULT_APPLY_STATUS = "active"


@click.group()
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


@topics.command("propose-migration")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_propose_migration(cfg: Config, as_json: bool) -> None:
    """Generate _system/migration-proposal.md for the human review gate.

    Proposes per-tag dispositions + topic→area assignments. Edit the decision
    columns, then run `topics migrate --proposal <path>` (dry-run first)."""
    taxonomy_path = cfg.vault_path / _TAXONOMY_RELPATH
    declared = parse_taxonomy_tags(taxonomy_path) if taxonomy_path.exists() else set()
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        proposal = build_migration_proposal(store, declared)
    finally:
        store.close()
    out_path = cfg.vault_path / "_system" / "migration-proposal.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_migration_proposal(proposal))
    _emit(
        {
            "path": str(out_path),
            "tags": len(proposal.dispositions),
            "topics": len(proposal.topic_areas),
        },
        as_json,
        f"Wrote {out_path} ({len(proposal.dispositions)} tags, "
        f"{len(proposal.topic_areas)} topic-area rows). Review + edit decisions.",
    )


@topics.command("migrate")
@click.option(
    "--proposal",
    "proposal_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="The human-approved _system/migration-proposal.md.",
)
@click.option("--apply", "apply_changes", is_flag=True,
              help="Execute. Default is dry-run (prints the diff, writes nothing).")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON instead of text.")
@click.pass_obj
def topics_migrate(cfg, proposal_path, apply_changes, as_json):
    """Apply the approved taxonomy migration (dry-run by default)."""
    try:
        proposal = parse_migration_proposal(proposal_path.read_text())
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    store = Store(cfg.db_path)
    try:
        store.init_schema()
        result = apply_cutover(
            store, cfg.vault_path, proposal, dry_run=not apply_changes
        )
    finally:
        store.close()
    payload = {
        "dry_run": not apply_changes,
        "notes_changed": result.notes_changed,
        "tags_dropped": result.tags_dropped,
        "topic_tags_added": result.topic_tags_added,
        "area_tags_added": result.area_tags_added,
        "topics_created": list(result.topics_created),
        "skipped_unreadable": list(result.skipped_unreadable),
        "diff": list(result.diff_lines),
    }
    if as_json:
        click.echo(json.dumps(payload))
        return
    for line in result.diff_lines:
        click.echo(line)
    click.echo(
        f"{'DRY-RUN — nothing written' if not apply_changes else 'APPLIED'}: "
        f"{result.notes_changed} notes · {result.tags_dropped} tags dropped · "
        f"{result.topic_tags_added} topic tags · {result.area_tags_added} area tags · "
        f"{len(result.topics_created)} new topic(s)"
    )


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
    secondary = high - 0.08. Persists unless --dry-run. Re-derives every topic
    unconditionally (the manual reset tool); the weekly pass, by contrast, only
    re-derives a topic on member growth to avoid self-tightening contraction."""
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
