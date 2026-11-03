import json
import tempfile
import unittest
from pathlib import Path

from scripts.youtube_private_upload import YouTubeUploadError, _load_upload_job, upload_private_video


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


    def test_longform_upload_requires_owner_voice_and_passing_technical_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "output/longform").mkdir(parents=True)
            (root / "output/seo").mkdir(parents=True)
            video = root / "output/longform/lesson.mp4"
            video.write_bytes(b"fake-mp4")
            report = {
                "audit_status": "pass",
                "upload_eligible": True,
                "voice_clone_used": True,
                "music": "none",
                "review_required": True,
                "unit": 1,
                "video": "output/longform/lesson.mp4",
                "technical": {
                    "width": 1920, "height": 1080, "video_codec": "h264",
                    "audio_streams": 1, "duration_seconds": 300,
                },
            }
            (root / "output/longform/2026-11-04-longform-render.json").write_text(
                json.dumps(report), encoding="utf-8"
            )
            (root / "output/seo/2026-11-04-seo-metadata.json").write_text(
                json.dumps([{
                    "unit": 1, "video_title": "Micro Economics Lesson",
                    "description": "Bilingual lesson", "tags": ["Economics"],
                }]),
                encoding="utf-8",
            )
            job, issue = _load_upload_job(root, "2026-11-04", "longform")
            self.assertIsNone(issue)
            self.assertEqual(job[0], video)
            self.assertEqual(job[1]["video_title"], "Micro Economics Lesson")

    def test_longform_upload_blocks_placeholder_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "output/longform").mkdir(parents=True)
            (root / "output/longform/lesson.mp4").write_bytes(b"fake-mp4")
            (root / "output/longform/2026-11-04-longform-render.json").write_text(
                json.dumps({
                    "audit_status": "blocked", "upload_eligible": False,
                    "voice_clone_used": False, "music": "none",
                    "review_required": True, "unit": 1,
                    "video": "output/longform/lesson.mp4",
                    "technical": {"width": 1920, "height": 1080,
                                  "video_codec": "h264", "audio_streams": 1,
                                  "duration_seconds": 300},
                }),
                encoding="utf-8",
            )
            job, issue = _load_upload_job(root, "2026-11-04", "longform")
            self.assertIsNone(job)
            self.assertIn("not eligible", issue)

    def test_uploader_accepts_longform_metadata_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lesson.mp4"
            path.write_bytes(b"fake-mp4")
            requests = []

            def opener(request, timeout=0):
                requests.append(request)
                if request.get_method() == "POST":
                    metadata = json.loads(request.data.decode("utf-8"))
                    self.assertEqual(metadata["snippet"]["title"], "Long Economics Lesson")
                    self.assertEqual(metadata["snippet"]["description"], "Lesson description")
                    return FakeResponse({}, {"Location": "https://upload.youtube.test/session/long"})
                return FakeResponse({
                    "id": "long123",
                    "status": {"privacyStatus": "private", "containsSyntheticMedia": True},
                })

            result = upload_private_video(
                path,
                {"video_title": "Long Economics Lesson", "description": "Lesson description",
                 "tags": ["Economics"]},
                "access-token",
                opener=opener,
            )
            self.assertEqual(result["video_id"], "long123")


if __name__ == "__main__":
    unittest.main()
