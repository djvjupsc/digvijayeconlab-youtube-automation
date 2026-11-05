import json
import unittest
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


    def test_call_gemini_uses_shared_provider_adapter(self):
        expected = {"candidates": [{"content": {"parts": [{"text": "{\\"ok\\":true}"}]}}]}
        with patch("scripts.generate_daily_assets.generate_content", return_value=expected) as adapter:
            result = call_gemini("test-key", {"contents": []})
        self.assertEqual(result, expected)
        adapter.assert_called_once()
        self.assertEqual(adapter.call_args.args[1], "test-key")
        self.assertEqual(adapter.call_args.kwargs["label"], "Daily asset generation")

    def test_call_gemini_converts_provider_failure_to_actionable_exit(self):
        with patch("scripts.generate_daily_assets.generate_content", side_effect=RuntimeError("provider unavailable")):
            with self.assertRaisesRegex(SystemExit, "provider unavailable"):
                call_gemini("test-key", {"contents": []})

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
