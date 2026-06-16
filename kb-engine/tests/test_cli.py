import json

from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.store import Store


def _vault(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir()
    (k / "mem.md").write_text(
        "---\ntitle: Memory\ntags: [AI]\n---\nlong term memory for agents"
    )
    return tmp_path


def _invoke(args, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    return CliRunner().invoke(main, args)


def test_sync_then_search_json(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = _invoke(["--vault", str(v), "--db", str(db), "sync", "--json"], monkeypatch)
    assert r.exit_code == 0
    assert json.loads(r.output)["added"] == 1

    r2 = _invoke(
        ["--vault", str(v), "--db", str(db), "search", "memory", "--json"], monkeypatch
    )
    assert r2.exit_code == 0
    hits = json.loads(r2.output)["hits"]
    assert hits and hits[0]["note_path"] == "Knowledge/mem.md"
    assert hits[0]["title"] == "Memory"


def test_search_resolves_titles_human_output(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    _invoke(["--vault", str(v), "--db", str(db), "sync"], monkeypatch)
    r = _invoke(
        ["--vault", str(v), "--db", str(db), "search", "memory"], monkeypatch
    )
    assert r.exit_code == 0
    assert "Memory" in r.output


def test_status_json_reports_counts(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    _invoke(["--vault", str(v), "--db", str(db), "sync"], monkeypatch)
    r = _invoke(["--vault", str(v), "--db", str(db), "status", "--json"], monkeypatch)
    assert r.exit_code == 0
    status = json.loads(r.output)
    assert status["notes"] == 1
    assert status["chunks"] >= 1
    assert status["db_path"] == str(db)


def test_rebuild_json(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    _invoke(["--vault", str(v), "--db", str(db), "sync"], monkeypatch)
    r = _invoke(["--vault", str(v), "--db", str(db), "rebuild", "--json"], monkeypatch)
    assert r.exit_code == 0
    assert json.loads(r.output)["added"] == 1


def test_sync_human_output(tmp_path, monkeypatch):
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    r = _invoke(["--vault", str(v), "--db", str(db), "sync"], monkeypatch)
    assert r.exit_code == 0
    assert "added" in r.output.lower()


def _topics_vault(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir()
    notes = {
        "a.md": ("Rust A", "rust macros"),
        "b.md": ("Rust B", "rust borrow"),
        "c.md": ("LLM", "llm prompt"),
    }
    for name, (title, body) in notes.items():
        (k / name).write_text(f"---\ntitle: {title}\n---\n{body}")
    return tmp_path


def test_topics_discover_cli_json(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0,-1")
    v = _topics_vault(tmp_path)
    db = tmp_path / "t.db"
    CliRunner().invoke(main, ["--vault", str(v), "--db", str(db), "sync"])
    r = CliRunner().invoke(
        main, ["--vault", str(v), "--db", str(db), "topics", "discover", "--json"]
    )
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert out["n_topics"] == 1 and out["n_unfiled"] == 1
    assert out["topics"][0]["size"] == 2
    assert "slug" in out["topics"][0] and "keywords" in out["topics"][0]


def test_topics_discover_cli_human_output(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0,-1")
    v = _topics_vault(tmp_path)
    db = tmp_path / "t.db"
    CliRunner().invoke(main, ["--vault", str(v), "--db", str(db), "sync"])
    r = CliRunner().invoke(
        main, ["--vault", str(v), "--db", str(db), "topics", "discover"]
    )
    assert r.exit_code == 0
    assert "unfiled" in r.output.lower()


def test_topics_discover_on_unsynced_db_does_not_crash(tmp_path, monkeypatch):
    # Discover before ever syncing must init the schema, not raise "no such table".
    monkeypatch.setenv("KB_FAKE_CLUSTER", "")
    v = _topics_vault(tmp_path)
    db = tmp_path / "fresh.db"
    r = CliRunner().invoke(
        main, ["--vault", str(v), "--db", str(db), "topics", "discover", "--json"]
    )
    assert r.exit_code == 0
    assert r.exception is None
    out = json.loads(r.output)
    assert out["n_topics"] == 0 and out["n_unfiled"] == 0


def test_topics_discover_sticky_cli_json(tmp_path, monkeypatch):
    # CLI wiring of --sticky: emits the sticky payload shape and preserves the
    # manual topic. (Assignment geometry is covered deterministically in
    # test_sticky.py; fake embeddings are near-orthogonal so we don't assert
    # a specific assignment count here.)
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0,1")
    v = _topics_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(
        main,
        args
        + ["topics", "add", "rust", "--label", "Rust", "--description", "rust macros"],
    )
    r = CliRunner().invoke(
        main, args + ["topics", "discover", "--sticky", "--high", "0.9", "--json"]
    )
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert out["sticky"] is True
    assert {"n_assigned_existing", "n_new_topics", "n_unfiled"} <= out.keys()
    # the manual topic must still exist after a sticky re-discover
    slugs = {t.slug for t in Store(db).load_topics()}
    assert "rust" in slugs


def test_topics_areas_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0,1,1")
    v = tmp_path / "Knowledge"
    v.mkdir(parents=True)
    for n, (t, b) in {
        "a.md": ("A", "rust macros"),
        "b.md": ("B", "rust borrow"),
        "c.md": ("C", "llm prompt"),
        "d.md": ("D", "llm tokens"),
    }.items():
        (v / n).write_text(f"---\ntitle: {t}\n---\n{b}")
    db = tmp_path / "t.db"
    args = ["--vault", str(tmp_path), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(main, args + ["topics", "discover"])
    r = CliRunner().invoke(main, args + ["topics", "areas", "--json"])
    assert r.exit_code == 0
    assert "areas" in json.loads(r.output)


def _tagged_vault(tmp_path):
    # 3 notes; a,b tagged Dev/Rust, c tagged AI/RAG. _taxonomy.md declares both
    # plus an orphan tag (Home/Gear) carried by no note that clusters.
    k = tmp_path / "Knowledge"
    k.mkdir()
    notes = {
        "a.md": ("Rust A", "Dev/Rust", "rust macros"),
        "b.md": ("Rust B", "Dev/Rust", "rust borrow"),
        "c.md": ("RAG", "AI/RAG", "retrieval embeddings"),
    }
    for name, (title, tag, body) in notes.items():
        (k / name).write_text(f"---\ntitle: {title}\ntags: [{tag}]\n---\n{body}")
    sysdir = tmp_path / "_system"
    sysdir.mkdir()
    (sysdir / "_taxonomy.md").write_text(
        "## Categories\n"
        "- **Dev/Rust** — rust\n"
        "- **AI/RAG** — retrieval\n"
        "- **Home/Gear** — gear\n"
    )
    return tmp_path


def test_topics_diff_taxonomy_cli_json(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0,1")  # a,b -> topic0; c -> topic1
    v = _tagged_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(main, args + ["topics", "discover"])
    r = CliRunner().invoke(main, args + ["topics", "diff-taxonomy", "--json"])
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert {"mapping", "new_topics", "orphan_tags"} <= out.keys()
    # Dev/Rust (notes a,b) aligns with the topic holding a,b
    rust_ranked = out["mapping"]["Dev/Rust"]
    assert rust_ranked and rust_ranked[0]["overlap"] > 0
    # Home/Gear is declared but no note carries it -> not even in the diff inputs
    assert "Home/Gear" not in out["mapping"]


def test_topics_diff_taxonomy_missing_file_is_greenfield(tmp_path, monkeypatch):
    # No _taxonomy.md: every discovered topic is "new" (nothing to align against).
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0,1")
    k = tmp_path / "Knowledge"
    k.mkdir()
    for name, (title, body) in {
        "a.md": ("A", "rust macros"),
        "b.md": ("B", "rust borrow"),
        "c.md": ("C", "llm prompt"),
    }.items():
        (k / name).write_text(f"---\ntitle: {title}\ntags: [Dev/Rust]\n---\n{body}")
    db = tmp_path / "t.db"
    args = ["--vault", str(tmp_path), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(main, args + ["topics", "discover"])
    # point at a taxonomy path that does not exist
    missing = tmp_path / "nope.md"
    r = CliRunner().invoke(
        main, args + ["topics", "diff-taxonomy", "--taxonomy", str(missing), "--json"]
    )
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert out["mapping"] == {}
    assert out["orphan_tags"] == []
    # all discovered topics are new structure in greenfield
    assert len(out["new_topics"]) == 2


def test_topics_render_cli_writes_index(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0,-1")
    v = _topics_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(main, args + ["topics", "discover"])
    r = CliRunner().invoke(main, args + ["topics", "render", "--json"])
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert out["n_topics"] == 1
    assert (tmp_path / "_system" / "topics" / "index.md").exists()


def test_topics_apply_cli_writes_tag_to_note(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    k = tmp_path / "Knowledge"
    k.mkdir()
    (k / "a.md").write_text("---\ntitle: A\ntags: [Dev/Rust]\n---\nrust body")
    db = tmp_path / "t.db"
    args = ["--vault", str(tmp_path), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    # an active manual topic with a.md as a member
    CliRunner().invoke(
        main,
        args
        + ["topics", "add", "rust", "--label", "Rust", "--description", "rust"],
    )
    s = Store(db)
    from kb_engine.models import TopicMember

    s.set_members(
        "rust", [TopicMember(note_path="Knowledge/a.md", score=0.9, source="auto")]
    )
    s.close()
    r = CliRunner().invoke(main, args + ["topics", "apply", "--json"])
    assert r.exit_code == 0
    out = json.loads(r.output)
    assert out["status"] == "active"
    assert out["n_changed"] == 1
    import frontmatter

    fm = frontmatter.load(k / "a.md")
    assert "topic/rust" in fm["tags"]


def test_search_on_unsynced_db_returns_empty_without_crash(tmp_path, monkeypatch):
    # Searching before ever syncing must not raise sqlite "no such table: chunks";
    # the command initializes the schema first and returns zero hits cleanly.
    v = _vault(tmp_path)
    db = tmp_path / "fresh.db"  # never synced
    r = _invoke(
        ["--vault", str(v), "--db", str(db), "search", "memory", "--json"], monkeypatch
    )
    assert r.exit_code == 0
    assert r.exception is None
    assert json.loads(r.output) == {"hits": []}
