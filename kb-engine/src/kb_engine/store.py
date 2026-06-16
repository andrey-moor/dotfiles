import json
import re
import sqlite3
from pathlib import Path
from typing import Iterator

import numpy as np

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  path TEXT PRIMARY KEY, title TEXT, sha256 TEXT NOT NULL, tags TEXT
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY, note_path TEXT NOT NULL, ordinal INTEGER NOT NULL,
  text TEXT NOT NULL, vector BLOB NOT NULL,
  FOREIGN KEY(note_path) REFERENCES notes(path) ON DELETE CASCADE
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, note_path UNINDEXED);
"""

# FTS terms = unicode word runs that may contain mid-word hyphens (e.g.
# "jina-v3", "GPT-4", "café"). Leading/trailing punctuation is stripped; a
# lone word char still matches via the final alternative.
_FTS_TOKEN_RE = re.compile(r"\w[\w\-]*\w|\w", re.UNICODE)


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
        self._conn.commit()

    def upsert_note(
        self, path: str, title: str, sha256: str, tags: list[str]
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO notes(path, title, sha256, tags) VALUES(?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET title=excluded.title,
                sha256=excluded.sha256, tags=excluded.tags
            """,
            (path, title, sha256, json.dumps(list(tags))),
        )
        self._conn.commit()

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
