import json
import os
import sys
from datetime import date
from pathlib import Path

import click

from kb_engine.backfill import DEFAULT_LIMIT as DEFAULT_BACKFILL_LIMIT
from kb_engine.backfill import backfill_content
from kb_engine.config import Config
from kb_engine.filing import apply_dispositions
from kb_engine.importing.inbox import existing_urls, import_urls
from kb_engine.importing.mail_notes import (
    DEFAULT_KB_LABEL,
    DEFAULT_MAIL_LIMIT,
    run_import_mail,
)
from kb_engine.importing.things import read_things_tasks
from kb_engine.importing.urls import normalize_url
from kb_engine.inbox_check import check_inbox
from kb_engine.store import Store

from kb_engine.commands._shared import _emit

# DEFAULT_KB_LABEL / DEFAULT_MAIL_LIMIT live in kb_engine.importing.mail_notes
# (imported above) so the import-mail flags and the pipeline share one default.

# Standard Things 3 SQLite location on macOS.
_THINGS_DB_GLOB = "Library/Group Containers/*ThingsMac*/**/main.sqlite"
_IMPORT_SAMPLE_SIZE = 5


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


@click.command("import-mail")
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


@click.command("backfill-content")
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


@click.command("import-things")
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


@click.command("inbox-check")
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


@click.command("file")
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
