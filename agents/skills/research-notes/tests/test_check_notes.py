"""Tests for check-notes.py. Run: python3 -m unittest discover -s tests -p 'test_*.py'"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-notes.py"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "note.md"


def note(claims: str, extra: str = "") -> str:
    """A minimal valid note around the given claim bullets; `extra` is inserted before Open questions."""
    header = ["# Router", "", "source: doc:src", "scope: test fixture", "read: 2026-09-15", "", "## In this system", ""]
    footer = ["", "## Open questions", "", "- none", ""]
    return "\n".join(header + [textwrap.dedent(claims).strip(), extra] + footer)


class CheckNotesCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "notes").mkdir()
        (self.root / "src").mkdir()
        (self.root / "src" / "commit.txt").write_text(textwrap.dedent("""\
            commit 4f2a9c1
            Author: Example Author
            Date:   2026-09-10

                Merged PR 5617: add snapshot probe to the router

                Background: the router had no record of which model served a
                request, so incidents could not be traced to a deployment.

                The probe runs on every request and records the model name.
                It writes the snapshot to the request log.
            """))
        (self.root / "src" / "router.md").write_text("# Router\n\nThe default model is gpt-5.6-luna.\nRequests time out after 30 seconds.\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_check(self, text: str, *args: str, sources: bool = True) -> subprocess.CompletedProcess:
        path = self.root / "notes" / "n.md"
        path.write_text(text)
        cmd = [sys.executable, str(SCRIPT), str(self.root / "notes")]
        if sources:
            cmd += ["--sources", str(self.root)]
        return subprocess.run(cmd + list(args), capture_output=True, text=True)


class ExistingBehavior(CheckNotesCase):
    def test_valid_note_passes(self):
        result = self.run_check(note("- [doc] Requests time out after 30 seconds. (src/router.md:4)"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_untagged_claim_fails(self):
        result = self.run_check(note("- Requests time out after 30 seconds. (src/router.md:4)"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("no confidence tag", result.stdout)

    def test_claim_without_citation_fails(self):
        result = self.run_check(note("- [doc] Requests time out after 30 seconds."))
        self.assertIn("no citation", result.stdout)

    def test_unknown_tag_fails(self):
        result = self.run_check(note("- [maybe] Requests time out. (src/router.md:4)"))
        self.assertIn("unknown tag", result.stdout)

    def test_missing_open_questions_fails(self):
        text = note("- [doc] Requests time out after 30 seconds. (src/router.md:4)").replace("## Open questions\n\n- none\n", "")
        result = self.run_check(text)
        self.assertIn("no 'Open questions' section", result.stdout)

    def test_absent_number_fails_doc_claim(self):
        result = self.run_check(note("- [doc] Requests time out after 45 seconds. (src/router.md:4)"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("45", result.stdout)

    def test_absent_number_is_only_a_note_for_inferred(self):
        result = self.run_check(note("- [inferred] Ten retries take 300 seconds. (from src/router.md:4)"))
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("note:", result.stdout)

    def test_citation_past_end_of_file_fails(self):
        result = self.run_check(note("- [doc] Requests time out. (src/router.md:99)"))
        self.assertIn("that file has", result.stdout)

    def test_term_without_citation_fails(self):
        result = self.run_check(note("- [doc] Requests time out after 30 seconds. (src/router.md:4)",
                                     extra="\n## Terms\n\n- **Probe**: records the model name.\n"))
        self.assertIn("Terms entry has no", result.stdout)

    def test_conflict_needs_two_citations(self):
        text = note("- [doc] Requests time out after 30 seconds. (src/router.md:4)")
        text = text.replace("- none", "- Conflict: timeout differs. src/router.md:4 says 30.")
        self.assertIn("must cite both sides", self.run_check(text).stdout)

    def test_fenced_code_is_ignored(self):
        text = note("- [doc] Requests time out after 30 seconds. (src/router.md:4)",
                    extra="\n```\n- not a claim\n```\n")
        self.assertEqual(self.run_check(text).returncode, 0)

    def test_template_passes_structure_check(self):
        result = subprocess.run([sys.executable, str(SCRIPT), str(TEMPLATE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)


class LineRanges(CheckNotesCase):
    def test_range_covers_number_five_lines_above(self):
        result = self.run_check(note("- [doc] PR 5617 added the probe that records the model name. (src/commit.txt:5-10)"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_single_line_still_misses_number_five_lines_above(self):
        result = self.run_check(note("- [doc] PR 5617 added the probe that records the model name. (src/commit.txt:10)"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("5617", result.stdout)

    def test_range_that_excludes_number_fails(self):
        result = self.run_check(note("- [doc] PR 5617 added the probe. (src/commit.txt:9-11)"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("5617", result.stdout)

    def test_range_past_end_fails(self):
        result = self.run_check(note("- [doc] The probe records the model name. (src/commit.txt:10-40)"))
        self.assertIn("that file has", result.stdout)

    def test_reversed_range_fails(self):
        result = self.run_check(note("- [doc] The probe records the model name. (src/commit.txt:10-5)"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("range", result.stdout)


class CodeSpans(CheckNotesCase):
    def test_number_inside_code_span_is_not_checked(self):
        result = self.run_check(note("- [doc] In `gpt-5.6-luna` deployments the probe writes the snapshot to the request log. (src/commit.txt:11)"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_number_outside_code_span_is_still_checked(self):
        result = self.run_check(note("- [doc] In `gpt-5.6-luna` deployments 40 probes write snapshots. (src/commit.txt:11)"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("40", result.stdout)


class WebClaims(CheckNotesCase):
    def test_web_claim_with_local_copy_is_number_checked(self):
        result = self.run_check(note("- [web] Requests time out after 45 seconds. (https://example.com/router, read 2026-09-15; src/router.md:4)"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("45", result.stdout)

    def test_web_claim_with_matching_local_copy_passes(self):
        result = self.run_check(note("- [web] Requests time out after 30 seconds. (https://example.com/router, read 2026-09-15; src/router.md:4)"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_web_claim_with_url_only_is_not_number_checked(self):
        result = self.run_check(note("- [web] Requests time out after 45 seconds. (https://example.com/router, read 2026-09-15)"))
        self.assertEqual(result.returncode, 0, result.stdout)


class EvidenceDates(CheckNotesCase):
    def setUp(self) -> None:
        super().setUp()
        (self.root / "evidence").mkdir()
        (self.root / "evidence" / "access.txt").write_text(
            "# command: reportctl access check\n# host: build-07\n# time: 2026-09-15T08:12:44Z\n# exit: 3\nsales_daily read allowed\n")

    def test_evidence_claim_without_date_fails(self):
        result = self.run_check(note("- [verified] The team can read sales_daily. (evidence/access.txt:5)"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("date", result.stdout)

    def test_evidence_claim_with_timestamp_passes(self):
        result = self.run_check(note("- [verified] The check ran at 2026-09-15T08:12:44Z and allowed reads of sales_daily. (evidence/access.txt:5)"))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_evidence_claim_with_date_passes(self):
        result = self.run_check(note("- [verified] As of 2026-09-15 the team can read sales_daily. (evidence/access.txt:5)"))
        self.assertEqual(result.returncode, 0, result.stdout)


class Deliverable(CheckNotesCase):
    def deliverable(self, body: str) -> Path:
        path = self.root / "doc.md"
        path.write_text("---\ntitle: Router change\ndate: 2026-09-15\n---\n\n" + textwrap.dedent(body))
        return path

    def notes_text(self) -> str:
        return note("- [doc] PR 5617 added the probe that writes to `request-log`. (src/commit.txt:5-11)")

    def test_names_and_numbers_from_notes_pass(self):
        doc = self.deliverable("# Change\n\nPR 5617 writes each snapshot to `request-log`.\n")
        result = self.run_check(self.notes_text(), "--deliverable", str(doc))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_code_name_missing_from_notes_fails(self):
        doc = self.deliverable("# Change\n\nIDs can carry suffixes such as `-msft-`.\n")
        result = self.run_check(self.notes_text(), "--deliverable", str(doc))
        self.assertEqual(result.returncode, 1)
        self.assertIn("-msft-", result.stdout)

    def test_number_missing_from_notes_fails(self):
        doc = self.deliverable("# Change\n\nThe probe adds 12 ms per request.\n")
        result = self.run_check(self.notes_text(), "--deliverable", str(doc))
        self.assertEqual(result.returncode, 1)
        self.assertIn("12", result.stdout)

    def test_front_matter_code_blocks_and_list_markers_are_skipped(self):
        doc = self.deliverable("# Change\n\n10. First step names PR 5617.\n\n```yaml\nretries: 99\n```\n")
        result = self.run_check(self.notes_text(), "--deliverable", str(doc))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_skip_section_leaves_out_illustrative_values(self):
        doc = self.deliverable("# Worked example\n\nOne request of 4096 tokens.\n\n# Parts\n\nPR 5617 writes the snapshot.\n")
        failing = self.run_check(self.notes_text(), "--deliverable", str(doc))
        self.assertIn("4096", failing.stdout)
        passing = self.run_check(self.notes_text(), "--deliverable", str(doc), "--skip-section", "Worked example")
        self.assertEqual(passing.returncode, 0, passing.stdout)


    def test_multi_line_html_comment_is_skipped(self):
        doc = self.deliverable("# Change\n\n<!-- author note:\nremember the 250 ms budget\n-->\nPR 5617 writes the snapshot.\n")
        result = self.run_check(self.notes_text(), "--deliverable", str(doc))
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_text_after_a_closing_comment_is_checked(self):
        doc = self.deliverable("# Change\n\n<!-- note\nstill a note --> The probe adds 12 ms.\n")
        result = self.run_check(self.notes_text(), "--deliverable", str(doc))
        self.assertIn("number 12", result.stdout)

    def test_subsections_of_a_skipped_section_stay_skipped(self):
        doc = self.deliverable("# Worked example\n\n## Step 1: send\n\nA 4096 token request.\n\n# Parts\n\nThe probe adds 12 ms.\n")
        result = self.run_check(self.notes_text(), "--deliverable", str(doc), "--skip-section", "worked example")
        self.assertNotIn("4096", result.stdout)
        self.assertIn("number 12", result.stdout)

    def test_digits_inside_note_code_spans_do_not_cover_deliverable_numbers(self):
        notes = note("- [doc] The service runs `llama-13b` in production. (src/router.md:3)")
        doc = self.deliverable("# Rollout\n\nResponse latency improved by 13% after the rollout.\n")
        result = self.run_check(notes, "--deliverable", str(doc), sources=False)
        self.assertIn("number 13 appears in no note", result.stdout)

    def test_code_span_name_must_match_a_whole_token(self):
        notes = note("- [doc] The service was built in 2013. (src/router.md:3)")
        doc = self.deliverable("# Rollout\n\nThe flag `13` turns the probe on.\n")
        result = self.run_check(notes, "--deliverable", str(doc), sources=False)
        self.assertIn("code span `13` appears in no note", result.stdout)

if __name__ == "__main__":
    unittest.main()
