import glob

import frontmatter

from kb_engine.importing.inbox import ImportResult, existing_urls, import_urls


def test_existing_urls_scans_vault(tmp_path):
    k = tmp_path / "Knowledge"
    (k / "inbox").mkdir(parents=True)
    (k / "a.md").write_text("---\ntitle: A\nurl: https://e.com/p\n---\nbody")
    assert "https://e.com/p" in existing_urls(tmp_path)


def test_existing_urls_normalizes(tmp_path):
    # A stored URL with tracking + trailing slash is matched in normalized form.
    k = tmp_path / "Knowledge"
    k.mkdir(parents=True)
    (k / "a.md").write_text(
        "---\ntitle: A\nurl: https://e.com/p/?utm_source=x\n---\nbody"
    )
    assert existing_urls(tmp_path) == {"https://e.com/p"}


def test_existing_urls_empty_when_no_vault(tmp_path):
    assert existing_urls(tmp_path) == set()


def test_import_urls_writes_stubs_and_dedups(tmp_path):
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    (tmp_path / "Knowledge" / "a.md").write_text(
        "---\ntitle: A\nurl: https://dup.com/x\n---\nb"
    )
    items = [
        ("https://new.com/p", "New Title"),
        ("https://dup.com/x", "Dup"),
        ("https://new.com/p", "New again"),
    ]
    res = import_urls(tmp_path, items)
    assert isinstance(res, ImportResult)
    assert res.written == 1
    assert res.skipped_existing == 1
    assert res.skipped_dup_in_batch == 1
    stub = glob.glob(str(tmp_path / "Knowledge" / "inbox" / "*.md"))[0]
    fm = frontmatter.load(stub)
    assert fm["url"] == "https://new.com/p"
    assert fm["status"] == "inbox"
    assert fm["source"] == "article"
    assert fm["context"] == "Imported from Things"
    assert fm["summary"] == ""
    assert fm["tags"] == []
    assert "Pending processing." in fm.content


def test_import_urls_stamps_date_when_provided(tmp_path):
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    res = import_urls(
        tmp_path, [("https://e.com/p", "P")], date_added="2026-06-16"
    )
    assert res.written == 1
    stub = glob.glob(str(tmp_path / "Knowledge" / "inbox" / "*.md"))[0]
    assert frontmatter.load(stub)["date_added"] == "2026-06-16"


def test_import_urls_default_date_is_empty(tmp_path):
    # The engine core never calls now(); without a date it leaves it blank.
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    import_urls(tmp_path, [("https://e.com/p", "P")])
    stub = glob.glob(str(tmp_path / "Knowledge" / "inbox" / "*.md"))[0]
    assert frontmatter.load(stub)["date_added"] == ""


def test_import_urls_dedupes_filenames_with_suffix(tmp_path):
    # Two distinct URLs whose titles slugify identically get -2, -3 filenames.
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    items = [
        ("https://e.com/a", "Same Title"),
        ("https://e.com/b", "Same Title"),
    ]
    res = import_urls(tmp_path, items)
    assert res.written == 2
    names = sorted(
        p.split("/")[-1]
        for p in glob.glob(str(tmp_path / "Knowledge" / "inbox" / "*.md"))
    )
    assert names == ["same-title-2.md", "same-title.md"]


def test_import_urls_slug_falls_back_to_url_path(tmp_path):
    # When the title is itself the URL, the slug comes from the URL path.
    (tmp_path / "Knowledge" / "inbox").mkdir(parents=True)
    res = import_urls(
        tmp_path, [("https://github.com/a/b", "https://github.com/a/b")]
    )
    assert res.written == 1
    name = glob.glob(str(tmp_path / "Knowledge" / "inbox" / "*.md"))[0].split("/")[-1]
    assert name and name.endswith(".md") and "http" not in name


def test_import_urls_creates_inbox_dir_if_missing(tmp_path):
    # No Knowledge/inbox yet — import_urls creates it.
    res = import_urls(tmp_path, [("https://e.com/p", "P")])
    assert res.written == 1
    assert (tmp_path / "Knowledge" / "inbox").is_dir()
