"""Tests for kb_engine.filing — apply_dispositions and FileResult."""

import json
import textwrap
from pathlib import Path

import frontmatter
import pytest

from kb_engine.filing import FileResult, apply_dispositions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vault(tmp_path: Path) -> Path:
    """Create a minimal vault layout: <tmp>/vault/Knowledge/inbox/."""
    vault = tmp_path / "vault"
    inbox = vault / "Knowledge" / "inbox"
    inbox.mkdir(parents=True)
    return vault


def _write_inbox_note(vault: Path, filename: str, extra_frontmatter: str = "", body: str = "Pending processing.") -> Path:
    """Write a note into <vault>/Knowledge/inbox/<filename>."""
    path = vault / "Knowledge" / "inbox" / filename
    fm_block = textwrap.dedent(f"""\
        ---
        title: Test Note
        url: https://example.com
        source: web
        date_added: "2024-01-01"
        context: some context
        author: Jane Doe
        status: inbox
        tags: []
        {extra_frontmatter.strip()}
        ---
        {body}
    """)
    path.write_text(fm_block)
    return path


def _disposition(filename: str, status: str = "reference", tags: list | None = None, summary: str = "A summary.") -> dict:
    return {
        "filename": filename,
        "status": status,
        "tags": tags if tags is not None else ["tag/one"],
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# dry-run: nothing written
# ---------------------------------------------------------------------------

def test_dry_run_writes_nothing(tmp_path):
    vault = _make_vault(tmp_path)
    src = _write_inbox_note(vault, "note.md")
    disp = [_disposition("note.md")]

    result = apply_dispositions(vault, disp, dry_run=True)

    # src still exists, dst never created — no side effects
    assert src.is_file()
    dst = vault / "Knowledge" / "note.md"
    assert not dst.exists()
    # Fix 3: dry-run now reports accurate tallies (n_filed reflects what would happen)
    assert result.n_filed == 1
    assert result.n_archived == 0


# ---------------------------------------------------------------------------
# apply reference: move + correct frontmatter + src removed
# ---------------------------------------------------------------------------

def test_apply_reference_moves_note(tmp_path):
    vault = _make_vault(tmp_path)
    src = _write_inbox_note(vault, "note.md")
    disp = [_disposition("note.md", status="reference", tags=["tag/one", "tag/two"], summary="My summary.")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert result.n_filed == 1
    assert result.n_archived == 0
    assert not src.exists(), "Source should be removed after filing"

    dst = vault / "Knowledge" / "note.md"
    assert dst.is_file()

    post = frontmatter.load(dst)
    assert post["status"] == "reference"
    assert post["tags"] == ["tag/one", "tag/two"]
    assert post["summary"] == "My summary."


def test_apply_reference_body_replaced_when_pending(tmp_path):
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md", body="Pending processing.")
    disp = [_disposition("note.md", summary="My insight.")]

    apply_dispositions(vault, disp, dry_run=False)

    dst = vault / "Knowledge" / "note.md"
    post = frontmatter.load(dst)
    assert post.content.strip() == "## Notes\n\nMy insight."


def test_apply_reference_body_replaced_when_empty(tmp_path):
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md", body="   ")
    disp = [_disposition("note.md", summary="Another insight.")]

    apply_dispositions(vault, disp, dry_run=False)

    dst = vault / "Knowledge" / "note.md"
    post = frontmatter.load(dst)
    assert post.content.strip() == "## Notes\n\nAnother insight."


def test_apply_reference_body_preserved_when_not_placeholder(tmp_path):
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md", body="Some real content I wrote.")
    disp = [_disposition("note.md", summary="Different summary.")]

    apply_dispositions(vault, disp, dry_run=False)

    dst = vault / "Knowledge" / "note.md"
    post = frontmatter.load(dst)
    assert "Some real content I wrote." in post.content
    assert "Different summary." not in post.content


# ---------------------------------------------------------------------------
# apply archived
# ---------------------------------------------------------------------------

def test_apply_archived(tmp_path):
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "old.md")
    disp = [_disposition("old.md", status="archived")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert result.n_archived == 1
    assert result.n_filed == 0

    dst = vault / "Knowledge" / "old.md"
    post = frontmatter.load(dst)
    assert post["status"] == "archived"


# ---------------------------------------------------------------------------
# other frontmatter fields preserved
# ---------------------------------------------------------------------------

def test_other_frontmatter_fields_preserved(tmp_path):
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md")
    disp = [_disposition("note.md", status="reference")]

    apply_dispositions(vault, disp, dry_run=False)

    dst = vault / "Knowledge" / "note.md"
    post = frontmatter.load(dst)
    assert post["title"] == "Test Note"
    assert post["url"] == "https://example.com"
    assert post["source"] == "web"
    assert post["date_added"] == "2024-01-01"
    assert post["context"] == "some context"
    assert post["author"] == "Jane Doe"


# ---------------------------------------------------------------------------
# collision → skipped_collision (src untouched)
# ---------------------------------------------------------------------------

def test_collision_skips_and_leaves_src(tmp_path):
    vault = _make_vault(tmp_path)
    src = _write_inbox_note(vault, "note.md")

    # Pre-create dst to cause collision
    dst = vault / "Knowledge" / "note.md"
    dst.write_text("---\ntitle: Existing\n---\noriginal content")

    disp = [_disposition("note.md")]
    result = apply_dispositions(vault, disp, dry_run=False)

    assert "note.md" in result.skipped_collision
    assert result.n_filed == 0
    # src not removed
    assert src.is_file()
    # dst not overwritten
    assert "original content" in dst.read_text()


# ---------------------------------------------------------------------------
# missing → skipped_missing
# ---------------------------------------------------------------------------

def test_missing_src_skipped(tmp_path):
    vault = _make_vault(tmp_path)
    disp = [_disposition("nonexistent.md")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert "nonexistent.md" in result.skipped_missing
    assert result.n_filed == 0


# ---------------------------------------------------------------------------
# invalid filename → skipped_invalid + nothing written outside
# ---------------------------------------------------------------------------

def test_invalid_filename_path_traversal(tmp_path):
    vault = _make_vault(tmp_path)
    disp = [_disposition("../evil.md")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert "../evil.md" in result.skipped_invalid
    evil = tmp_path / "evil.md"
    assert not evil.exists(), "Path traversal must not write outside vault"


def test_invalid_filename_subdirectory(tmp_path):
    vault = _make_vault(tmp_path)
    disp = [_disposition("sub/dir.md")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert "sub/dir.md" in result.skipped_invalid


def test_invalid_filename_absolute(tmp_path):
    vault = _make_vault(tmp_path)
    disp = [_disposition("/etc/passwd")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert "/etc/passwd" in result.skipped_invalid


def test_invalid_filename_empty(tmp_path):
    vault = _make_vault(tmp_path)
    disp = [_disposition("")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert "" in result.skipped_invalid


def test_invalid_filename_dot(tmp_path):
    vault = _make_vault(tmp_path)
    disp = [_disposition(".")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert "." in result.skipped_invalid


def test_invalid_filename_dotdot(tmp_path):
    vault = _make_vault(tmp_path)
    disp = [_disposition("..")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert ".." in result.skipped_invalid


def test_invalid_filename_backslash(tmp_path):
    vault = _make_vault(tmp_path)
    disp = [_disposition("..\\evil.md")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert "..\\evil.md" in result.skipped_invalid


# ---------------------------------------------------------------------------
# invalid status → skipped_invalid
# ---------------------------------------------------------------------------

def test_invalid_status(tmp_path):
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md")
    disp = [_disposition("note.md", status="pending")]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert "note.md" in result.skipped_invalid
    assert result.n_filed == 0


# ---------------------------------------------------------------------------
# path-traversal via resolved path cannot write outside vault
# ---------------------------------------------------------------------------

def test_path_traversal_cannot_escape_vault(tmp_path):
    """Even if filename passes basename checks but resolves outside vault, skip it."""
    vault = _make_vault(tmp_path)

    # Create a file outside the vault that a symlinked inbox could expose
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "secret.md"
    original_content = "---\ntitle: Secret\n---\nsecret"
    outside_file.write_text(original_content)

    # Replace inbox with a symlink pointing outside
    inbox = vault / "Knowledge" / "inbox"
    import shutil
    shutil.rmtree(str(inbox))
    inbox.symlink_to(outside_dir)

    disp = [_disposition("secret.md")]
    result = apply_dispositions(vault, disp, dry_run=False)

    # The key invariant: no file written outside vault/Knowledge/.
    knowledge_dir = vault / "Knowledge"
    for f in knowledge_dir.rglob("*"):
        if f.is_file():
            assert f.resolve().is_relative_to(vault.resolve()), (
                f"File {f} resolved outside vault boundary"
            )

    # The outside file must be completely untouched — byte-for-byte identical
    assert outside_file.exists(), "Outside file should still exist"
    assert outside_file.read_text() == original_content, (
        "Outside file content must be unchanged"
    )

    # Must have been rejected (either as invalid or missing — never silently filed)
    assert (
        "secret.md" in result.skipped_invalid or "secret.md" in result.skipped_missing
    ), f"secret.md must be skipped; got result={result}"


# ---------------------------------------------------------------------------
# FileResult dataclass
# ---------------------------------------------------------------------------

def test_file_result_is_frozen():
    r = FileResult(n_filed=1, n_archived=0)
    with pytest.raises((AttributeError, TypeError)):
        r.n_filed = 99  # type: ignore[misc]


def test_file_result_defaults():
    r = FileResult(n_filed=0, n_archived=0)
    assert r.skipped_missing == ()
    assert r.skipped_collision == ()
    assert r.skipped_invalid == ()


# ---------------------------------------------------------------------------
# Multiple dispositions: tallying
# ---------------------------------------------------------------------------

def test_multiple_dispositions_tallied(tmp_path):
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "ref.md")
    _write_inbox_note(vault, "arc.md")

    disp = [
        _disposition("ref.md", status="reference"),
        _disposition("arc.md", status="archived"),
        _disposition("missing.md"),
    ]

    result = apply_dispositions(vault, disp, dry_run=False)

    assert result.n_filed == 1
    assert result.n_archived == 1
    assert "missing.md" in result.skipped_missing


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

def test_cli_file_dry_run(tmp_path):
    """kb-engine file reads dispositions from --from and respects dry-run default."""
    from click.testing import CliRunner
    from kb_engine.cli import main

    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md")

    dispositions = [_disposition("note.md")]
    disp_file = tmp_path / "disp.json"
    disp_file.write_text(json.dumps(dispositions))

    db = tmp_path / "t.db"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--vault", str(vault), "--db", str(db), "file", "--from", str(disp_file)],
    )

    assert result.exit_code == 0, result.output
    # dry-run: source still exists
    assert (vault / "Knowledge" / "inbox" / "note.md").is_file()


def test_cli_file_apply_json(tmp_path):
    """kb-engine file --apply --json returns correct JSON payload."""
    from click.testing import CliRunner
    from kb_engine.cli import main

    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md")

    dispositions = [_disposition("note.md")]
    disp_file = tmp_path / "disp.json"
    disp_file.write_text(json.dumps(dispositions))

    db = tmp_path / "t.db"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--vault", str(vault), "--db", str(db), "file", "--from", str(disp_file), "--apply", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["filed"] == 1
    assert payload["archived"] == 0
    assert payload["dry_run"] is False
    assert "skipped_missing" in payload
    assert "skipped_collision" in payload
    assert "skipped_invalid" in payload


# ---------------------------------------------------------------------------
# Fix 1: non-dict disposition item → skipped_invalid, no crash, valid items processed
# ---------------------------------------------------------------------------

def test_non_dict_disposition_item_skipped(tmp_path):
    """A non-dict item must go to skipped_invalid with no exception, valid items still processed."""
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "good.md")

    dispositions = [
        "not_a_dict",          # non-dict
        _disposition("good.md"),
    ]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert result.n_filed == 1, "valid item after bad one should be filed"
    assert len(result.skipped_invalid) == 1


def test_non_dict_disposition_various_types(tmp_path):
    """Non-dict items of various types (None, int, list) all go to skipped_invalid."""
    vault = _make_vault(tmp_path)

    dispositions = [None, 42, ["a", "b"]]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert len(result.skipped_invalid) == 3
    assert result.n_filed == 0


# ---------------------------------------------------------------------------
# Fix 1: non-string filename → skipped_invalid, no crash
# ---------------------------------------------------------------------------

def test_non_string_filename_skipped(tmp_path):
    """A numeric filename must go to skipped_invalid without crashing."""
    vault = _make_vault(tmp_path)

    dispositions = [{"filename": 123, "status": "reference", "tags": [], "summary": "x"}]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert len(result.skipped_invalid) == 1
    assert result.n_filed == 0


# ---------------------------------------------------------------------------
# Fix 2: non-list tags → skipped_invalid (not silently corrupted)
# ---------------------------------------------------------------------------

def test_non_list_tags_skipped(tmp_path):
    """tags='oops' must not become ['o','o','p','s'] — item goes to skipped_invalid."""
    vault = _make_vault(tmp_path)
    src = _write_inbox_note(vault, "note.md")

    dispositions = [{"filename": "note.md", "status": "reference", "tags": "oops", "summary": "s"}]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert "note.md" in result.skipped_invalid
    assert result.n_filed == 0
    # Source must be untouched
    assert src.is_file()
    # Destination must NOT have been written
    dst = vault / "Knowledge" / "note.md"
    assert not dst.exists()


# ---------------------------------------------------------------------------
# Fix 2: non-string summary → skipped_invalid
# ---------------------------------------------------------------------------

def test_non_string_summary_skipped(tmp_path):
    """summary=5 must go to skipped_invalid."""
    vault = _make_vault(tmp_path)
    src = _write_inbox_note(vault, "note.md")

    dispositions = [{"filename": "note.md", "status": "reference", "tags": [], "summary": 5}]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert "note.md" in result.skipped_invalid
    assert result.n_filed == 0
    assert src.is_file()


# ---------------------------------------------------------------------------
# Unicode filename + YAML-special summary survives round-trip
# ---------------------------------------------------------------------------

def test_unicode_filename_and_yaml_special_summary(tmp_path):
    """Unicode filename and YAML-special chars in summary survive frontmatter round-trip."""
    vault = _make_vault(tmp_path)
    fname = "Café — Gödel's \"theorem\".md"
    _write_inbox_note(vault, fname)

    summary = 'weird: " # , chars'
    tags = ["tag/one", "tag/two"]
    dispositions = [{"filename": fname, "status": "reference", "tags": tags, "summary": summary}]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert result.n_filed == 1, f"expected 1 filed, got {result}"

    dst = vault / "Knowledge" / fname
    assert dst.is_file()

    post = frontmatter.load(dst)
    assert post["tags"] == tags
    assert post["summary"] == summary
    assert post["status"] == "reference"
    assert summary in post.content


# ---------------------------------------------------------------------------
# Fix 4: symlink AT the destination → skipped_invalid, symlink target untouched
# ---------------------------------------------------------------------------

def test_symlink_at_destination_skipped(tmp_path):
    """If dst is a symlink (even dangling), skip and do not write through it."""
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md")

    # Create a real target file and put a symlink at the destination
    target = tmp_path / "target.md"
    target.write_text("original target content")
    dst = vault / "Knowledge" / "note.md"
    dst.symlink_to(target)

    dispositions = [_disposition("note.md")]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert "note.md" in result.skipped_invalid
    assert result.n_filed == 0
    # The symlink target must be completely untouched
    assert target.read_text() == "original target content"


def test_dangling_symlink_at_destination_skipped(tmp_path):
    """A dangling symlink at dst pointing outside the vault → skipped_invalid, outside file not created."""
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md")

    outside_target = tmp_path / "outside_target.md"
    # Don't create outside_target — dangling symlink
    dst = vault / "Knowledge" / "note.md"
    dst.symlink_to(outside_target)

    dispositions = [_disposition("note.md")]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert "note.md" in result.skipped_invalid
    assert result.n_filed == 0
    # The outside target was NOT created
    assert not outside_target.exists()


# ---------------------------------------------------------------------------
# Duplicate filename within one batch → first filed, second skipped_missing
# ---------------------------------------------------------------------------

def test_duplicate_filename_in_batch(tmp_path):
    """Filing the same filename twice: second disposition hits skipped_missing (src gone)."""
    vault = _make_vault(tmp_path)
    _write_inbox_note(vault, "note.md")

    dispositions = [_disposition("note.md"), _disposition("note.md")]
    result = apply_dispositions(vault, dispositions, dry_run=False)

    assert result.n_filed == 1
    assert "note.md" in result.skipped_missing


# ---------------------------------------------------------------------------
# Fix 3: dry-run returns accurate n_filed / n_archived tallies
# ---------------------------------------------------------------------------

def test_dry_run_accurate_tally(tmp_path):
    """dry-run must report non-zero n_filed/n_archived without actually moving files."""
    vault = _make_vault(tmp_path)
    src_ref = _write_inbox_note(vault, "ref.md")
    src_arc = _write_inbox_note(vault, "arc.md")

    dispositions = [
        _disposition("ref.md", status="reference"),
        _disposition("arc.md", status="archived"),
    ]
    result = apply_dispositions(vault, dispositions, dry_run=True)

    # Tallies must reflect what would have happened
    assert result.n_filed == 1, f"dry-run n_filed should be 1, got {result.n_filed}"
    assert result.n_archived == 1, f"dry-run n_archived should be 1, got {result.n_archived}"

    # No files were actually moved
    assert src_ref.is_file(), "src_ref must still be in inbox"
    assert src_arc.is_file(), "src_arc must still be in inbox"
    dst_ref = vault / "Knowledge" / "ref.md"
    dst_arc = vault / "Knowledge" / "arc.md"
    assert not dst_ref.exists(), "dst_ref must not exist after dry-run"
    assert not dst_arc.exists(), "dst_arc must not exist after dry-run"


# ---------------------------------------------------------------------------
# Strengthen: path_traversal_cannot_escape_vault (already replaced above)
# covered by the updated test_path_traversal_cannot_escape_vault above
# ---------------------------------------------------------------------------
