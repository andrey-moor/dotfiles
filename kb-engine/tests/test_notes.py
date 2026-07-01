from pathlib import Path

from kb_engine.importing.notes import slug_for, next_free_path


def test_slug_for_prefers_title():
    assert slug_for("Rust Macros", "https://example.com/x") == "rust-macros"


def test_slug_for_falls_back_to_url_path_when_title_is_a_url():
    assert slug_for("https://example.com/cool-post", "https://example.com/cool-post") == "cool-post"


def test_next_free_path_disambiguates(tmp_path):
    taken: set[str] = set()
    p1 = next_free_path(tmp_path, "a", taken)
    p1.write_text("x")
    p2 = next_free_path(tmp_path, "a", taken)
    assert p1.name == "a.md" and p2.name == "a-2.md"
