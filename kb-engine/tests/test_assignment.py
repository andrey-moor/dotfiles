import json

import numpy as np
from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.models import Topic, TopicMember
from kb_engine.store import Store
from kb_engine.topics.assignment import assign_notes


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
    assigned, borderline = assign_notes(note_vecs, topics, high=0.9, low=0.5)
    assert assigned["Knowledge/a.md"][0] == "rust"
    assert "Knowledge/b.md" in {p for p, _ in borderline}  # between low and high


def test_assign_below_low_is_unassigned():
    topics = [_t("rust", [1, 0, 0])]
    assigned, borderline = assign_notes(
        {"Knowledge/x.md": np.array([0, 1, 0], np.float32)},
        topics,
        high=0.9,
        low=0.5,
    )
    assert assigned == {} and borderline == []


def test_assign_skips_zero_norm_centroid():
    topics = [_t("zero", [0, 0, 0]), _t("rust", [1, 0, 0])]
    assigned, _ = assign_notes(
        {"Knowledge/a.md": np.array([1, 0, 0], np.float32)},
        topics,
        high=0.9,
        low=0.5,
    )
    assert assigned["Knowledge/a.md"][0] == "rust"  # zero-norm topic ignored


def test_assign_tie_break_is_deterministic():
    # Both centroids equidistant from the note; the lexicographically-larger
    # slug wins, regardless of input ordering.
    topics = [_t("alpha", [1, 0, 0]), _t("omega", [1, 0, 0])]
    note = {"Knowledge/a.md": np.array([1, 0, 0], np.float32)}
    a1, _ = assign_notes(note, topics, high=0.5, low=0.1)
    a2, _ = assign_notes(note, list(reversed(topics)), high=0.5, low=0.1)
    assert a1["Knowledge/a.md"][0] == a2["Knowledge/a.md"][0] == "omega"


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
        main, args + ["topics", "assign", "--high", "-1", "--low", "-1", "--json"]
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
        main, args + ["topics", "assign", "--high", "-1", "--low", "-1", "--apply"]
    )
    assert r.exit_code == 0
    assert len(Store(db).topic_members("rust")) >= 1  # members persisted
