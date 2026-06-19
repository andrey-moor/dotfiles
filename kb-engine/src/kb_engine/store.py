import json
import re
import sqlite3
from pathlib import Path
from typing import Iterator

import numpy as np

from kb_engine.models import Area, Topic, TopicMember
from kb_engine.topics._math import frozen_centroid

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  path TEXT PRIMARY KEY, title TEXT, sha256 TEXT NOT NULL, tags TEXT, summary TEXT
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY, note_path TEXT NOT NULL, ordinal INTEGER NOT NULL,
  text TEXT NOT NULL, vector BLOB NOT NULL,
  FOREIGN KEY(note_path) REFERENCES notes(path) ON DELETE CASCADE
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, note_path UNINDEXED);
CREATE TABLE IF NOT EXISTS topics (
  slug TEXT PRIMARY KEY, label TEXT, keywords TEXT, centroid BLOB NOT NULL,
  kind TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS topic_members (
  topic_slug TEXT NOT NULL, note_path TEXT NOT NULL, score REAL, source TEXT,
  PRIMARY KEY (topic_slug, note_path),
  FOREIGN KEY (topic_slug) REFERENCES topics(slug) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS areas (
  slug TEXT PRIMARY KEY, label TEXT
);
CREATE TABLE IF NOT EXISTS area_members (
  area_slug TEXT NOT NULL, topic_slug TEXT NOT NULL,
  PRIMARY KEY (area_slug, topic_slug),
  FOREIGN KEY (area_slug) REFERENCES areas(slug) ON DELETE CASCADE
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

    def init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        # Backfill for databases created before summary was added to _SCHEMA.
        self._ensure_column("notes", "summary", "TEXT")
        self._conn.commit()

    def _ensure_column(self, table: str, column: str, decl: str) -> None:
        cols = {row[1] for row in self._conn.execute(f"PRAGMA table_info({table})")}
        if column not in cols:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")

    def upsert_note(
        self, path: str, title: str, sha256: str, tags: list[str], summary: str = ""
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO notes(path, title, sha256, tags, summary) VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET title=excluded.title,
                sha256=excluded.sha256, tags=excluded.tags, summary=excluded.summary
            """,
            (path, title, sha256, json.dumps(list(tags)), summary),
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

    def note_texts(self) -> dict[str, str]:
        """Return ``{note_path: "title first-chunk-text"}`` for keyword labeling.

        Each note contributes its title plus the text of its first chunk
        (ordinal 0) — enough signal for c-TF-IDF labels without loading whole
        notes. Notes with no chunks contribute their title alone.
        """
        rows = self._conn.execute(
            """
            SELECT n.path, n.title, (
                SELECT text FROM chunks
                WHERE note_path = n.path ORDER BY ordinal LIMIT 1
            ) AS first_chunk
            FROM notes n
            """
        ).fetchall()
        texts: dict[str, str] = {}
        for path, title, first_chunk in rows:
            parts = [part for part in (title, first_chunk) if part]
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
                    INSERT INTO topics(slug, label, keywords, centroid, kind, status)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        slug,
                        topic.label,
                        json.dumps(list(topic.keywords)),
                        _to_blob(topic.centroid),
                        topic.kind,
                        topic.status,
                    ),
                )
                for member in members_by_slug.get(topic.slug, []):
                    self._conn.execute(
                        """
                        INSERT INTO topic_members(topic_slug, note_path, score, source)
                        VALUES(?, ?, ?, ?)
                        """,
                        (slug, member.note_path, member.score, member.source),
                    )

    def load_topics(self) -> list[Topic]:
        rows = self._conn.execute(
            "SELECT slug, label, keywords, centroid, kind, status FROM topics ORDER BY slug"
        ).fetchall()
        return [
            Topic(
                slug=slug,
                label=label,
                keywords=tuple(json.loads(keywords)),
                centroid=frozen_centroid(_from_blob(centroid)),
                kind=kind,
                status=status,
            )
            for slug, label, keywords, centroid, kind, status in rows
        ]

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
            SELECT note_path, score, source FROM topic_members
            WHERE topic_slug=? ORDER BY score DESC, note_path
            """,
            (slug,),
        ).fetchall()
        return [
            TopicMember(note_path=note_path, score=score, source=source)
            for note_path, score, source in rows
        ]

    def save_areas(self, areas: list[Area]) -> None:
        """Replace all areas + their members in a single transaction.

        Areas are a full re-grouping each run, so existing areas (and their
        cascading members) are cleared before inserting the new set.
        """
        with self._conn:
            self._conn.execute("DELETE FROM areas")
            for area in areas:
                self._conn.execute(
                    "INSERT INTO areas(slug, label) VALUES(?, ?)",
                    (area.slug, area.label),
                )
                for topic_slug in area.topic_slugs:
                    self._conn.execute(
                        "INSERT INTO area_members(area_slug, topic_slug) VALUES(?, ?)",
                        (area.slug, topic_slug),
                    )

    def load_areas(self) -> list[Area]:
        rows = self._conn.execute(
            "SELECT slug, label FROM areas ORDER BY slug"
        ).fetchall()
        areas: list[Area] = []
        for slug, label in rows:
            member_rows = self._conn.execute(
                "SELECT topic_slug FROM area_members WHERE area_slug=? ORDER BY topic_slug",
                (slug,),
            ).fetchall()
            areas.append(
                Area(
                    slug=slug,
                    label=label,
                    topic_slugs=tuple(topic_slug for (topic_slug,) in member_rows),
                )
            )
        return areas

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
                        topic_slug, note_path, score, source
                    ) VALUES(?, ?, ?, ?)
                    """,
                    (slug, member.note_path, member.score, member.source),
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
