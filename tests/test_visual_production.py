import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.render_longform_video import (
    draw_slide,
    group_sections,
    language_for,
    parse_lesson,
    render_voice_policy,
)
from scripts.render_thumbnails import find_font, render_one
from scripts.hindi_typography import find_hindi_font, load_hindi_font


class VisualProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font_regular = find_font(
            "DejaVu Sans", ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
        )
        cls.font_bold = find_font(
            "DejaVu Sans:style=Bold", ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        )
        cls.hindi_font = find_hindi_font()
        load_hindi_font(cls.hindi_font, 32)

    def test_thumbnail_is_1280_by_720_and_under_two_mb(self):
        item = {
            "unit": 1,
            "video_title": "Theory of Consumer Behaviour | UGC NET Economics",
            "thumbnail_text_options": ["Consumer Behaviour"],
            "playlist_title": "UGC NET Economics Unit 1 | Micro Economics | DigvijayEconLab",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "unit-01-thumbnail.jpg"
            report = render_one(item, path, self.font_regular, self.font_bold, self.hindi_font)
            with Image.open(path) as image:
                self.assertEqual(image.size, (1280, 720))
                self.assertEqual(image.format, "JPEG")
            self.assertLess(report["bytes"], 2_000_000)

    def test_markdown_parser_keeps_paragraphs_and_skips_code_tables_and_sources(self):
        sample = """# Lesson: Demand

## Meaning of Demand

Demand means the quantity consumers are willing and able to purchase at different prices.
मांग से आशय विभिन्न कीमतों पर खरीदी जाने वाली मात्रा से है।

| Price | Quantity |
|---|---|
| 10 | 20 |

## Example

A hypothetical example helps explain the concept in a classroom setting.

```
do not narrate this
```

## Source Notes

Do not narrate this private source-only section.
"""
        sections = parse_lesson(sample)
        all_text = " ".join(text for _, paragraphs in sections for text in paragraphs)
        self.assertIn("Demand means", all_text)
        self.assertIn("मांग से आशय", all_text)
        self.assertIn("hypothetical example", all_text)
        self.assertNotIn("do not narrate", all_text)
        self.assertNotIn("private source-only", all_text)

    def test_hindi_font_uses_raqm_shaping(self):
        from PIL import features
        self.assertTrue(features.check_feature("raqm"))
        font = load_hindi_font(self.hindi_font, 40)
        self.assertIsNotNone(font.getmask("हिन्दी अर्थशास्त्र").getbbox())

    def test_language_detection_handles_hindi_and_english(self):
        self.assertEqual(language_for("मांग का अर्थ विभिन्न कीमतों पर मात्रा है।"), "hi")
        self.assertEqual(language_for("Demand is the quantity consumers are willing to buy."), "en")

    def test_grouping_preserves_every_paragraph(self):
        sections = [
            ("Meaning", ["First economic explanation paragraph.", "दूसरा हिंदी व्याख्यात्मक अनुच्छेद।"]),
            ("Example", ["A hypothetical worked example with clear steps and units."]),
        ]
        groups = group_sections(sections, max_chars=35)
        flattened = [p for group in groups for p in group["paragraphs"]]
        expected = [p for _, paragraphs in sections for p in paragraphs]
        self.assertEqual(flattened, expected)

    def test_production_voice_is_upload_eligible(self):
        policy = render_voice_policy(True, ["Chatterbox Multilingual V3"], False)
        self.assertEqual(policy["audit_status"], "pass")
        self.assertTrue(policy["voice_clone_used"])
        self.assertTrue(policy["upload_eligible"])
        self.assertFalse(policy["preview_only"])

    def test_preview_voice_renders_but_is_never_upload_eligible(self):
        policy = render_voice_policy(False, ["eSpeak NG (en-us)"], False)
        self.assertEqual(policy["audit_status"], "preview")
        self.assertFalse(policy["voice_clone_used"])
        self.assertFalse(policy["upload_eligible"])
        self.assertTrue(policy["preview_only"])

    def test_unresolved_markers_block_even_production_voice(self):
        policy = render_voice_policy(True, ["Chatterbox Multilingual V3"], True)
        self.assertEqual(policy["audit_status"], "blocked")
        self.assertFalse(policy["upload_eligible"])

    def test_longform_slide_is_landscape_1920_by_1080(self):
        group = {
            "heading": "Theory of Consumer Behaviour",
            "paragraphs": [
                "Consumers choose bundles to maximize utility subject to a budget constraint.",
                "उपभोक्ता बजट सीमा के अंतर्गत उपयोगिता को अधिकतम करने के लिए वस्तुओं का चयन करते हैं।",
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "slide.png"
            draw_slide(
                group, 0, 1, 1, "Micro Economics", "Consumer Behaviour",
                self.font_regular, self.font_bold, self.hindi_font, path,
            )
            with Image.open(path) as image:
                self.assertEqual(image.size, (1920, 1080))
                self.assertEqual(image.format, "PNG")


if __name__ == "__main__":
    unittest.main()
