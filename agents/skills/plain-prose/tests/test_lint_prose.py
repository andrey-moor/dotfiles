"""Tests for lint-prose.py. Run: python3 -m unittest discover -s tests -p 'test_*.py'"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "lint-prose.py"
LONG_SENTENCE = "The export job reads every new item from each source and writes one file per item into the export folder before it records where the run stopped today."


class LintCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def lint(self, text: str, *args: str, name: str = "doc.md") -> subprocess.CompletedProcess:
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return subprocess.run([sys.executable, str(SCRIPT), str(path), *args], capture_output=True, text=True)

    def findings(self, text: str, *args: str) -> list[str]:
        result = self.lint(text, *args)
        self.assertIn(result.returncode, (0, 1), f"lint crashed or refused: {result.stderr}")
        return [line.split(": ", 1)[1] for line in result.stdout.splitlines() if line.startswith(str(self.dir))]

    def rules(self, text: str) -> list[str]:
        return [f.split(":", 1)[0] for f in self.findings(text)]


class Punctuation(LintCase):
    def test_clean_prose_passes(self):
        result = self.lint("# Export\n\nThe job runs every night. It is not shown here.\n".replace("It is not shown here.", "The log shows each run."))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_em_dash_is_flagged_on_its_line(self):
        result = self.lint("# Export\n\nThe job runs nightly.\nThe job — a cron task — fails twice a month.\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("doc.md:4: dash", result.stdout)

    def test_en_dash_and_spaced_hyphen_are_flagged(self):
        self.assertEqual(self.rules("The job runs – then stops.\n\nThe job runs - then stops.\n"), ["dash", "dash"])

    def test_semicolon_is_flagged_but_entities_are_not(self):
        self.assertEqual(self.rules("The job runs nightly; the log grows.\n\nSales &amp; finance read it.\n"), ["semicolon"])

    def test_parenthesis_is_flagged_but_link_targets_and_list_markers_are_not(self):
        text = "The job (a cron task) fails.\n\nSee the [runbook](https://example.com/run(book)).\n\n1) Open the app.\n"
        self.assertEqual(self.rules(text), ["parenthesis"])


class Exemptions(LintCase):
    def test_code_spans_are_exempt(self):
        self.assertEqual(self.rules("Run `export --since 2026-09-01; echo (done) — ok` first.\n"), [])

    def test_fenced_code_is_exempt_including_nested_fences(self):
        text = "Intro line.\n\n````markdown\n```bash\necho a; echo (b) — c\n```\nstill code; (yes)\n````\n\nThe end.\n"
        self.assertEqual(self.rules(text), [])

    def test_front_matter_and_comments_are_exempt(self):
        text = "---\ntitle: Export — guide; draft (v2)\n---\n\n<!-- author note; (todo) —\nmore -->\nThe guide starts here.\n"
        self.assertEqual(self.rules(text), [])

    def test_quoted_ui_labels_and_bold_labels_are_exempt(self):
        text = 'Choose "Save (draft)" to keep it.\n\nChoose **Save (draft)** to keep it.\n\nChoose “Export — all” next.\n'
        self.assertEqual(self.rules(text), [])


class Sentences(LintCase):
    def test_long_sentence_is_flagged_with_its_count(self):
        findings = self.findings(LONG_SENTENCE + "\n")
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("long-sentence", findings[0])
        self.assertIn("28 words", findings[0])

    def test_sentence_at_the_limit_passes(self):
        twenty_five = " ".join(["word"] * 24) + " end."
        self.assertEqual(self.rules(twenty_five + "\n"), [])

    def test_max_words_option(self):
        self.assertEqual(self.lint("One two three four five six.\n", "--max-words", "5").returncode, 1)

    def test_abbreviations_and_decimals_do_not_split_sentences(self):
        text = "Use a tool, e.g. the export CLI, at version 2.5 for this. The run ends.\n"
        self.assertEqual(self.rules(text), [])

    def test_period_inside_closing_quote_ends_the_sentence(self):
        text = 'Instead of "a parameter worth varying," the mannered writer produces "a dial worth turning." Instead of "this point still matters," they write "this point earns its keep." The fix is short.\n'
        self.assertEqual([r for r in self.rules(text) if r == "long-sentence"], [])

    def test_period_inside_a_quote_does_not_end_the_sentence(self):
        text = 'Choose "Settings. Advanced" and then the export tab opens with every option that the routine needs for the nightly run to finish today for every team.\n'
        findings = self.findings(text)
        self.assertEqual([f for f in findings if f.startswith("long-sentence")].__len__(), 1, findings)

    def test_bold_lead_in_ends_its_sentence(self):
        text = "1. **One term per thing, defined on first use, across the whole document.** Give each acronym and internal system name a short definition the first time it appears in the text.\n"
        self.assertEqual(self.rules(text), [])

    def test_sentence_starting_with_a_code_span_is_its_own_sentence(self):
        text = "Write the marker before invoking the plugin, because the marker stops the first-run style question. `apply-profile.py` and `check-figure.py` read the marker to pick the palette for the figure.\n"
        self.assertEqual(self.rules(text), [])

    def test_heading_is_not_merged_into_the_next_bullet(self):
        heading = "Steps that a new teammate follows to set up the nightly export routine in Scheduler"
        text = f"## {heading}\n- Open Scheduler and choose Routines from the menu on the left side.\n"
        self.assertEqual(self.rules(text), [])

    def test_paragraph_lines_join_into_one_sentence(self):
        text = "The export job reads every new item from each source\nand writes one file per item into the export folder\nbefore it records where the run stopped today, every night.\n"
        findings = self.findings(text)
        self.assertEqual(len(findings), 1, findings)
        self.assertTrue(findings[0].startswith("long-sentence"))
        self.assertIn("doc.md:1:", self.lint(text).stdout)

    def test_table_cells_skip_length_but_not_punctuation(self):
        text = "| Step | Result |\n|---|---|\n| " + LONG_SENTENCE + " | Done — ok |\n"
        self.assertEqual(self.rules(text), ["dash"])

    def test_pipe_inside_code_does_not_split_a_table_cell(self):
        text = "| Command | Description |\n| --- | --- |\n| `grep x file | wc -l; echo done` | Counts matches |\n| a \\| b | Escaped pipe stays in one cell; flagged |\n"
        self.assertEqual(self.rules(text), ["semicolon"])

    def test_sentence_starting_with_it_is_flagged(self):
        self.assertEqual(self.rules("The probe runs on every request. It writes the snapshot.\n"), ["pronoun"])

    def test_high_average_is_flagged_once(self):
        sentence = " ".join(["word"] * 22) + " end."
        text = "\n\n".join([sentence] * 3) + "\n"
        self.assertEqual(self.rules(text), ["average-length"])


class Usage(LintCase):
    def test_missing_file_exits_2(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(self.dir / "nope.md")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_summary_line_counts_findings(self):
        result = self.lint("The job — nightly.\n")
        self.assertIn("lint-prose: 1 file(s), 1 finding(s)", result.stdout)


if __name__ == "__main__":
    unittest.main()
