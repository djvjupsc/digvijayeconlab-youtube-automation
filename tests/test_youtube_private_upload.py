import json
import tempfile
import unittest
from pathlib import Path

from scripts.youtube_private_upload import YouTubeUploadError, upload_private_video


class FakeResponse:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class YouTubePrivateUploadTests(unittest.TestCase):
    def test_resumable_upload_is_private_and_declares_synthetic_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.mp4"
            path.write_bytes(b"fake-mp4")
            requests = []

            def opener(request, timeout=0):
                requests.append(request)
                if request.get_method() == "POST":
                    metadata = json.loads(request.data.decode("utf-8"))
                    self.assertEqual(metadata["status"]["privacyStatus"], "private")
                    self.assertTrue(metadata["status"]["containsSyntheticMedia"])
                    self.assertEqual(request.headers["X-upload-content-type"], "video/mp4")
                    return FakeResponse({}, {"Location": "https://upload.youtube.test/session/123"})
                self.assertEqual(request.get_method(), "PUT")
                self.assertEqual(request.full_url, "https://upload.youtube.test/session/123")
                self.assertEqual(request.data, b"fake-mp4")
                self.assertEqual(request.headers["Content-range"], "bytes 0-7/8")
                return FakeResponse({
                    "id": "abc123",
                    "status": {
                        "privacyStatus": "private",
                        "containsSyntheticMedia": True,
                    },
                })

            result = upload_private_video(
                path,
                {"short_title": "Economics Short", "short_description": "Test", "tags": ["Economics"]},
                "access-token",
                opener=opener,
            )
            self.assertEqual(len(requests), 2)
            self.assertEqual(result["privacy_status"], "private")
            self.assertTrue(result["contains_synthetic_media"])
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

    def test_rejects_missing_resumable_session_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "short.mp4"
            path.write_bytes(b"fake-mp4")
            with self.assertRaises(YouTubeUploadError):
                upload_private_video(
                    path,
                    {"short_title": "Economics Short"},
                    "access-token",
                    opener=lambda *_args, **_kwargs: FakeResponse({}),
                )


if __name__ == "__main__":
    unittest.main()
