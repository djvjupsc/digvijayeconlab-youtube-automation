import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.academic_gate import evaluate, main


class SeverityBasedAcademicGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source_verification = Path(self.temp.name) / "source-verification.md"
        self.source_verification.write_text(
            "AI-assisted source review completed. This is not a human sign-off.",
            encoding="utf-8",
        )
        self.det = "- Blocking findings: 0\n"
        self.script = "# Law of Demand\nNo unresolved markers.\n"

    def tearDown(self):
        self.temp.cleanup()

    def report(self, verdict, critical="*None.* (No theoretical contradictions or unsupported claims were identified.)", high="*None.*", other="Minor punctuation suggestion."):
        return (
            f"### Overall Verdict\n{verdict}\n\n"
            f"### Critical Issues\n{critical}\n\n"
            f"### High-Priority Issues\n{high}\n\n"
            f"### Other Improvements\n{other}\n"
        )

    def test_ready_with_no_critical_or_high_issues_passes(self):
        ok, blockers = evaluate(self.report("**READY FOR HUMAN REVIEW**"), self.det, self.script, self.source_verification)
        self.assertTrue(ok)
        self.assertEqual(blockers, [])

    def test_hold_due_only_to_medium_low_recommendations_passes_to_human_review(self):
        ok, blockers = evaluate(self.report("**HOLD FOR CORRECTION**", other="Medium: punctuation and style."), self.det, self.script, self.source_verification)
        self.assertTrue(ok)
        self.assertEqual(blockers, [])

    def test_generic_lesson_gate_does_not_require_a_separate_source_report(self):
        ok, blockers = evaluate(
            self.report("**READY FOR HUMAN REVIEW**"),
            self.det,
            self.script,
        )
        self.assertTrue(ok)
        self.assertEqual(blockers, [])

    def test_generic_gate_keeps_unresolved_correction_items_for_human_review(self):
        correction_log = Path(self.temp.name) / "correction-log.md"
        correction_log.write_text(
            "## Unresolved human-verification items\n"
            "- Verify the historical date against an authoritative source.\n",
            encoding="utf-8",
        )
        ok, blockers = evaluate(
            self.report("**READY FOR HUMAN REVIEW**"),
            self.det,
            self.script,
            correction_log=correction_log,
        )
        self.assertTrue(ok)
        self.assertEqual(blockers, [])

    def test_generic_gate_accepts_correction_log_with_no_unresolved_items(self):
        correction_log = Path(self.temp.name) / "correction-log.md"
        correction_log.write_text(
            "## Unresolved human-verification items\n"
            "- None reported; human review is still required.\n",
            encoding="utf-8",
        )
        ok, blockers = evaluate(
            self.report("**READY FOR HUMAN REVIEW**"),
            self.det,
            self.script,
            correction_log=correction_log,
        )
        self.assertTrue(ok)
        self.assertEqual(blockers, [])

    def test_missing_overall_verdict_fails_closed(self):
        report = (
            "### Critical Issues\n*None.*\n"
            "### High-Priority Issues\n*None.*\n"
        )
        ok, blockers = evaluate(report, self.det, self.script, self.source_verification)
        self.assertFalse(ok)
        self.assertTrue(any("Overall Verdict" in item for item in blockers))

    def test_nested_critical_high_subheading_content_is_included_and_blocks(self):
        nested = (
            "### Overall Verdict\n**HOLD FOR CORRECTION**\n\n"
            "### Critical Issues\nNone.\n\n"
            "### High-Priority Issues\n"
            "#### Incorrect concept explanation\n"
            "The Hindi explanation reverses the income-effect direction.\n"
            "### Other Improvements\nMinor punctuation.\n"
        )
        ok, blockers = evaluate(nested, self.det, self.script, self.source_verification)
        self.assertFalse(ok)
        self.assertTrue(any("high-priority" in x for x in blockers))

    def test_explicit_not_ready_verdict_blocks_even_when_issue_sections_are_empty(self):
        ok, blockers = evaluate(
            self.report("**NOT READY**"),
            self.det,
            self.script,
            self.source_verification,
        )
        self.assertFalse(ok)
        self.assertTrue(any("explicitly rejected" in x for x in blockers))

    def test_explicit_not_approved_verdict_blocks_even_without_findings(self):
        ok, blockers = evaluate(
            self.report("**NOT APPROVED**"),
            self.det,
            self.script,
            self.source_verification,
        )
        self.assertFalse(ok)
        self.assertTrue(any("explicitly rejected" in x for x in blockers))

    def test_any_high_priority_finding_blocks(self):
        ok, blockers = evaluate(self.report("**READY**", high="- Fix incorrect explanation."), self.det, self.script, self.source_verification)
        self.assertFalse(ok)
        self.assertTrue(any("high-priority" in x for x in blockers))

    def test_any_critical_finding_blocks(self):
        ok, blockers = evaluate(self.report("**READY**", critical="- Wrong economic definition."), self.det, self.script, self.source_verification)
        self.assertFalse(ok)
        self.assertTrue(any("critical" in x for x in blockers))

    def test_unresolved_marker_is_preserved_but_does_not_block_human_review(self):
        ok, blockers = evaluate(
            self.report("**READY FOR HUMAN REVIEW**"),
            self.det,
            self.script + "[VERIFY claim]",
            self.source_verification,
        )
        self.assertTrue(ok)
        self.assertEqual(blockers, [])

    def test_cli_writes_remaining_verification_marker_count(self):
        review_path = Path(self.temp.name) / "review.md"
        deterministic_path = Path(self.temp.name) / "deterministic.md"
        script_path = Path(self.temp.name) / "corrected.md"
        output_path = Path(self.temp.name) / "decision.md"

        review_path.write_text(self.report("**READY FOR HUMAN REVIEW**"), encoding="utf-8")
        deterministic_path.write_text(self.det, encoding="utf-8")
        script_path.write_text("# Lesson\n[VERIFY: check this claim]\n", encoding="utf-8")

        argv = [
            "academic_gate.py",
            str(review_path),
            str(deterministic_path),
            str(script_path),
            "--output",
            str(output_path),
        ]
        with patch("sys.argv", argv):
            main()

        decision = output_path.read_text(encoding="utf-8")
        self.assertIn("- Remaining verification markers: 1", decision)
        self.assertIn("PASS — READY FOR HUMAN REVIEW", decision)

    def test_missing_source_verification_blocks(self):
        missing = Path(self.temp.name) / "missing.md"
        ok, blockers = evaluate(self.report("**READY**"), self.det, self.script, missing)
        self.assertFalse(ok)
        self.assertTrue(any("source-verification" in x for x in blockers))

    def test_missing_issue_sections_fails_closed(self):
        incomplete = "### Overall Verdict\n**READY**\n"
        ok, blockers = evaluate(incomplete, self.det, self.script, self.source_verification)
        self.assertFalse(ok)
        self.assertTrue(any("missing a parseable" in x for x in blockers))

    def test_structural_blocker_blocks(self):
        ok, blockers = evaluate(self.report("**READY**"), "- Blocking findings: 2\n", self.script, self.source_verification)
        self.assertFalse(ok)
        self.assertTrue(any("structural" in x for x in blockers))


if __name__ == "__main__":
    unittest.main()
