"""One-time generator: copy ~58 real note vectors from the live DB into
tests/fixtures/real_vectors.{npy,json}.

Run from kb-engine/:  uv run python scripts/generate_real_vectors.py
Requires the live populated DB (post-Phase-3 re-embed). Deterministic given
the DB state. Re-run only deliberately — tests key off group labels, not paths.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np

DB = Path.home() / ".local" / "state" / "kb-engine" / "kb-engine.db"
OUT_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
MEMBERS_PER_TOPIC = 2
NEARDUP_PAIRS = 5
UNFILED_COUNT = 4


def main() -> None:
    conn = sqlite3.connect(f"file:{DB}?immutable=1", uri=True)
    vec: dict[str, np.ndarray] = {}
    text: dict[str, str] = {}
    for path, t, blob in conn.execute("SELECT note_path, text, vector FROM chunks"):
        vec[path] = np.frombuffer(blob, np.float32)
        text[path] = t

    selected: dict[str, str] = {}  # path -> group (first assignment wins)

    manual = [r[0] for r in conn.execute(
        "SELECT slug FROM topics WHERE kind='manual' AND status='active' ORDER BY slug"
    )]
    for slug in manual:
        rows = conn.execute(
            "SELECT note_path FROM topic_members WHERE topic_slug=? "
            "ORDER BY score DESC, note_path LIMIT ?",
            (slug, MEMBERS_PER_TOPIC + 2),
        ).fetchall()
        picked = 0
        for (p,) in rows:
            if picked >= MEMBERS_PER_TOPIC:
                break
            if p in vec and p not in selected:
                selected[p] = f"topic:{slug}"
                picked += 1

    paths = sorted(vec)
    mat = np.vstack([vec[p] for p in paths])
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    sim = (mat / norms) @ (mat / norms).T
    iu = np.triu_indices(len(paths), k=1)
    order = np.argsort(sim[iu])[::-1]
    pair_i = 0
    for idx in order:
        if pair_i >= NEARDUP_PAIRS:
            break
        a, b = paths[iu[0][idx]], paths[iu[1][idx]]
        if a in selected or b in selected:
            continue
        selected[a] = f"neardup:{pair_i}"
        selected[b] = f"neardup:{pair_i}"
        pair_i += 1

    in_topic = {r[0] for r in conn.execute("SELECT DISTINCT note_path FROM topic_members")}
    unfiled = 0
    for p in paths:
        if unfiled >= UNFILED_COUNT:
            break
        if p not in in_topic and p not in selected:
            selected[p] = "unfiled"
            unfiled += 1
    conn.close()

    ordered = sorted(selected)
    matrix = np.vstack([vec[p] for p in ordered]).astype(np.float32)
    entries = [{"path": p, "group": selected[p], "text": text[p]} for p in ordered]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUT_DIR / "real_vectors.npy", matrix)
    (OUT_DIR / "real_vectors.json").write_text(json.dumps(entries, indent=1))
    print(f"wrote {len(ordered)} vectors: "
          f"{sum(1 for g in selected.values() if g.startswith('topic:'))} topic members, "
          f"{2 * pair_i} near-dup, {unfiled} unfiled")


if __name__ == "__main__":
    main()
