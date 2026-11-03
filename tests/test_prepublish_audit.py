import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepublish_audit import audit


class PrepublishAuditTests(unittest.TestCase):
    def make_files(self, root, clone=True):
        storyboard = root / "short.json"
        render = root / "render.json"
        video = root / "short.mp4"
        output = root / "audit.json"
        storyboard.write_text(json.dumps({
            "short_title": "Demand explained with an Indian example",
            "scenes": [{}, {}, {}, {}],
        }), encoding="utf-8")
        render.write_text(json.dumps({
            "music": "none",
            "voice_clone_used": clone,
            "voice_reference_stored_in_repository": False,
            "review_required": True,
        }), encoding="utf-8")
        video.write_bytes(b"test")
        return storyboard, render, video, output

    @patch("scripts.prepublish_audit.inspect_video", return_value={
        "duration_seconds": 42.0, "width": 1080, "height": 1920,
        "video_codec": "h264", "audio_streams": 1,
    })
    def test_passes_technical_and_owner_voice_checks_but_never_self_approves(self, _):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_files(Path(tmp))
            self.assertTrue(audit(*map(str, paths)))
            report = json.loads(paths[3].read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertFalse(report["publish_authorized"])
            self.assertTrue(report["human_review_required"])

    def test_blocks_generic_placeholder_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_files(Path(tmp), clone=False)
            self.assertFalse(audit(*map(str, paths)))
            report = json.loads(paths[3].read_text(encoding="utf-8"))
            self.assertTrue(any("voice clone" in item.lower() for item in report["blocking_issues"]))

    def test_blocks_if_music_is_added_without_a_reviewed_license_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self.make_files(Path(tmp))
            render = json.loads(paths[1].read_text(encoding="utf-8"))
            render["music"] = "background track"
            paths[1].write_text(json.dumps(render), encoding="utf-8")
            self.assertFalse(audit(*map(str, paths)))


if __name__ == "__main__":
    unittest.main()
