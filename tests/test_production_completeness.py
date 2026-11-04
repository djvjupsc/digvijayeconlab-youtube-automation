import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.production_completeness import inspect


class ProductionCompletenessTests(unittest.TestCase):
    def build_package(self, root):
        date = "2026-11-05"
        output = root / "output"
        for folder in ("community", "seo", "shorts", "thumbnails", "longform"):
            (output / folder).mkdir(parents=True, exist_ok=True)
        (output / "quality_checks").mkdir(parents=True, exist_ok=True)
        (output / "quality_checks" / "daily-batch-status.md").write_text(
            "- Lessons passed to human review: 10 / 10\\n- Lessons blocked: 0 / 10\\n",
            encoding="utf-8",
        )
        (output / "community" / f"{date}-community-post.md").write_text("Community draft", encoding="utf-8")
        (output / "seo" / f"{date}-seo-metadata.json").write_text(json.dumps([{"unit": i} for i in range(1, 11)]), encoding="utf-8")
        (output / "seo" / f"{date}-seo-metadata.md").write_text("SEO draft", encoding="utf-8")
        (output / "shorts" / f"{date}-short.json").write_text(json.dumps({"short_title": "Draft"}), encoding="utf-8")
        (output / "shorts" / f"{date}-short-storyboard.md").write_text("Storyboard", encoding="utf-8")
        (output / "shorts" / f"{date}-short-render.json").write_text(json.dumps({"preview_only": True, "voice_clone_used": False}), encoding="utf-8")
        (output / "shorts" / f"{date}-digvijayeconlab-short.mp4").write_bytes(b"draft mp4")
        (output / "shorts" / f"{date}-prepublish-audit.json").write_text(json.dumps({"status": "blocked"}), encoding="utf-8")
        for unit in range(1, 11):
            Image.new("RGB", (1280, 720)).save(output / "thumbnails" / f"unit-{unit:02d}-thumbnail.jpg")
        video = output / "longform" / f"{date}-unit-07.mp4"
        video.write_bytes(b"draft mp4")
        (output / "longform" / f"{date}-longform-render.json").write_text(json.dumps({
            "status": "rendered", "video": str(video.relative_to(root)),
            "voice_clone_used": False, "audit_status": "preview_only"
        }), encoding="utf-8")
        return date

    def test_complete_preview_package_is_not_marked_publication_approved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            date = self.build_package(root)
            self.assertTrue(inspect(root, date))
            report = json.loads((root / "output" / "production-completeness.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "draft_complete")
            self.assertEqual(report["publication_status"], "blocked")
            self.assertEqual(report["release_label"], "DRAFT COMPLETE — PUBLICATION BLOCKED")
            self.assertFalse(report["quality_and_release"]["publication_approved"])
            self.assertFalse(report["quality_and_release"]["owner_authorized_voice_used_for_both_videos"])
            self.assertEqual(report["quality_and_release"]["short_prepublication_audit"], "blocked")

    def test_missing_deliverable_makes_package_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            date = self.build_package(root)
            (root / "output" / "thumbnails" / "unit-10-thumbnail.jpg").unlink()
            self.assertFalse(inspect(root, date))
            report = json.loads((root / "output" / "production-completeness.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "production_incomplete")
            self.assertEqual(report["release_label"], "PRODUCTION INCOMPLETE")
            self.assertTrue(report["missing_or_invalid_deliverables"])


if __name__ == "__main__":
    unittest.main()
