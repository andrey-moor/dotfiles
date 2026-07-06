from kb_engine.store import Store


def test_store_indexes_url_and_message_id(tmp_path):
    s = Store(tmp_path / "kb.db"); s.init_schema()
    s.upsert_note(path="Knowledge/a.md", title="A", sha256="h1", tags=[], summary="",
                  url="https://example.com/x/", message_id="m1@host")
    s.upsert_note(path="Knowledge/b.md", title="B", sha256="h2", tags=[], summary="")  # no url/msgid
    assert s.existing_urls() == {"https://example.com/x"}     # normalized (trailing slash dropped)
    assert s.existing_message_ids() == {"m1@host"}
    s.close()


def test_init_schema_is_idempotent_on_existing_db(tmp_path):
    db = tmp_path / "kb.db"
    Store(db).init_schema()          # v1
    s = Store(db); s.init_schema()   # re-run migration must not crash
    s.upsert_note(path="Knowledge/c.md", title="C", sha256="h", tags=[], summary="", url="https://e.com/z")
    assert s.existing_urls() == {"https://e.com/z"}
    s.close()
