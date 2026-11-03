import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.youtube_private_upload import YouTubeUploadError, upload_private_video


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class YouTubePrivateUploadTests(unittest.TestCase):
    def test_upload_requests_private_visibility_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.mp4"
            path.write_bytes(b"fake-mp4")
            captured = {}

            def opener(request, timeout=0):
                captured["request"] = request
                captured["timeout"] = timeout
                return FakeResponse({"id": "abc123", "status": {"privacyStatus": "private"}})

            result = upload_private_video(
                path,
                {"short_title": "Economics Short", "short_description": "Test", "tags": ["Economics"]},
                "access-token",
                opener=opener,
            )
            body = captured["request"].data
            self.assertIn(b'"privacyStatus": "private"', body)
            self.assertNotIn(b'"privacyStatus": "public"', body)
            self.assertEqual(result["privacy_status"], "private")
            self.assertEqual(result["video_id"], "abc123")

    def test_rejects_missing_video(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(YouTubeUploadError):
                upload_private_video(
                    Path(tmp) / "missing.mp4",
                    {"short_title": "Test"},
                    "access-token",
                    opener=lambda *_args, **_kwargs: None,
                )

    def test_rejects_missing_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.mp4"
            path.write_bytes(b"fake-mp4")
            with self.assertRaises(YouTubeUploadError):
                upload_private_video(path, {}, "access-token",
                                    opener=lambda *_args, **_kwargs: None)


if __name__ == "__main__":
    unittest.main()
