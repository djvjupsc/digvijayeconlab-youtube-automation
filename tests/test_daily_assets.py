import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from scripts.generate_daily_assets import call_gemini, validate


class DailyAssetsValidationTests(unittest.TestCase):
    def valid_payload(self):
        return {
            "short_title": "Demand and Price",
            "short_description": "A short economics lesson.",
            "scenes": [
                {
                    "screen_title_en": f"Scene {i}",
                    "screen_title_hi": f"दृश्य {i}",
                    "screen_text_en": "A simple economics idea.",
                    "screen_text_hi": "एक सरल आर्थिक विचार।",
                    "voiceover_en": "This is an economics explanation.",
                    "voiceover_hi": "यह अर्थशास्त्र की व्याख्या है।",
                    "visual_direction": "Show a simple chart.",
                }
                for i in range(1, 6)
            ],
            "outro_en": "Follow DigvijayEconLab.",
            "outro_hi": "DigvijayEconLab से जुड़ें।",
            "community_post": "Today's lesson plan.",
            "poll_question": "Which unit do you want to revise?",
            "poll_options": ["Micro", "Macro"],
            "pinned_comment": "Share your answer.",
            "hashtags": ["#Economics", "#UGCNET", "#DigvijayEconLab"],
            "seo_metadata": [
                {
                    "unit": i,
                    "video_title": f"UGC NET Economics Unit {i}: Topic Explained",
                    "alternative_titles": [f"Alternative {i}A", f"Alternative {i}B"],
                    "primary_keyword": f"UGC NET Economics Unit {i}",
                    "secondary_keywords": ["economics", "exam preparation", "Hindi"],
                    "description": "Bilingual Economics lesson for exam preparation.",
                    "tags": ["UGC NET", "Economics", "DigvijayEconLab"],
                    "hashtags": ["#Economics", "#UGCNET"],
                    "thumbnail_text_options": ["Understand This", "Exam Revision"],
                    "playlist_title": f"UGC NET Economics Unit {i} | DigvijayEconLab",
                }
                for i in range(1, 11)
            ],
        }


    def test_call_gemini_retries_transient_503_then_succeeds(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"candidates": []}'

        temporary = urllib.error.HTTPError(
            "https://example.invalid", 503, "Unavailable", {}, io.BytesIO(b"busy")
        )
        with patch("scripts.generate_daily_assets.urllib.request.urlopen",
                   side_effect=[temporary, Response()]) as urlopen, \
             patch("scripts.generate_daily_assets.time.sleep") as sleep:
            result = call_gemini("test-key", {"contents": []})
        self.assertEqual(result, {"candidates": []})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(3)

    def test_call_gemini_does_not_retry_non_transient_http_error(self):
        bad_request = urllib.error.HTTPError(
            "https://example.invalid", 400, "Bad Request", {}, io.BytesIO(b"invalid")
        )
        with patch("scripts.generate_daily_assets.urllib.request.urlopen",
                   side_effect=bad_request) as urlopen, \
             patch("scripts.generate_daily_assets.time.sleep") as sleep:
            with self.assertRaisesRegex(SystemExit, "HTTP 400"):
                call_gemini("test-key", {"contents": []})
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()

    def test_call_gemini_stops_after_maximum_transient_attempts(self):
        unavailable = urllib.error.HTTPError(
            "https://example.invalid", 503, "Unavailable", {}, io.BytesIO(b"busy")
        )
        with patch("scripts.generate_daily_assets.urllib.request.urlopen",
                   side_effect=unavailable) as urlopen, \
             patch("scripts.generate_daily_assets.time.sleep") as sleep:
            with self.assertRaisesRegex(SystemExit, "after 5/5 attempt"):
                call_gemini("test-key", {"contents": []})
        self.assertEqual(urlopen.call_count, 5)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [3, 6, 12, 24])

    def test_accepts_valid_bilingual_short_and_community_post(self):
        self.assertTrue(validate(self.valid_payload()))

    def test_rejects_short_with_too_few_scenes(self):
        payload = self.valid_payload()
        payload["scenes"] = payload["scenes"][:3]
        with self.assertRaisesRegex(ValueError, "four and six scenes"):
            validate(payload)

    def test_rejects_missing_hindi_voiceover(self):
        payload = self.valid_payload()
        payload["scenes"][0]["voiceover_hi"] = ""
        with self.assertRaisesRegex(ValueError, "voiceover_hi"):
            validate(payload)

    def test_rejects_playlist_title_not_in_controlled_catalogue(self):
        payload = self.valid_payload()
        expected = {i: f"UGC NET Economics Unit {i} | DigvijayEconLab" for i in range(1, 11)}
        expected[1] = "Different playlist title"
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate(payload, expected)

    def test_rejects_duplicate_or_missing_unit_seo_metadata(self):
        payload = self.valid_payload()
        payload["seo_metadata"][1]["unit"] = 1
        with self.assertRaisesRegex(ValueError, "each unit number"):
            validate(payload)

    def test_rejects_overlong_seo_title(self):
        payload = self.valid_payload()
        payload["seo_metadata"][0]["video_title"] = "X" * 96
        with self.assertRaisesRegex(ValueError, "exceeds"):
            validate(payload)

    def test_rejects_overlong_seo_tags(self):
        payload = self.valid_payload()
        payload["seo_metadata"][0]["tags"] = ["keyword" * 70]
        with self.assertRaisesRegex(ValueError, "tags exceed"):
            validate(payload)

    def test_rejects_empty_poll_options(self):
        payload = self.valid_payload()
        payload["poll_options"] = ["Micro", ""]
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            validate(payload)


if __name__ == "__main__":
    unittest.main()
