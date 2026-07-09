import json

import numpy as np
import pytest
from click.testing import CliRunner

from kb_engine.cli import main
from kb_engine.models import QueueEntry, Topic, TopicMember
from kb_engine.store import Store


def _seed_topic(store, slug, n_members):
    topic = Topic(
        slug=slug,
        label=slug.upper(),
        keywords=(slug,),
        centroid=np.ones(4, np.float32),
        kind="discovered",
        status="proposed",
    )
    store.save_topics(
        [topic],
        {slug: [TopicMember(f"Knowledge/{slug}-{i}.md", 0.9, "auto") for i in range(n_members)]},
    )


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


def test_topics_areas_cli(tmp_path, monkeypatch):
    pytest.importorskip("sklearn")  # build_areas uses AgglomerativeClustering — [topics] extra
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
    # Phase 3 contract: emitted paths are vault-relative, not absolute.
    assert out["index_path"] == "_system/topics/index.md"
    assert out["taxonomy_path"] == "_system/_taxonomy.md"


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


# --- import-things -----------------------------------------------------------

import sqlite3  # noqa: E402


def _things_db(tmp_path):
    db = tmp_path / "main.sqlite"
    c = sqlite3.connect(db)
    c.executescript(
        """
      CREATE TABLE TMArea(uuid TEXT, title TEXT);
      CREATE TABLE TMTask(type INT, status INT, trashed INT, title TEXT,
                          notes TEXT, area TEXT, project TEXT, uuid TEXT);
      INSERT INTO TMArea VALUES('A1','Reading');
      INSERT INTO TMTask VALUES(0,0,0,'Cool article','see https://e.com/p','A1',NULL,'t1');
      INSERT INTO TMTask VALUES(0,0,0,'https://github.com/a/b',NULL,NULL,NULL,'t2');
      INSERT INTO TMTask VALUES(0,3,0,'done','https://done.com',NULL,NULL,'t3');
    """
    )
    c.commit()
    c.close()
    return db


def _import_vault(tmp_path):
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    return tmp_path


def test_import_things_dry_run_reports_and_writes_nothing(tmp_path):
    things = _things_db(tmp_path)
    v = _import_vault(tmp_path / "vault")
    r = CliRunner().invoke(
        main,
        [
            "--vault", str(v),
            "import-things", "--things-db", str(things),
            "--status", "open", "--dry-run", "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["dry_run"] is True
    assert out["n_tasks"] == 2
    assert out["n_urls"] == 2
    assert out["would_write"] == 2
    assert out["would_skip_existing"] == 0
    assert out["would_skip_dup_in_batch"] == 0
    assert "sample" in out
    # nothing written
    import glob

    assert glob.glob(str(v / "Knowledge" / "inbox" / "*.md")) == []


def test_import_things_dry_run_counts_in_batch_dups(tmp_path):
    # Two open tasks carry the SAME url; dry-run must predict one write and one
    # in-batch dup skip, matching the real run's skipped_dup_in_batch.
    db = tmp_path / "main.sqlite"
    c = sqlite3.connect(db)
    c.executescript(
        """
      CREATE TABLE TMArea(uuid TEXT, title TEXT);
      CREATE TABLE TMTask(type INT, status INT, trashed INT, title TEXT,
                          notes TEXT, area TEXT, project TEXT, uuid TEXT);
      INSERT INTO TMTask VALUES(0,0,0,'First','https://dup.com/x',NULL,NULL,'t1');
      INSERT INTO TMTask VALUES(0,0,0,'Second','https://dup.com/x',NULL,NULL,'t2');
    """
    )
    c.commit()
    c.close()
    v = _import_vault(tmp_path / "vault")
    r = CliRunner().invoke(
        main,
        [
            "--vault", str(v),
            "import-things", "--things-db", str(db),
            "--dry-run", "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["n_urls"] == 2
    assert out["would_write"] == 1
    assert out["would_skip_dup_in_batch"] == 1
    assert out["would_skip_existing"] == 0


def test_import_things_real_run_writes_stubs(tmp_path):
    things = _things_db(tmp_path)
    v = _import_vault(tmp_path / "vault")
    r = CliRunner().invoke(
        main,
        [
            "--vault", str(v),
            "import-things", "--things-db", str(things),
            "--date", "2026-06-16", "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["written"] == 2
    assert out["skipped_existing"] == 0
    assert out["skipped_dup_in_batch"] == 0
    import glob

    import frontmatter

    stubs = glob.glob(str(v / "Knowledge" / "inbox" / "*.md"))
    assert len(stubs) == 2
    fm = frontmatter.load(stubs[0])
    assert fm["date_added"] == "2026-06-16"
    assert fm["status"] == "inbox"


def test_import_things_dedups_against_existing_vault_url(tmp_path):
    things = _things_db(tmp_path)
    v = _import_vault(tmp_path / "vault")
    # one of the Things URLs already exists in the vault
    (v / "Knowledge" / "have.md").write_text(
        "---\ntitle: Have\nurl: https://e.com/p\n---\nbody"
    )
    r = CliRunner().invoke(
        main,
        ["--vault", str(v), "import-things", "--things-db", str(things), "--json"],
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["written"] == 1
    assert out["skipped_existing"] == 1


def test_import_things_area_filter(tmp_path):
    things = _things_db(tmp_path)
    v = _import_vault(tmp_path / "vault")
    r = CliRunner().invoke(
        main,
        [
            "--vault", str(v),
            "import-things", "--things-db", str(things),
            "--area", "Reading", "--dry-run", "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["n_tasks"] == 1
    assert out["n_urls"] == 1


def test_import_things_exclude_area_reduces_count(tmp_path):
    # --exclude-area drops the 'Reading' task (https://e.com/p), leaving fewer
    # tasks/urls than an unfiltered dry-run.
    things = _things_db(tmp_path)
    v = _import_vault(tmp_path / "vault")
    base = CliRunner().invoke(
        main,
        [
            "--vault", str(v),
            "import-things", "--things-db", str(things),
            "--status", "open", "--dry-run", "--json",
        ],
    )
    assert base.exit_code == 0, base.output
    base_out = json.loads(base.output)

    excluded = CliRunner().invoke(
        main,
        [
            "--vault", str(v),
            "import-things", "--things-db", str(things),
            "--status", "open", "--exclude-area", "Reading",
            "--dry-run", "--json",
        ],
    )
    assert excluded.exit_code == 0, excluded.output
    excl_out = json.loads(excluded.output)

    assert excl_out["n_tasks"] < base_out["n_tasks"]
    assert excl_out["n_urls"] < base_out["n_urls"]
    assert excl_out["n_tasks"] == base_out["n_tasks"] - 1


def test_import_things_exclude_project_reduces_count(tmp_path):
    # A URL task under a 'Junk' project is dropped by --exclude-project.
    db = tmp_path / "main.sqlite"
    c = sqlite3.connect(db)
    c.executescript(
        """
      CREATE TABLE TMArea(uuid TEXT, title TEXT);
      CREATE TABLE TMTask(type INT, status INT, trashed INT, title TEXT,
                          notes TEXT, area TEXT, project TEXT, uuid TEXT);
      INSERT INTO TMTask VALUES(1,0,0,'Junk',NULL,NULL,NULL,'pj');
      INSERT INTO TMTask VALUES(0,0,0,'keep','https://keep.com/x',NULL,NULL,'t1');
      INSERT INTO TMTask VALUES(0,0,0,'drop','https://drop.com/x',NULL,'pj','t2');
    """
    )
    c.commit()
    c.close()
    v = _import_vault(tmp_path / "vault")
    r = CliRunner().invoke(
        main,
        [
            "--vault", str(v),
            "import-things", "--things-db", str(db),
            "--exclude-project", "Junk", "--dry-run", "--json",
        ],
    )
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert out["n_tasks"] == 1
    assert out["sample"][0]["url"] == "https://keep.com/x"


def test_default_things_db_prefers_live_over_backups(tmp_path, monkeypatch):
    # The standard glob also matches Backups/*.thingsdatabase/main.sqlite; the
    # default must pick the LIVE database, never a dated backup. (Phase-3b's
    # scheduled job relies on this default resolving correctly.)
    from kb_engine import cli

    base = tmp_path / "Library" / "Group Containers" / "X.ThingsMac" / "ThingsData-AB"
    live = base / "Things Database.thingsdatabase" / "main.sqlite"
    backup = base / "Backups" / "Things Database Backup 2026-06-07.thingsdatabase" / "main.sqlite"
    for p in (live, backup):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("")
    monkeypatch.setattr(cli.Path, "home", staticmethod(lambda: tmp_path))
    resolved = cli._default_things_db()
    assert resolved == live
    assert "Backups" not in str(resolved)


def test_default_things_db_falls_back_to_backup_if_only_option(tmp_path, monkeypatch):
    # If somehow only a backup exists, still return something rather than None.
    from kb_engine import cli

    base = tmp_path / "Library" / "Group Containers" / "X.ThingsMac" / "ThingsData-AB"
    backup = base / "Backups" / "Things Database Backup 2026-06-07.thingsdatabase" / "main.sqlite"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text("")
    monkeypatch.setattr(cli.Path, "home", staticmethod(lambda: tmp_path))
    assert cli._default_things_db() == backup


def test_default_things_db_none_when_absent(tmp_path, monkeypatch):
    from kb_engine import cli

    monkeypatch.setattr(cli.Path, "home", staticmethod(lambda: tmp_path))
    assert cli._default_things_db() is None


def test_import_things_missing_db_errors_clearly(tmp_path):
    v = _import_vault(tmp_path / "vault")
    r = CliRunner().invoke(
        main,
        [
            "--vault", str(v),
            "import-things", "--things-db", str(tmp_path / "nope.sqlite"),
            "--json",
        ],
    )
    assert r.exit_code != 0
    assert "not found" in r.output.lower() or "nope.sqlite" in r.output


def test_import_things_human_output(tmp_path):
    things = _things_db(tmp_path)
    v = _import_vault(tmp_path / "vault")
    r = CliRunner().invoke(
        main,
        ["--vault", str(v), "import-things", "--things-db", str(things), "--dry-run"],
    )
    assert r.exit_code == 0, r.output
    assert "would write" in r.output.lower() or "would_write" in r.output.lower()


# --- digest ------------------------------------------------------------------


def test_digest_cli_writes_system_file_and_reports_json(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    monkeypatch.setenv("KB_FAKE_CLUSTER", "0,0,-1")
    v = _topics_vault(tmp_path)
    # add an inbox stub so the backlog count is non-zero
    (v / "Knowledge" / "inbox").mkdir(parents=True)
    (v / "Knowledge" / "inbox" / "x.md").write_text(
        "---\ntitle: X\nurl: https://e.com/x\nstatus: inbox\n---\n## Notes"
    )
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(main, args + ["topics", "discover"])
    r = CliRunner().invoke(main, args + ["digest", "--json"])
    assert r.exit_code == 0, r.output
    out = json.loads(r.output)
    assert {"inbox", "proposals", "topics", "areas", "unfiled", "digest_path"} <= out.keys()
    assert out["inbox"] == 1
    assert out["digest_path"] == "_system/kb-digest.md"
    digest_file = v / "_system" / "kb-digest.md"
    assert digest_file.exists()
    assert "Inbox" in digest_file.read_text()


def test_digest_cli_idempotent_file(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    CliRunner().invoke(main, args + ["digest"])
    first = (v / "_system" / "kb-digest.md").read_text()
    CliRunner().invoke(main, args + ["digest"])
    second = (v / "_system" / "kb-digest.md").read_text()
    assert first == second


def test_digest_cli_human_output(tmp_path, monkeypatch):
    monkeypatch.setenv("KB_FAKE_EMBED", "1")
    v = _vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    CliRunner().invoke(main, args + ["sync"])
    r = CliRunner().invoke(main, args + ["digest"])
    assert r.exit_code == 0, r.output
    assert "inbox" in r.output.lower()


def test_synthesis_candidates_cli_json(tmp_path):
    (tmp_path / "Knowledge" / "wiki").mkdir(parents=True)
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    _seed_topic(store, "rag", 6)
    store.close()
    r = CliRunner().invoke(
        main, ["--vault", str(tmp_path), "--db", str(db), "synthesis-candidates", "--json"]
    )
    assert r.exit_code == 0, r.output
    cands = json.loads(r.output)["candidates"]
    assert [c["slug"] for c in cands] == ["rag"]
    assert cands[0]["size"] == 6


def test_synthesis_candidates_cli_human_empty(tmp_path):
    # No topics seeded -> human output reports nothing.
    (tmp_path / "Knowledge" / "wiki").mkdir(parents=True)
    db = tmp_path / "t.db"
    r = CliRunner().invoke(
        main, ["--vault", str(tmp_path), "--db", str(db), "synthesis-candidates"]
    )
    assert r.exit_code == 0, r.output
    assert "no synthesis candidates" in r.output.lower()


def _related_vault(tmp_path):
    k = tmp_path / "Knowledge"
    k.mkdir()
    (k / "mem.md").write_text("---\ntitle: Memory\n---\nlong term memory for agents")
    (k / "rust.md").write_text("---\ntitle: Rust\n---\nrust macros and traits")
    return tmp_path


def test_related_query_cli_json(tmp_path, monkeypatch):
    v = _related_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    _invoke(args + ["sync"], monkeypatch)
    r = _invoke(args + ["related", "--query", "memory for agents", "--json"], monkeypatch)
    assert r.exit_code == 0, r.output
    hits = json.loads(r.output)["hits"]
    assert hits and hits[0]["note_path"] == "Knowledge/mem.md"
    assert hits[0]["title"] == "Memory"


def test_related_to_note_cli_json(tmp_path, monkeypatch):
    v = _related_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    _invoke(args + ["sync"], monkeypatch)
    r = _invoke(args + ["related", "--to", "Knowledge/mem.md", "--json"], monkeypatch)
    assert r.exit_code == 0, r.output
    hits = json.loads(r.output)["hits"]
    assert "Knowledge/mem.md" not in [h["note_path"] for h in hits]  # excludes self


def test_related_requires_exactly_one_of_query_or_to(tmp_path, monkeypatch):
    v = _related_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    # Neither provided -> usage error.
    r_none = _invoke(args + ["related"], monkeypatch)
    assert r_none.exit_code != 0
    assert "exactly one" in r_none.output.lower()
    # Both provided -> usage error.
    r_both = _invoke(
        args + ["related", "--query", "x", "--to", "Knowledge/mem.md"], monkeypatch
    )
    assert r_both.exit_code != 0
    assert "exactly one" in r_both.output.lower()


def test_related_empty_query_with_to_does_not_silently_run_to(tmp_path, monkeypatch):
    # --query "" --to X must NOT fall through to the --to branch: an empty string
    # was provided for --query, so exactly-one-of is satisfied and the empty
    # query is rejected on its own merit.
    v = _related_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    _invoke(args + ["sync"], monkeypatch)
    r = _invoke(
        args + ["related", "--query", "", "--to", "Knowledge/mem.md"], monkeypatch
    )
    assert r.exit_code != 0
    assert "exactly one" in r.output.lower()


def test_related_whitespace_query_is_rejected(tmp_path, monkeypatch):
    v = _related_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    _invoke(args + ["sync"], monkeypatch)
    r = _invoke(args + ["related", "--query", "  "], monkeypatch)
    assert r.exit_code != 0
    assert "must not be empty" in r.output.lower()


def test_related_to_ghost_note_returns_empty(tmp_path, monkeypatch):
    # --to a note that was never synced: exits 0 with no hits (the CLI empty path).
    v = _related_vault(tmp_path)
    db = tmp_path / "t.db"
    args = ["--vault", str(v), "--db", str(db)]
    _invoke(args + ["sync"], monkeypatch)
    r = _invoke(args + ["related", "--to", "Knowledge/ghost.md", "--json"], monkeypatch)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output) == {"hits": []}


# --- dedup-report ------------------------------------------------------------


def test_dedup_report_json(tmp_path, monkeypatch, real_vectors):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    for path, vec in real_vectors.by_group("neardup:0"):
        p = f"Knowledge/{path.split('/')[-1]}"
        store.upsert_note(p, p, f"sha-{p}", [])
        store.replace_chunks(p, [(0, p, vec)])
    store.close()
    r = _invoke(
        ["--vault", str(tmp_path), "--db", str(db), "dedup-report", "--json"],
        monkeypatch,
    )
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload["threshold"] == 0.95
    assert len(payload["pairs"]) == 1
    assert payload["pairs"][0]["cosine"] > 0.97


# --- topics reanchor ---------------------------------------------------------


def test_topics_reanchor_json(tmp_path, monkeypatch, real_vectors):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("warm", "Warm", "d", np.ones(1024, np.float32))
    rows = []
    for path, vec in real_vectors.by_group("topic:")[:3]:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
        rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
    store.set_members("warm", rows)
    store.close()
    r = _invoke(
        ["--vault", str(tmp_path), "--db", str(db), "topics", "reanchor", "--json"],
        monkeypatch,
    )
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload["reanchored"] == ["warm"]


def test_topics_thresholds_dry_run_does_not_persist(tmp_path, monkeypatch, real_vectors):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(1024, np.float32))
    rows = []
    for path, vec in real_vectors.by_group("topic:")[:3]:
        store.upsert_note(path, path, f"sha-{path}", [])
        store.replace_chunks(path, [(0, path, vec)])
        rows.append(TopicMember(note_path=path, score=0.8, source="auto"))
    store.set_members("t1", rows)
    store.close()

    r = _invoke(["--vault", str(tmp_path), "--db", str(db),
                 "topics", "thresholds", "--dry-run", "--json"], monkeypatch)
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload["persisted"] is False
    assert payload["topics"][0]["slug"] == "t1"
    store = Store(db)
    store.init_schema()
    assert store.load_topics()[0].threshold_high is None
    store.close()

    r2 = _invoke(["--vault", str(tmp_path), "--db", str(db),
                  "topics", "thresholds", "--json"], monkeypatch)
    assert json.loads(r2.output)["persisted"] is True
    store = Store(db)
    store.init_schema()
    assert store.load_topics()[0].threshold_high is not None
    store.close()


def test_topics_confirm_from_queue(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(4, np.float32))
    store.upsert_note("Knowledge/n.md", "N", "sha-n", [])
    store.replace_review_queue(
        [QueueEntry("Knowledge/n.md", (("t1", 0.52),), "borderline")]
    )
    store.close()
    r = _invoke(["--vault", str(tmp_path), "--db", str(db),
                 "topics", "confirm", "t1", "Knowledge/n.md", "--json"], monkeypatch)
    assert r.exit_code == 0
    payload = json.loads(r.output)
    assert payload == {
        "slug": "t1", "note": "Knowledge/n.md",
        "score": 0.52, "source": "user", "dequeued": True,
    }
    store = Store(db)
    store.init_schema()
    members = store.topic_members("t1")
    assert [(m.note_path, m.source, m.is_primary) for m in members] == [
        ("Knowledge/n.md", "user", True)
    ]
    assert store.load_review_queue() == []
    store.close()


def test_topics_confirm_unknown_slug_fails(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.upsert_note("Knowledge/n.md", "N", "sha-n", [])
    store.close()
    r = _invoke(["--vault", str(tmp_path), "--db", str(db),
                 "topics", "confirm", "nope", "Knowledge/n.md"], monkeypatch)
    assert r.exit_code != 0
    assert "no such topic" in r.output


def test_topics_confirm_unknown_note_fails(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    store = Store(db)
    store.init_schema()
    store.add_manual_topic("t1", "T1", "d", np.ones(4, np.float32))
    store.close()
    r = _invoke(["--vault", str(tmp_path), "--db", str(db),
                 "topics", "confirm", "t1", "Knowledge/ghost.md"], monkeypatch)
    assert r.exit_code != 0
    assert "not in the index" in r.output
