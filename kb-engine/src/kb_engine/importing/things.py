"""Read open URL-bearing tasks from a local Things 3 SQLite database.

The DB is read by copying it (plus any ``-wal``/``-shm`` sidecars) to a temp
file and opening that copy read-only, which is safe to do while Things itself
has the database open. The temp copy is always cleaned up.

Things schema (grounded against the real DB): ``TMTask(type, status, trashed,
title, notes, area→TMArea.uuid, project→TMTask.uuid, uuid)`` and
``TMArea(uuid, title)``. We keep ``type=0`` (task, not project/heading),
``trashed=0``, and an optional status filter (open=0, completed=3).
"""

import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from kb_engine.importing.urls import extract_urls

# Things status codes.
_STATUS_OPEN = 0
_STATUS_COMPLETED = 3
_STATUS_FILTERS: dict[str, int | None] = {
    "open": _STATUS_OPEN,
    "completed": _STATUS_COMPLETED,
    "all": None,
}

_SIDECAR_SUFFIXES = ("-wal", "-shm")


@dataclass(frozen=True)
class ThingsTask:
    title: str
    notes: str
    area: str | None
    project: str | None
    urls: tuple[str, ...]


def _copy_db_readonly(db_path: Path, dest_dir: Path) -> Path:
    """Copy the DB (+ wal/shm sidecars) into ``dest_dir``; return the copy path."""
    dest = dest_dir / db_path.name
    shutil.copy2(db_path, dest)
    for suffix in _SIDECAR_SUFFIXES:
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, dest.with_name(dest.name + suffix))
    return dest


def _query(conn: sqlite3.Connection, status: str) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    where = ["t.type = 0", "t.trashed = 0"]
    params: list[object] = []
    status_value = _STATUS_FILTERS[status]
    if status_value is not None:
        where.append("t.status = ?")
        params.append(status_value)
    sql = f"""
        SELECT t.title AS title, t.notes AS notes,
               area.title AS area_title, proj.title AS project_title
        FROM TMTask t
        LEFT JOIN TMArea area ON area.uuid = t.area
        LEFT JOIN TMTask proj ON proj.uuid = t.project
        WHERE {" AND ".join(where)}
        ORDER BY t.uuid
    """
    return conn.execute(sql, params).fetchall()


def read_things_tasks(
    db_path: str | Path,
    status: str = "open",
    areas: list[str] | None = None,
    projects: list[str] | None = None,
) -> list[ThingsTask]:
    """Return URL-bearing Things tasks matching the filters (read-only, safe).

    ``status`` is one of ``open`` (default), ``completed``, or ``all``. ``areas``
    and ``projects`` (if given) filter by exact area/project title. Only tasks
    with at least one extracted URL (from title or notes) are returned.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Things DB not found: {db_path}")
    if status not in _STATUS_FILTERS:
        raise ValueError(
            f"invalid status {status!r}: expected one of {sorted(_STATUS_FILTERS)}"
        )

    area_filter = set(areas) if areas else None
    project_filter = set(projects) if projects else None

    with tempfile.TemporaryDirectory(prefix="kb-things-") as tmp:
        copy_path = _copy_db_readonly(db_path, Path(tmp))
        conn = sqlite3.connect(f"file:{copy_path}?mode=ro", uri=True)
        try:
            rows = _query(conn, status)
        finally:
            conn.close()

    tasks: list[ThingsTask] = []
    for row in rows:
        area = row["area_title"]
        project = row["project_title"]
        if area_filter is not None and area not in area_filter:
            continue
        if project_filter is not None and project not in project_filter:
            continue
        title = row["title"] or ""
        notes = row["notes"] or ""
        urls = tuple(extract_urls(title) + extract_urls(notes))
        if not urls:
            continue
        tasks.append(
            ThingsTask(
                title=title, notes=notes, area=area, project=project, urls=urls
            )
        )
    return tasks
