"""Tests for the doc-diagrams scripts. Run: python3 -m unittest discover -s tests -p 'test_*.py'"""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))
import palette  # noqa: E402


def load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_figure = load("check_figure", "check-figure.py")
PAPER = "#ffffff"


def svg(body: str) -> str:
    return f'<svg viewBox="0 0 960 400" xmlns="http://www.w3.org/2000/svg">\n<rect width="100%" height="100%" fill="#ffffff"/>\n{body}\n</svg>'


class MaskColors(unittest.TestCase):
    ZONE = '<rect x="40" y="40" width="600" height="300" rx="8" fill="rgba(14,40,65,0.02)" stroke="rgba(14,40,65,0.10)"/>'

    def test_paper_mask_inside_tinted_zone_is_flagged_with_the_layers_to_add(self):
        findings = check_figure.mask_findings(svg(self.ZONE + '\n<rect x="56" y="48" width="176" height="16" rx="2" fill="#ffffff"/>'), PAPER)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("rgba(14,40,65,0.02)", findings[0])
        self.assertIn("line 4", findings[0])

    def test_mask_with_the_zone_color_passes(self):
        text = svg(self.ZONE + '\n<rect x="56" y="48" width="176" height="16" rx="2" fill="#fafbfb"/>')
        self.assertEqual(check_figure.mask_findings(text, PAPER), [])

    def test_mask_layered_with_the_zone_tint_passes(self):
        mask = '<rect x="56" y="48" width="176" height="16" rx="2" fill="#ffffff"/>\n<rect x="56" y="48" width="176" height="16" rx="2" fill="rgba(14,40,65,0.02)"/>'
        self.assertEqual(check_figure.mask_findings(svg(self.ZONE + "\n" + mask), PAPER), [])

    def test_finding_suggests_the_tint_layer(self):
        findings = check_figure.mask_findings(svg(self.ZONE + '\n<rect x="56" y="48" width="176" height="16" rx="2" fill="#ffffff"/>'), PAPER)
        self.assertIn('fill="rgba(14,40,65,0.02)"', findings[0])

    def test_one_unit_of_rounding_is_allowed(self):
        text = svg(self.ZONE + '\n<rect x="56" y="48" width="176" height="16" rx="2" fill="#fafafb"/>')
        self.assertEqual(check_figure.mask_findings(text, PAPER), [])

    def test_mask_across_the_zone_border_is_not_judged(self):
        text = svg(self.ZONE + '\n<rect x="56" y="32" width="176" height="16" rx="2" fill="#ffffff"/>')
        self.assertEqual(check_figure.mask_findings(text, PAPER), [])

    def test_paper_mask_outside_zones_passes(self):
        text = svg(self.ZONE + '\n<rect x="700" y="100" width="120" height="16" rx="2" fill="#ffffff"/>')
        self.assertEqual(check_figure.mask_findings(text, PAPER), [])

    def test_zone_painted_after_the_mask_does_not_count(self):
        text = svg('<rect x="56" y="48" width="176" height="16" rx="2" fill="#ffffff"/>\n' + self.ZONE)
        self.assertEqual(check_figure.mask_findings(text, PAPER), [])

    def test_nested_tints_blend_in_paint_order(self):
        node = '<rect x="60" y="80" width="300" height="120" rx="6" fill="rgba(233,113,50,0.08)"/>'
        mask = '<rect x="80" y="90" width="100" height="16" rx="2" fill="#ffffff"/>'
        findings = check_figure.mask_findings(svg(self.ZONE + "\n" + node + "\n" + mask), PAPER)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn('fill="rgba(14,40,65,0.02)" then fill="rgba(233,113,50,0.08)"', findings[0])

    def test_rects_with_attributes_across_lines_are_read(self):
        zone = '<rect x="40" y="40"\n      width="600" height="300" fill="rgba(14,40,65,0.02)"/>'
        findings = check_figure.mask_findings(svg(zone + '\n<rect\n  x="56" y="48" width="176" height="16" fill="#ffffff"/>'), PAPER)
        self.assertEqual(len(findings), 1, findings)


class SingleQuotes(unittest.TestCase):
    def test_single_quoted_attributes_are_read(self):
        zone = "<rect x='40' y='40' width='600' height='300' fill='rgba(14,40,65,0.02)'/>"
        mask = "<rect x='56' y='48' width='176' height='16' fill='#ffffff'/>"
        self.assertEqual(len(check_figure.mask_findings(svg(zone + "\n" + mask), PAPER)), 1)


class ProfileLookup(unittest.TestCase):
    def test_profile_missing_from_home_folder_falls_back_to_the_skill_copy(self):
        original = palette.PROFILES
        with tempfile.TemporaryDirectory() as empty:
            try:
                palette.PROFILES = Path(empty) / "no-profiles-here"
                self.assertEqual(palette.profile_path("word-office"), SKILL / "profiles" / "word-office.md")
            finally:
                palette.PROFILES = original

    def test_unknown_profile_names_both_places(self):
        with self.assertRaises(SystemExit) as raised:
            palette.profile_path("no-such-profile")
        self.assertIn("no-such-profile", str(raised.exception))


def plugin_installed() -> bool:
    try:
        palette.plugin_root()
        return True
    except SystemExit:
        return False


@unittest.skipUnless(plugin_installed(), "diagram-design plugin not installed")
class Template(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / ".diagram-design").write_text("profile: word-office\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.dir)

    def copy_template(self, name: str = "figure.html") -> Path:
        text = (SKILL / "templates" / "doc-inline.html").read_text(encoding="utf-8")
        target = self.dir / name
        target.write_text(text.replace("doc-inline-", Path(name).stem + "-"), encoding="utf-8")
        return target

    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True)

    def test_doc_inline_template_passes_every_check(self):
        figure = self.copy_template()
        result = self.run_script("check-figure.py", str(figure))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 finding(s)", result.stdout)

    def test_template_uses_the_doc_inline_sizes(self):
        text = (SKILL / "templates" / "doc-inline.html").read_text(encoding="utf-8")
        self.assertRegex(text, r'viewBox="0 0 960 \d+"')
        sizes = {int(s) for s in __import__("re").findall(r'font-size="(\d+)"', text)}
        self.assertTrue(sizes, "template sets font sizes")
        self.assertTrue(sizes <= {12, 16}, f"only 12px and 16px text, found {sorted(sizes)}")

    def test_leftover_shipped_color_fails_the_check(self):
        figure = self.copy_template()
        figure.write_text(figure.read_text(encoding="utf-8").replace("</svg>", '<rect x="0" y="0" width="4" height="4" fill="#eb6c36"/></svg>'), encoding="utf-8")
        result = self.run_script("check-figure.py", str(figure))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("shipped colors still present", result.stdout)


if __name__ == "__main__":
    unittest.main()
