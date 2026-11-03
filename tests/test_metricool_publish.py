import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.metricool_publish import _already_scheduled, publication_gate


class MetricoolPublicationGateTests(unittest.TestCase):
    def make_pack(self, root):
        (root / "output/corrected_scripts").mkdir(parents=True)
        (root / "output/reviews").mkdir(parents=True)
        (root / "output/quality_checks").mkdir(parents=True)
        manifest = {"units": []}
        for unit in range(1, 11):
            stem = f"unit-{unit:02d}-topic"
            manifest["units"].append({"unit": unit})
            (root / "output/corrected_scripts" / f"{stem}.md").write_text(
                "# Reviewed lesson\nNo verification gaps remain.\n", encoding="utf-8"
            )
            (root / "output/reviews" / f"{stem}-quality-review.md").write_text(
                "# Academic Quality Review\n\n## Overall Verdict\nREADY FOR PRODUCTION\n",
                encoding="utf-8",
            )
            (root / "output/reviews" / f"{stem}-original-quality-review.md").write_text(
                "# Original Academic Review\n\n## Overall Verdict\nREADY FOR CORRECTION\n",
                encoding="utf-8",
            )
            (root / "output/quality_checks" / f"{stem}-corrected-deterministic-check.md").write_text(
                "# Deterministic Script Quality Check\n- Blocking findings: 0\n"
                "## Gate result\n**STRUCTURAL CHECKS PASSED — HUMAN REVIEW STILL REQUIRED**\n",
                encoding="utf-8",
            )
        return manifest

    def test_passes_when_all_ten_units_have_review_and_no_verification_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.make_pack(root)
            passed, issues = publication_gate(manifest, root)
            self.assertTrue(passed)
            self.assertEqual(issues, [])

    def test_blocks_when_any_unit_has_unresolved_verify_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.make_pack(root)
            path = root / "output/corrected_scripts/unit-04-topic.md"
            path.write_text("# Lesson\n[VERIFY: check textbook claim]\n", encoding="utf-8")
            passed, issues = publication_gate(manifest, root)
            self.assertFalse(passed)
            self.assertTrue(any("Unit 4" in issue and "VERIFY" in issue for issue in issues))

    def test_blocks_when_reviewer_returns_hold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.make_pack(root)
            path = root / "output/reviews/unit-07-topic-quality-review.md"
            path.write_text("# Review\n## Overall Verdict\nHOLD FOR CORRECTION\n", encoding="utf-8")
            passed, issues = publication_gate(manifest, root)
            self.assertFalse(passed)
            self.assertTrue(any("Unit 7" in issue and "HOLD" in issue for issue in issues))

    def test_blocks_when_deterministic_report_has_blocking_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self.make_pack(root)
            path = root / "output/quality_checks/unit-03-topic-corrected-deterministic-check.md"
            path.write_text("# Report\n- Blocking findings: 2\n**HOLD FOR CORRECTION**\n", encoding="utf-8")
            passed, issues = publication_gate(manifest, root)
            self.assertFalse(passed)
            self.assertTrue(any("Unit 3" in issue for issue in issues))

    def test_does_not_claim_duplicate_scheduled_video_is_new(self):
        posts = [
            {
                "youtubeData": {"title": "Daily Economics Short"},
                "publicationDate": {"dateTime": "2026-11-05T19:00:00"},
            }
        ]
        when = datetime(2026, 11, 5, 19, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
        self.assertIsNotNone(_already_scheduled(posts, "Daily Economics Short", when))
        self.assertIsNone(_already_scheduled(posts, "Different Title", when))


if __name__ == "__main__":
    unittest.main()
