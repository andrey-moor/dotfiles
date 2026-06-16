import sqlite3

import pytest

from kb_engine.importing.things import ThingsTask, read_things_tasks


def _fixture_things(tmp_path):
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
      INSERT INTO TMTask VALUES(0,3,0,'done link','https://done.com',NULL,NULL,'t3');
      INSERT INTO TMTask VALUES(0,0,1,'trashed','https://t.com',NULL,NULL,'t4');
      INSERT INTO TMTask VALUES(0,0,0,'no url task','just text',NULL,NULL,'t5');
      INSERT INTO TMTask VALUES(1,0,0,'a project','https://proj.com',NULL,NULL,'p1');
    """
    )
    c.commit()
    c.close()
    return db


def test_read_things_open_url_tasks(tmp_path):
    tasks = read_things_tasks(_fixture_things(tmp_path), status="open")
    urls = sorted(u for t in tasks for u in t.urls)
    assert urls == ["https://e.com/p", "https://github.com/a/b"]
    assert any(t.area == "Reading" for t in tasks)


def test_read_things_area_filter(tmp_path):
    tasks = read_things_tasks(
        _fixture_things(tmp_path), status="open", areas=["Reading"]
    )
    assert all(t.area == "Reading" for t in tasks) and len(tasks) == 1


def test_read_things_completed_status(tmp_path):
    tasks = read_things_tasks(_fixture_things(tmp_path), status="completed")
    urls = sorted(u for t in tasks for u in t.urls)
    assert urls == ["https://done.com"]


def test_read_things_all_status_excludes_trashed_and_projects(tmp_path):
    # status=all drops the status filter but type=0 AND trashed=0 still hold,
    # and only url-bearing tasks survive.
    tasks = read_things_tasks(_fixture_things(tmp_path), status="all")
    urls = sorted(u for t in tasks for u in t.urls)
    assert urls == ["https://done.com", "https://e.com/p", "https://github.com/a/b"]


def test_read_things_returns_frozen_tasks(tmp_path):
    tasks = read_things_tasks(_fixture_things(tmp_path), status="open")
    assert all(isinstance(t, ThingsTask) for t in tasks)
    with pytest.raises(AttributeError):
        tasks[0].title = "x"  # type: ignore[misc]


def test_read_things_resolves_project_title(tmp_path):
    db = tmp_path / "main.sqlite"
    c = sqlite3.connect(db)
    c.executescript(
        """
      CREATE TABLE TMArea(uuid TEXT, title TEXT);
      CREATE TABLE TMTask(type INT, status INT, trashed INT, title TEXT,
                          notes TEXT, area TEXT, project TEXT, uuid TEXT);
      INSERT INTO TMTask VALUES(1,0,0,'My Project',NULL,NULL,NULL,'proj-1');
      INSERT INTO TMTask VALUES(0,0,0,'task','https://e.com/x',NULL,'proj-1','t-1');
    """
    )
    c.commit()
    c.close()
    tasks = read_things_tasks(db, status="open")
    assert len(tasks) == 1 and tasks[0].project == "My Project"
    # project name filter narrows to that project
    assert read_things_tasks(db, status="open", projects=["My Project"])
    assert read_things_tasks(db, status="open", projects=["Other"]) == []


def test_read_things_missing_db_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_things_tasks(tmp_path / "nope.sqlite", status="open")


def test_read_things_does_not_mutate_or_lock_source(tmp_path):
    # The source DB is copied read-only; the original is never modified and the
    # reader must work even with a concurrent writer connection held open.
    db = _fixture_things(tmp_path)
    before = db.read_bytes()
    holder = sqlite3.connect(db)  # simulate Things holding the DB open
    try:
        tasks = read_things_tasks(db, status="open")
    finally:
        holder.close()
    assert tasks
    assert db.read_bytes() == before
    # no stray temp files left in the source directory
    assert sorted(p.name for p in tmp_path.iterdir()) == ["main.sqlite"]
