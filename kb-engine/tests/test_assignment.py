import json

import numpy as np
import pytest
from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store
from kb_engine.topics.assignment import Assignment, assign_notes


def _t(slug, vec):
    return Topic(
        slug=slug,
        label=slug,
        keywords=(),
        centroid=np.array(vec, np.float32),
        kind="manual",
        status="active",
    )


def test_assign_high_and_borderline():
    topics = [_t("rust", [1, 0, 0]), _t("llm", [0, 0, 1])]
    note_vecs = {
        "Knowledge/a.md": np.array([0.98, 0.02, 0], np.float32),  # clearly rust
        "Knowledge/b.md": np.array([0.6, 0.0, 0.4], np.float32),  # borderline rust
    }
    assigned, borderline = assign_notes(note_vecs, topics, high=0.9, secondary=0.7, low=0.5)
    assert assigned["Knowledge/a.md"][0].slug == "rust"
    assert "Knowledge/b.md" in {p for p, _ in borderline}  # between low and high


def test_assign_below_low_is_unassigned():
    topics = [_t("rust", [1, 0, 0])]
    assigned, borderline = assign_notes(
        {"Knowledge/x.md": np.array([0, 1, 0], np.float32)},
        topics,
        high=0.9,
        secondary=0.7,
        low=0.5,
    )
    assert assigned == {} and borderline == []


def test_assign_skips_zero_norm_centroid():
    topics = [_t("zero", [0, 0, 0]), _t("rust", [1, 0, 0])]
    assigned, _ = assign_notes(
        {"Knowledge/a.md": np.array([1, 0, 0], np.float32)},
        topics,
        high=0.9,
        secondary=0.7,
        low=0.5,
    )
    assert assigned["Knowledge/a.md"][0].slug == "rust"  # zero-norm topic ignored


def test_assign_zero_note_vector_is_unassigned():
    # A zero-norm note vector yields cosine 0 against every topic → unassigned.
    topics = [_t("rust", [1, 0, 0])]
    assigned, borderline = assign_notes(
        {"Knowledge/z.md": np.zeros(3, np.float32)}, topics, high=0.9, secondary=0.7, low=0.5
    )
    assert assigned == {} and borderline == []


def test_assign_tie_break_is_deterministic():
    # Both centroids equidistant from the note; on a score tie the
    # lexicographically-SMALLER slug wins, regardless of input ordering.
    topics = [_t("alpha", [1, 0, 0]), _t("omega", [1, 0, 0])]
    note = {"Knowledge/a.md": np.array([1, 0, 0], np.float32)}
    a1, _ = assign_notes(note, topics, high=0.5, secondary=0.1, low=0.1)
    a2, _ = assign_notes(note, list(reversed(topics)), high=0.5, secondary=0.1, low=0.1)
    assert a1["Knowledge/a.md"][0].slug == a2["Knowledge/a.md"][0].slug == "alpha"


def test_set_members_is_additive(tmp_path):
    s = Store(tmp_path / "t.db")
    s.init_schema()
    t = Topic(
        slug="rust",
        label="Rust",
        keywords=(),
        centroid=np.ones(4, np.float32),
        kind="manual",
        status="active",
    )
    s.save_topics([t], {"rust": [TopicMember("Knowledge/a.md", 0.9, "seed")]})
    s.set_members("rust", [TopicMember("Knowledge/b.md", 0.95, "auto")])
    paths = {m.note_path for m in s.topic_members("rust")}
    assert paths == {"Knowledge/a.md", "Knowledge/b.md"}  # additive, not replacing
    # Re-setting an existing member updates it in place (INSERT OR REPLACE on PK).
    s.set_members("rust", [TopicMember("Knowledge/a.md", 0.5, "auto")])
    by_path = {m.note_path: m for m in s.topic_members("rust")}
    assert abs(by_path["Knowledge/a.md"].score - 0.5) < 1e-6
    assert by_path["Knowledge/a.md"].source == "auto"


def _assign_vault(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir()
    for n, (t, b) in {
        "a.md": ("A", "rust macros and borrow checker"),
        "b.md": ("B", "llm prompt tokens"),
    }.items():
        (k / n).write_text(f"---\ntitle: {t}\n---\n{b}")
    return tmp_path


def test_topics_assign_dry_run_does_not_write(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    v = _assign_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(
        main,
        args + ["topics", "add", "rust", "--label", "Rust", "--description", "rust"],
    )
    # Dry-run default: report only, no members persisted.
    r = CliRunner().invoke(
        main, args + ["topics", "assign", "--high", "-1", "--secondary", "-1", "--low", "-1", "--json"]
    )
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert "assigned" in out and "borderline" in out and "unassigned" in out
    assert Store(db).topic_members("rust") == []  # nothing written without --apply


def test_topics_assign_apply_persists_members(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    v = _assign_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(
        main,
        args + ["topics", "add", "rust", "--label", "Rust", "--description", "rust"],
    )
    # high=-1 forces every scored note to be high-confidence so --apply writes them.
    r = CliRunner().invoke(
        main, args + ["topics", "assign", "--high", "-1", "--secondary", "-1", "--low", "-1", "--apply"]
    )
    assert r.exit_code == 0
    assert len(Store(db).topic_members("rust")) >= 1  # members persisted


def _topic(slug, centroid, high=None, secondary=None):
    return Topic(
        slug=slug, label=slug.upper(), keywords=(slug,),
        centroid=np.asarray(centroid, np.float32), kind="manual", status="active",
        threshold_high=high, threshold_secondary=secondary,
    )


def test_assign_returns_primary_plus_capped_secondaries():
    topics = [_topic("a", [1, 0, 0]), _topic("b", [0.95, 0.31, 0]),
              _topic("c", [0.9, 0.0, 0.44]), _topic("d", [0.88, 0.2, 0.43])]
    vecs = {"Knowledge/n.md": np.asarray([1, 0.1, 0.1], np.float32)}
    assigned, borderline = assign_notes(vecs, topics, high=0.8, secondary=0.6, low=0.4)
    members = assigned["Knowledge/n.md"]
    primaries = [m for m in members if m.is_primary]
    secondaries = [m for m in members if not m.is_primary]
    assert len(primaries) == 1 and primaries[0].slug == "a"
    assert len(secondaries) == 2  # cap fires: 3 eligible -> exactly 2 taken
    assert all(m.score >= 0.6 for m in secondaries)


def test_assign_no_primary_when_below_high_is_borderline():
    topics = [_topic("a", [1, 0, 0])]
    vecs = {"Knowledge/n.md": np.asarray([0.5, 0.5, 0.7], np.float32)}
    assigned, borderline = assign_notes(vecs, topics, high=0.9, secondary=0.6, low=0.4)
    assert "Knowledge/n.md" not in assigned


def test_topics_assign_apply_persists_primary_and_secondary(tmp_path):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    # note closest to topic "a" (primary), also near "b" (secondary)
    store.add_manual_topic("a", "A", "a", np.array([1, 0, 0], np.float32))
    store.add_manual_topic("b", "B", "b", np.array([0, 1, 0], np.float32))
    store.upsert_note(path="Knowledge/n.md", title="N", sha256="h", tags=[])
    store.replace_chunks("Knowledge/n.md", [(0, "n", np.array([0.8, 0.6, 0], np.float32))])
    store.close()
    r = CliRunner().invoke(main, [
        "--vault", str(tmp_path), "--db", str(db),
        "topics", "assign", "--high", "0.7", "--secondary", "0.5", "--low", "0.3", "--apply",
    ])
    assert r.exit_code == 0, r.output
    s = Store(db)
    a_members = {m.note_path: m for m in s.topic_members("a")}
    b_members = {m.note_path: m for m in s.topic_members("b")}
    assert a_members["Knowledge/n.md"].is_primary is True
    assert b_members["Knowledge/n.md"].is_primary is False
    s.close()


def test_assign_rejects_secondary_above_high():
    topics = [_t("a", [1, 0, 0])]
    with pytest.raises(ValueError):
        assign_notes(
            {"Knowledge/n.md": np.array([1, 0, 0], np.float32)},
            topics, high=0.5, secondary=0.9, low=0.4,
        )


def test_topics_assign_text_counts_notes_not_rows(tmp_path):
    # A note with a primary + a secondary is ONE assigned note, not two rows.
    db = tmp_path / "t.db"
    store = Store(db); store.init_schema()
    store.add_manual_topic("a", "A", "a", np.array([1, 0, 0], np.float32))
    store.add_manual_topic("b", "B", "b", np.array([0, 1, 0], np.float32))
    store.upsert_note(path="Knowledge/n.md", title="N", sha256="h", tags=[])
    store.replace_chunks("Knowledge/n.md", [(0, "n", np.array([0.8, 0.6, 0], np.float32))])
    store.close()
    r = CliRunner().invoke(main, [
        "--vault", str(tmp_path), "--db", str(db),
        "topics", "assign", "--high", "0.7", "--secondary", "0.5", "--low", "0.3",
    ])
    assert r.exit_code == 0, r.output
    assert "assigned=1 " in r.output  # 1 note, despite 2 membership rows


def test_topics_assign_rejects_secondary_above_high_cleanly(tmp_path):
    # A bad threshold combo is a clean click UsageError (exit 2), not a traceback.
    r = CliRunner().invoke(
        main,
        [
            "--vault", str(tmp_path), "--db", str(tmp_path / "t.db"),
            "topics", "assign", "--high", "0.5", "--secondary", "0.9",
        ],
    )
    assert r.exit_code == 2
    assert "must be <= --high" in r.output


def _distinct_pair(real_vectors):
    """First fixture group pair where member 0 of g1 sits closer to its own
    centroid than to g2's — the geometric premise the tests below need
    (test_topic_groups_are_geometrically_distinct guarantees such pairs exist)."""
    groups = {}
    for e, row in zip(real_vectors.entries, real_vectors.matrix):
        if e["group"].startswith("topic:"):
            groups.setdefault(e["group"], []).append(row)
    items = list(groups.values())
    for i, v1 in enumerate(items):
        c1 = np.mean(v1, axis=0)
        c1 = c1 / np.linalg.norm(c1)
        for v2 in items[i + 1:]:
            c2 = np.mean(v2, axis=0)
            c2 = c2 / np.linalg.norm(c2)
            if float(v1[0] @ c1) > float(v1[0] @ c2):
                return v1, c1, v2, c2
    raise AssertionError("no geometrically distinct fixture group pair")


def test_per_topic_high_overrides_global(real_vectors):
    """A note failing a tight topic's bar but clearing a looser lower-ranked
    topic gets the looser topic as primary."""
    v1, c1, v2, c2 = _distinct_pair(real_vectors)
    note = v1[0]  # a member of g1
    s1 = float(note @ c1)
    s2 = float(note @ c2)
    assert s1 > s2
    # tight bar on its own topic (just above its score), loose on the other
    topics = [
        _topic("own", c1, high=s1 + 0.01, secondary=s1 - 0.02),
        _topic("other", c2, high=max(0.0, s2 - 0.01), secondary=max(0.0, s2 - 0.02)),
    ]
    assigned, borderline = assign_notes(
        {"n.md": note}, topics, high=0.99, secondary=0.98, low=0.0
    )
    assert "n.md" in assigned
    assert assigned["n.md"][0].slug == "other"
    assert assigned["n.md"][0].is_primary is True


def test_borderline_carries_top3_candidates(real_vectors):
    members = real_vectors.by_group("topic:")
    note = members[0][1]
    cents = []
    for i in range(3):
        c = members[i][1].astype(np.float64)
        cents.append((c / np.linalg.norm(c)).astype(np.float32))
    scores = sorted((float(note @ c) for c in cents), reverse=True)
    top = scores[0]
    topics = [
        _topic(f"t{i}", cents[i], high=top + 0.05, secondary=None) for i in range(3)
    ]
    assigned, borderline = assign_notes(
        {"n.md": note}, topics, high=top + 0.05, secondary=top + 0.04, low=0.0
    )
    assert assigned == {}
    assert len(borderline) == 1
    path, candidates = borderline[0]
    assert path == "n.md"
    assert 1 <= len(candidates) <= 3
    assert candidates[0][1] == pytest.approx(top, abs=1e-5)
    assert [c[1] for c in candidates] == sorted(
        [c[1] for c in candidates], reverse=True
    )


def test_secondary_uses_each_topics_own_bar(real_vectors):
    v1, c1, v2, c2 = _distinct_pair(real_vectors)
    note = v1[0]
    s2 = float(note @ c2)
    topics_loose = [
        _topic("home", c1, high=0.0, secondary=0.0),
        _topic("link", c2, high=0.99, secondary=max(0.0, s2 - 0.01)),
    ]
    assigned, _ = assign_notes({"n.md": note}, topics_loose, 0.99, 0.98, 0.0)
    slugs = [a.slug for a in assigned["n.md"]]
    assert slugs[0] == "home" and "link" in slugs
    topics_tight = [
        _topic("home", c1, high=0.0, secondary=0.0),
        _topic("link", c2, high=0.99, secondary=min(1.0, s2 + 0.01)),
    ]
    assigned2, _ = assign_notes({"n.md": note}, topics_tight, 0.99, 0.98, 0.0)
    assert [a.slug for a in assigned2["n.md"]] == ["home"]
