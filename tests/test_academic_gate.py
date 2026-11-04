import tempfile
import unittest
from pathlib import Path

from scripts.academic_gate import evaluate


class SeverityBasedAcademicGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.attestation = Path(self.temp.name) / "attestation.md"
        self.attestation.write_text(
            "The workflow input records that the user explicitly confirmed personal review.",
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
        ok, blockers = evaluate(self.report("**READY FOR HUMAN REVIEW**"), self.det, self.script, self.attestation)
        self.assertTrue(ok)
        self.assertEqual(blockers, [])

    def test_hold_due_only_to_medium_low_recommendations_passes_to_human_review(self):
        ok, blockers = evaluate(self.report("**HOLD FOR CORRECTION**", other="Medium: punctuation and style."), self.det, self.script, self.attestation)
        self.assertTrue(ok)
        self.assertEqual(blockers, [])

    def test_missing_overall_verdict_fails_closed(self):
        report = (
            "### Critical Issues\\n*None.*\\n"
            "### High-Priority Issues\\n*None.*\\n"
        )
        ok, blockers = evaluate(report, self.det, self.script, self.attestation)
        self.assertFalse(ok)
        self.assertTrue(any("Overall Verdict" in item for item in blockers))

    def test_nested_critical_high_subheading_content_is_included_and_blocks(self):
        nested = (
            "### Overall Verdict\\n**HOLD FOR CORRECTION**\\n\\n"
            "### Critical Issues\\nNone.\\n\\n"
            "### High-Priority Issues\\n"
            "#### Incorrect concept explanation\\n"
            "The Hindi explanation reverses the income-effect direction.\\n"
            "### Other Improvements\\nMinor punctuation.\\n"
        )
        ok, blockers = evaluate(nested, self.det, self.script, self.attestation)
        self.assertFalse(ok)
        self.assertTrue(any("high-priority" in x for x in blockers))

    def test_explicit_not_ready_verdict_blocks_even_when_issue_sections_are_empty(self):
        ok, blockers = evaluate(
            self.report("**NOT READY**"),
            self.det,
            self.script,
            self.attestation,
        )
        self.assertFalse(ok)
        self.assertTrue(any("explicitly rejected" in x for x in blockers))

    def test_explicit_not_approved_verdict_blocks_even_without_findings(self):
        ok, blockers = evaluate(
            self.report("**NOT APPROVED**"),
            self.det,
            self.script,
            self.attestation,
        )
        self.assertFalse(ok)
        self.assertTrue(any("explicitly rejected" in x for x in blockers))

    def test_any_high_priority_finding_blocks(self):
        ok, blockers = evaluate(self.report("**READY**", high="- Fix incorrect explanation."), self.det, self.script, self.attestation)
        self.assertFalse(ok)
        self.assertTrue(any("high-priority" in x for x in blockers))

    def test_any_critical_finding_blocks(self):
        ok, blockers = evaluate(self.report("**READY**", critical="- Wrong economic definition."), self.det, self.script, self.attestation)
        self.assertFalse(ok)
        self.assertTrue(any("critical" in x for x in blockers))

    def test_unresolved_marker_blocks(self):
        ok, blockers = evaluate(self.report("**READY**"), self.det, self.script + "[VERIFY claim]", self.attestation)
        self.assertFalse(ok)
        self.assertTrue(any("verification markers" in x for x in blockers))

    def test_missing_attestation_blocks(self):
        missing = Path(self.temp.name) / "missing.md"
        ok, blockers = evaluate(self.report("**READY**"), self.det, self.script, missing)
        self.assertFalse(ok)
        self.assertTrue(any("attestation" in x for x in blockers))

    def test_missing_issue_sections_fails_closed(self):
        incomplete = "### Overall Verdict\\n**READY**\\n"
        ok, blockers = evaluate(incomplete, self.det, self.script, self.attestation)
        self.assertFalse(ok)
        self.assertTrue(any("missing a parseable" in x for x in blockers))

    def test_structural_blocker_blocks(self):
        ok, blockers = evaluate(self.report("**READY**"), "- Blocking findings: 2\n", self.script, self.attestation)
        self.assertFalse(ok)
        self.assertTrue(any("structural" in x for x in blockers))


if __name__ == "__main__":
    unittest.main()
