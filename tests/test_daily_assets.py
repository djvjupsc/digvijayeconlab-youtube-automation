import unittest
from scripts.generate_daily_assets import validate


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
        }

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

    def test_rejects_empty_poll_options(self):
        payload = self.valid_payload()
        payload["poll_options"] = ["Micro", ""]
        with self.assertRaisesRegex(ValueError, "non-empty strings"):
            validate(payload)


if __name__ == "__main__":
    unittest.main()
