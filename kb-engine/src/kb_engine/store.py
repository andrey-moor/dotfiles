import json
import re
import sqlite3
from pathlib import Path
from typing import Iterator

import numpy as np

from kb_engine.importing.urls import normalize_url
from kb_engine.models import Area, QueueEntry, Topic, TopicMember
from kb_engine.topics._math import frozen_centroid

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  path TEXT PRIMARY KEY, title TEXT, sha256 TEXT NOT NULL, tags TEXT, summary TEXT,
  url TEXT, message_id TEXT
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY, note_path TEXT NOT NULL, ordinal INTEGER NOT NULL,
  text TEXT NOT NULL, vector BLOB NOT NULL,
  FOREIGN KEY(note_path) REFERENCES notes(path) ON DELETE CASCADE
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, note_path UNINDEXED);
CREATE TABLE IF NOT EXISTS topics (
  slug TEXT PRIMARY KEY, label TEXT, keywords TEXT, centroid BLOB NOT NULL,
  kind TEXT NOT NULL, status TEXT NOT NULL,
  anchor_source TEXT NOT NULL DEFAULT 'label',
  threshold_high REAL, threshold_secondary REAL,
  area TEXT,
  threshold_derived_n INTEGER
);
CREATE TABLE IF NOT EXISTS topic_members (
  topic_slug TEXT NOT NULL, note_path TEXT NOT NULL, score REAL, source TEXT,
  is_primary INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (topic_slug, note_path),
  FOREIGN KEY (topic_slug) REFERENCES topics(slug) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS areas (
  slug TEXT PRIMARY KEY, label TEXT, description TEXT
);
CREATE TABLE IF NOT EXISTS area_members (
  area_slug TEXT NOT NULL, topic_slug TEXT NOT NULL,
  PRIMARY KEY (area_slug, topic_slug),
  FOREIGN KEY (area_slug) REFERENCES areas(slug) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  kind TEXT NOT NULL,
  query TEXT,
  top_path TEXT,
  hit_rank INTEGER
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  command TEXT NOT NULL,
  tier TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  ok INTEGER,
  counts TEXT,
  errors TEXT
);
CREATE TABLE IF NOT EXISTS review_queue (
  note_path TEXT PRIMARY KEY,
  candidates TEXT NOT NULL,
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

# FTS terms = unicode word runs that may contain mid-word hyphens (e.g.
# "jina-v3", "GPT-4", "café"). Leading/trailing punctuation is stripped; a
# lone word char still matches via the final alternative.
_FTS_TOKEN_RE = re.compile(r"\w[\w\-]*\w|\w", re.UNICODE)

# Topic slugs become filenames under _system/topics/, so they must be a single
# safe path segment: lowercase alphanumerics + internal hyphens only. This
# blocks path traversal (e.g. "../escape") at the input boundary.
SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]*$"
_SLUG_RE = re.compile(SLUG_PATTERN)


def is_valid_slug(slug: str) -> bool:
    """True if ``slug`` is a safe single path segment (see ``SLUG_PATTERN``)."""
    return bool(_SLUG_RE.match(slug))


def _next_free_slug(base: str, taken: set[str]) -> str:
    """Return ``base`` if free, else ``base-2``, ``base-3``, … (deterministic)."""
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


def _to_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, np.float32).tobytes()


def _from_blob(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, np.float32)


def _sanitize_fts_query(query: str) -> str:
    """Quote each term so user input can't break the FTS5 MATCH grammar."""
    terms = _FTS_TOKEN_RE.findall(query)
    return " ".join(f'"{t}"' for t in terms)


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")

    def init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        # Backfill for databases created before summary was added to _SCHEMA.
        self._ensure_column("notes", "summary", "TEXT")
        # Backfill for databases created before is_primary was added to _SCHEMA.
        self._ensure_column("topic_members", "is_primary", "INTEGER NOT NULL DEFAULT 1")
        # Backfill for databases created before url/message_id were added to _SCHEMA.
        self._ensure_column("notes", "url", "TEXT")
        self._ensure_column("notes", "message_id", "TEXT")
        # Backfill for databases created before mtime/size (stat-prefilter) were added.
        self._ensure_column("notes", "mtime", "REAL")
        self._ensure_column("notes", "size", "INTEGER")
        # Backfill for databases created before topic re-anchoring (Phase 4).
        self._ensure_column("topics", "anchor_source", "TEXT NOT NULL DEFAULT 'label'")
        # Backfill for databases created before per-topic thresholds (Phase 4).
        self._ensure_column("topics", "threshold_high", "REAL")
        self._ensure_column("topics", "threshold_secondary", "REAL")
        # Backfill for databases created before the areas→topics hierarchy (Phase 5).
        self._ensure_column("topics", "area", "TEXT")
        self._ensure_column("areas", "description", "TEXT")
        # Backfill for databases created before growth-gated re-derive (Phase 6).
        self._ensure_column("topics", "threshold_derived_n", "INTEGER")
        self._conn.commit()

    def _ensure_column(self, table: str, column: str, decl: str) -> None:
        cols = {row[1] for row in self._conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def upsert_note(
        self,
        path: str,
        title: str,
        sha256: str,
        tags: list[str],
        summary: str = "",
        url: str | None = None,
        message_id: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO notes(path, title, sha256, tags, summary, url, message_id)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET title=excluded.title,
                sha256=excluded.sha256, tags=excluded.tags, summary=excluded.summary,
                url=excluded.url, message_id=excluded.message_id
            """,
            (path, title, sha256, json.dumps(list(tags)), summary, url, message_id),
        )
        self._conn.commit()

    def existing_urls(self) -> set[str]:
        """Return the set of normalized URLs stored in the cache."""
        rows = self._conn.execute(
            "SELECT url FROM notes WHERE url IS NOT NULL AND url != ''"
        ).fetchall()
        return {normalize_url(row[0]) for row in rows}

    def existing_message_ids(self) -> set[str]:
        """Return the set of message IDs stored in the cache."""
        rows = self._conn.execute(
            "SELECT message_id FROM notes WHERE message_id IS NOT NULL AND message_id != ''"
        ).fetchall()
        return {row[0] for row in rows}

    def set_note_metadata(self, path: str, url: str | None, message_id: str | None) -> None:
        """Patch just the url/message_id of an already-indexed note (no re-embed)."""
        self._conn.execute(
            "UPDATE notes SET url = ?, message_id = ? WHERE path = ?", (url, message_id, path)
        )
        self._conn.commit()

    def note_summary(self, note_path: str) -> str | None:
        row = self._conn.execute(
            "SELECT summary FROM notes WHERE path=?", (note_path,)
        ).fetchone()
        return row[0] if row else None

    def replace_chunks(
        self, note_path: str, chunks: list[tuple[int, str, np.ndarray]]
    ) -> None:
        self._conn.execute("DELETE FROM chunks WHERE note_path=?", (note_path,))
        self._conn.execute("DELETE FROM chunks_fts WHERE note_path=?", (note_path,))
        for ordinal, text, vector in chunks:
            self._conn.execute(
                "INSERT INTO chunks(note_path, ordinal, text, vector) VALUES(?, ?, ?, ?)",
                (note_path, ordinal, text, _to_blob(vector)),
            )
            self._conn.execute(
                "INSERT INTO chunks_fts(text, note_path) VALUES(?, ?)",
                (text, note_path),
            )
        self._conn.commit()

    def delete_note(self, note_path: str) -> None:
        # FTS is a standalone table (no content-table), so delete its rows manually.
        self._conn.execute("DELETE FROM chunks_fts WHERE note_path=?", (note_path,))
        self._conn.execute("DELETE FROM notes WHERE path=?", (note_path,))
        self._conn.commit()

    def note_sha(self, note_path: str) -> str | None:
        row = self._conn.execute(
            "SELECT sha256 FROM notes WHERE path=?", (note_path,)
        ).fetchone()
        return row[0] if row else None

    def all_note_shas(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT path, sha256 FROM notes").fetchall()
        return {path: sha for path, sha in rows}

    def all_note_stats(self) -> dict[str, tuple[str, float | None, int | None]]:
        """Return ``{path: (sha256, mtime, size)}`` for the stat-prefiltered sync."""
        rows = self._conn.execute("SELECT path, sha256, mtime, size FROM notes").fetchall()
        return {r[0]: (r[1], r[2], r[3]) for r in rows}

    def set_note_stat(self, path: str, mtime: float, size: int) -> None:
        """Refresh the stored mtime/size for an already-indexed note (no re-embed)."""
        with self._conn:
            self._conn.execute(
                "UPDATE notes SET mtime = ?, size = ? WHERE path = ?", (mtime, size, path)
            )

    def notes_by_tag(self) -> dict[str, set[str]]:
        """Return ``{tag: {note_path, ...}}`` built from each note's tags JSON.

        Untagged notes contribute nothing. Used by the restructure-diff to map
        existing taxonomy tags onto discovered topic membership.
        """
        by_tag: dict[str, set[str]] = {}
        for path, tags_json in self._conn.execute(
            "SELECT path, tags FROM notes"
        ).fetchall():
            for tag in json.loads(tags_json) if tags_json else []:
                by_tag.setdefault(tag, set()).add(path)
        return by_tag

    def notes_without_topic(self) -> dict[str, list[str]]:
        """Return ``{note_path: [taxonomy tags]}`` for notes in NO topic_members row.

        Membership is the source of truth for "filed"; a note with any topic
        membership (primary or secondary) is excluded. ``topic/...`` tags are
        stripped from the returned list so only coarse taxonomy tags remain.
        """
        in_topic = {
            p for (p,) in self._conn.execute(
                "SELECT DISTINCT note_path FROM topic_members"
            )
        }
        out: dict[str, list[str]] = {}
        for path, tags_json in self._conn.execute("SELECT path, tags FROM notes"):
            if path in in_topic:
                continue
            tags = [
                t
                for t in (json.loads(tags_json) if tags_json else [])
                if not t.startswith("topic/")
            ]
            out[path] = tags
        return out

    def note_title(self, note_path: str) -> str | None:
        row = self._conn.execute(
            "SELECT title FROM notes WHERE path=?", (note_path,)
        ).fetchone()
        return row[0] if row else None

    def iter_vectors(self) -> Iterator[tuple[str, int, np.ndarray]]:
        for note_path, ordinal, blob in self._conn.execute(
            "SELECT note_path, ordinal, vector FROM chunks ORDER BY note_path, ordinal"
        ):
            yield note_path, ordinal, _from_blob(blob)

    def note_vectors(self) -> Iterator[tuple[str, np.ndarray]]:
        """Yield one mean-pooled vector per note, ordered by note path.

        Chunk vectors for a note are averaged into a single note-level vector.
        """
        current_path: str | None = None
        acc: list[np.ndarray] = []
        for note_path, _ordinal, vector in self.iter_vectors():
            if note_path != current_path:
                if current_path is not None:
                    yield current_path, np.mean(acc, axis=0).astype(np.float32)
                current_path = note_path
                acc = []
            acc.append(vector)
        if current_path is not None:
            yield current_path, np.mean(acc, axis=0).astype(np.float32)

    def note_vectors_for(self, paths: list[str]) -> dict[str, np.ndarray]:
        """Mean-pooled note vectors for just ``paths`` (missing paths omitted)."""
        out: dict[str, list[np.ndarray]] = {}
        marks = ",".join("?" for _ in paths)
        if not paths:
            return {}
        for note_path, blob in self._conn.execute(
            f"SELECT note_path, vector FROM chunks WHERE note_path IN ({marks})",
            list(paths),
        ):
            out.setdefault(note_path, []).append(_from_blob(blob))
        return {
            p: np.mean(vs, axis=0).astype(np.float32) for p, vs in out.items()
        }

    def note_texts(self) -> dict[str, str]:
        """Return ``{note_path: "title summary"}`` for keyword (c-TF-IDF) labeling.

        Uses the stored summary (not chunk/body text) so labels stay topical and
        free of body noise (handles, URLs, IDs).
        """
        rows = self._conn.execute("SELECT path, title, summary FROM notes").fetchall()
        texts: dict[str, str] = {}
        for path, title, summary in rows:
            parts = [part for part in (title, summary) if part]
            texts[path] = " ".join(parts)
        return texts

    def save_topics(
        self,
        topics: list[Topic],
        members_by_slug: dict[str, list[TopicMember]],
    ) -> None:
        """Persist discovered topics + members in a single transaction.

        Existing ``kind='discovered'`` topics are deleted first (cascading their
        members) so a re-discover replaces stale proposals, while ``kind='manual'``
        topics are left untouched. If an incoming discovered slug collides with a
        retained (non-discovered) slug, it is deterministically suffixed
        (``-2``, ``-3``, …) instead of raising a UNIQUE error — its members are
        re-keyed to match.
        """
        retained = {
            slug
            for (slug,) in self._conn.execute(
                "SELECT slug FROM topics WHERE kind != 'discovered'"
            )
        }
        taken = set(retained)
        with self._conn:
            self._conn.execute("DELETE FROM topics WHERE kind='discovered'")
            for topic in topics:
                slug = _next_free_slug(topic.slug, taken)
                taken.add(slug)
                self._conn.execute(
                    """
                    INSERT INTO topics(slug, label, keywords, centroid, kind, status,
                        anchor_source, threshold_high, threshold_secondary, area,
                        threshold_derived_n)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        slug,
                        topic.label,
                        json.dumps(list(topic.keywords)),
                        _to_blob(topic.centroid),
                        topic.kind,
                        topic.status,
                        topic.anchor_source,
                        topic.threshold_high,
                        topic.threshold_secondary,
                        topic.area,
                        topic.threshold_derived_n,
                    ),
                )
                for member in members_by_slug.get(topic.slug, []):
                    self._conn.execute(
                        """
                        INSERT INTO topic_members(topic_slug, note_path, score, source, is_primary)
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        (slug, member.note_path, member.score, member.source,
                         int(member.is_primary)),
                    )

    def load_topics(self) -> list[Topic]:
        rows = self._conn.execute(
            "SELECT slug, label, keywords, centroid, kind, status, anchor_source, "
            "threshold_high, threshold_secondary, area, threshold_derived_n "
            "FROM topics ORDER BY slug"
        ).fetchall()
        return [
            Topic(
                slug=slug,
                label=label,
                keywords=tuple(json.loads(keywords)),
                centroid=frozen_centroid(_from_blob(centroid)),
                kind=kind,
                status=status,
                anchor_source=anchor_source,
                threshold_high=threshold_high,
                threshold_secondary=threshold_secondary,
                area=area,
                threshold_derived_n=threshold_derived_n,
            )
            for (
                slug, label, keywords, centroid, kind, status, anchor_source,
                threshold_high, threshold_secondary, area, threshold_derived_n,
            ) in rows
        ]

    def update_topic_anchor(
        self, slug: str, centroid: np.ndarray, anchor_source: str
    ) -> None:
        """Swap a topic's anchor centroid and record where it came from."""
        with self._conn:
            self._conn.execute(
                "UPDATE topics SET centroid = ?, anchor_source = ? WHERE slug = ?",
                (_to_blob(centroid), anchor_source, slug),
            )

    def set_topic_thresholds(
        self, slug: str, high: float, secondary: float, derived_n: int
    ) -> None:
        """Persist a topic's derived assignment thresholds.

        ``derived_n`` records the member count the derivation saw, so a later
        pass can gate re-derivation on membership growth (see persist_thresholds).
        """
        with self._conn:
            self._conn.execute(
                "UPDATE topics SET threshold_high = ?, threshold_secondary = ?, "
                "threshold_derived_n = ? WHERE slug = ?",
                (high, secondary, derived_n, slug),
            )

    def set_topic_area(self, slug: str, area: str | None) -> None:
        """Assign a topic to a registry area (None clears it)."""
        with self._conn:
            self._conn.execute(
                "UPDATE topics SET area = ? WHERE slug = ?", (area, slug)
            )

    def add_manual_topic(
        self, slug: str, label: str, description: str, centroid: np.ndarray
    ) -> None:
        """Insert a ``kind='manual', status='active'`` topic anchored by ``centroid``.

        The description is stored as the topic's single keyword for later
        labeling context. Raises ``ValueError`` if the slug is malformed (it
        becomes a filename, so traversal-unsafe slugs are rejected) or already
        exists.
        """
        if not is_valid_slug(slug):
            raise ValueError(
                f"invalid topic slug {slug!r}: must match {SLUG_PATTERN}"
            )
        if self._conn.execute(
            "SELECT 1 FROM topics WHERE slug=?", (slug,)
        ).fetchone():
            raise ValueError(f"topic slug already exists: {slug}")
        self._conn.execute(
            """
            INSERT INTO topics(slug, label, keywords, centroid, kind, status)
            VALUES(?, ?, ?, ?, 'manual', 'active')
            """,
            (slug, label, json.dumps([description]), _to_blob(centroid)),
        )
        self._conn.commit()

    def topic_members(self, slug: str) -> list[TopicMember]:
        rows = self._conn.execute(
            """
            SELECT note_path, score, source, is_primary FROM topic_members
            WHERE topic_slug=? ORDER BY is_primary DESC, score DESC, note_path
            """,
            (slug,),
        ).fetchall()
        return [
            TopicMember(note_path=p, score=s, source=src, is_primary=bool(ip))
            for p, s, src, ip in rows
        ]

    def save_areas(self, areas: list[Area]) -> None:
        """Replace the areas REGISTRY (slug/label/description rows).

        Membership is not stored here: an area's topics are composed at read
        time from ``topics.area``. The legacy ``area_members`` table is no
        longer written (kept for old DBs; harmless)."""
        with self._conn:
            self._conn.execute("DELETE FROM areas")
            for area in areas:
                self._conn.execute(
                    "INSERT INTO areas(slug, label, description) VALUES(?, ?, ?)",
                    (area.slug, area.label, area.description),
                )

    def load_areas(self) -> list[Area]:
        by_area: dict[str, list[str]] = {}
        for slug, area in self._conn.execute(
            "SELECT slug, area FROM topics WHERE area IS NOT NULL ORDER BY slug"
        ):
            by_area.setdefault(area, []).append(slug)
        rows = self._conn.execute(
            "SELECT slug, label, description FROM areas ORDER BY slug"
        ).fetchall()
        return [
            Area(
                slug=slug,
                label=label,
                topic_slugs=tuple(by_area.get(slug, [])),
                description=description or "",
            )
            for slug, label, description in rows
        ]

    def set_members(self, slug: str, members: list[TopicMember]) -> None:
        """Add/update topic members additively (existing members are kept).

        Uses INSERT OR REPLACE on the (topic_slug, note_path) primary key, so a
        member already present is updated in place and new ones are appended
        without clearing the rest.
        """
        with self._conn:
            for member in members:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO topic_members(
                        topic_slug, note_path, score, source, is_primary
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (slug, member.note_path, member.score, member.source,
                     int(member.is_primary)),
                )

    def replace_auto_members(self, slug: str, members: list[TopicMember]) -> None:
        """Replace a topic's auto-sourced members wholesale (one weekly pass's
        truth). Human rows (source user/seed) are never touched — on a path
        collision the existing human row wins (INSERT OR IGNORE)."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM topic_members WHERE topic_slug = ? AND source = 'auto'",
                (slug,),
            )
            for member in members:
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO topic_members(
                        topic_slug, note_path, score, source, is_primary
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (slug, member.note_path, member.score, member.source,
                     int(member.is_primary)),
                )

    def user_primary_paths(self) -> set[str]:
        """Note paths a human has pinned as primary somewhere (assignment skips them)."""
        rows = self._conn.execute(
            "SELECT DISTINCT note_path FROM topic_members "
            "WHERE source = 'user' AND is_primary = 1"
        ).fetchall()
        return {row[0] for row in rows}

    def clear_auto_primaries(self, note_path: str) -> None:
        """Drop a note's auto primary rows — a human confirm supersedes them."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM topic_members "
                "WHERE note_path = ? AND source = 'auto' AND is_primary = 1",
                (note_path,),
            )

    def replace_review_queue(self, entries: list[QueueEntry]) -> None:
        """Rewrite the borderline review queue (one weekly pass's truth)."""
        with self._conn:
            self._conn.execute("DELETE FROM review_queue")
            for entry in entries:
                self._conn.execute(
                    "INSERT INTO review_queue(note_path, candidates, reason, created_at) "
                    "VALUES(?, ?, ?, datetime('now'))",
                    (
                        entry.note_path,
                        json.dumps([[slug, score] for slug, score in entry.candidates]),
                        entry.reason,
                    ),
                )

    def load_review_queue(self) -> list[QueueEntry]:
        """Queue entries, best top-candidate score first (ties by path)."""
        rows = self._conn.execute(
            "SELECT note_path, candidates, reason, created_at FROM review_queue"
        ).fetchall()
        entries = [
            QueueEntry(
                note_path=path,
                candidates=tuple(
                    (slug, float(score)) for slug, score in json.loads(candidates)
                ),
                reason=reason,
                created_at=created_at,
            )
            for path, candidates, reason, created_at in rows
        ]
        return sorted(
            entries,
            key=lambda e: (-(e.candidates[0][1] if e.candidates else 0.0), e.note_path),
        )

    def remove_from_review_queue(self, note_path: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM review_queue WHERE note_path = ?", (note_path,)
            )

    def keyword_search(self, query: str, limit: int = 20) -> list[tuple[str, float]]:
        match = _sanitize_fts_query(query)
        if not match:
            return []
        rows = self._conn.execute(
            """
            SELECT note_path, bm25(chunks_fts) AS rank
            FROM chunks_fts WHERE chunks_fts MATCH ?
            ORDER BY rank LIMIT ?
            """,
            (match, limit),
        ).fetchall()
        # More-negative bm25 rank = better match; ascending ORDER BY returns best first.
        best: dict[str, float] = {}
        order: list[str] = []
        for note_path, rank in rows:
            if note_path not in best:
                best[note_path] = float(rank)
                order.append(note_path)
        return [(p, best[p]) for p in order]

    def record_event(
        self,
        kind: str,
        query: str | None = None,
        top_path: str | None = None,
        hit_rank: int | None = None,
    ) -> None:
        """Append a local telemetry event (cache-local observability, not files-as-truth)."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO events (ts, kind, query, top_path, hit_rank) "
                "VALUES (datetime('now'), ?, ?, ?, ?)",
                (kind, query, top_path, hit_rank),
            )

    def count_events(self, kind: str | None = None) -> int:
        if kind is None:
            row = self._conn.execute("SELECT count(*) FROM events").fetchone()
        else:
            row = self._conn.execute(
                "SELECT count(*) FROM events WHERE kind = ?", (kind,)
            ).fetchone()
        return int(row[0])

    def start_run(self, command: str, tier: str | None = None) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO runs (command, tier, started_at) VALUES (?, ?, datetime('now'))",
                (command, tier),
            )
        return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        ok: bool,
        counts: dict | None = None,
        errors: list[str] | None = None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE runs SET finished_at = datetime('now'), ok = ?, counts = ?, errors = ? WHERE id = ?",
                (int(ok), json.dumps(counts or {}), json.dumps(errors or []), run_id),
            )

    def last_run(self, command: str | None = None) -> dict | None:
        sql = "SELECT command, tier, started_at, finished_at, ok, counts, errors FROM runs"
        params: tuple = ()
        if command is not None:
            sql += " WHERE command = ?"
            params = (command,)
        sql += " ORDER BY id DESC LIMIT 1"
        row = self._conn.execute(sql, params).fetchone()
        if row is None:
            return None
        return {
            "command": row[0],
            "tier": row[1],
            "started_at": row[2],
            "finished_at": row[3],
            "ok": None if row[4] is None else bool(row[4]),
            "counts": json.loads(row[5]) if row[5] else {},
            "errors": json.loads(row[6]) if row[6] else [],
        }

    def count_notes(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]

    def count_chunks(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def drop_all(self) -> None:
        self._conn.executescript(
            "DROP TABLE IF EXISTS chunks_fts;"
            "DROP TABLE IF EXISTS chunks;"
            "DROP TABLE IF EXISTS notes;"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
