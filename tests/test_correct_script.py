import json
import unittest

from scripts.correct_script import (
    apply_known_editorial_repairs,
    parse_structured_response,
    preserve_original_verification_markers,
)


class StructuredCorrectionTests(unittest.TestCase):
    def test_valid_structured_response_is_accepted(self):
        original = "# Original"
        payload = {
            "corrected_script": "# Corrected",
            "correction_log": ["Improved bilingual parity."],
            "unresolved_items": ["Verify Giffen goods example."],
        }
        result = parse_structured_response(json.dumps(payload), original)
        self.assertEqual(result[0], "# Corrected")
        self.assertEqual(result[1], payload["correction_log"])
        self.assertEqual(result[2], payload["unresolved_items"])
        self.assertFalse(result[3])

    def test_malformed_json_preserves_original(self):
        original = "# Keep exactly"
        result = parse_structured_response('{"corrected_script":', original)
        self.assertEqual(result[0], original)
        self.assertTrue(result[3])
        self.assertTrue(result[1])
        self.assertTrue(result[2])

    def test_repairs_known_regional_placeholder_and_bengali_script_contamination(self):
        source = (
            "in MPPSC region X. "
            "MPPSC क्षेत्र X में प्रदूषण है। "
            "(বাজার असफलता की परिभाषा) "
            "negative consumption/production externality"
        )
        repaired, changes = apply_known_editorial_repairs(source)
        self.assertIn("a hypothetical industrial region", repaired)
        self.assertIn("एक काल्पनिक औद्योगिक क्षेत्र में", repaired)
        self.assertIn("(बाजार असफलता की परिभाषा)", repaired)
        self.assertIn("negative production externality", repaired)
        self.assertNotIn("MPPSC region X", repaired)
        self.assertNotIn("বাজার", repaired)
        self.assertEqual(len(changes), 4)

    def test_source_notes_can_resolve_original_markers_when_no_items_remain(self):
        corrected, changes, unresolved = preserve_original_verification_markers(
            "# Corrected claim.",
            "# Claim [VERIFY].\nदावा [सत्यापन योग्य]।",
            unresolved_items=[],
            source_notes_supplied=True,
        )
        self.assertEqual(corrected, "# Corrected claim.")
        self.assertFalse(unresolved)
        self.assertTrue(any("Cleared original verification markers" in item for item in changes))

    def test_markers_are_preserved_when_no_source_notes_were_supplied(self):
        corrected, changes, unresolved = preserve_original_verification_markers(
            "# Edited claim.",
            "# Claim [VERIFY].",
            unresolved_items=[],
            source_notes_supplied=False,
        )
        self.assertIn("[VERIFY]", corrected)
        self.assertTrue(unresolved)

    def test_gemini_retry_policy_covers_temporary_server_and_rate_limit_errors(self):
        from scripts.correct_script import MAX_GEMINI_ATTEMPTS, RETRYABLE_HTTP_STATUS
        self.assertEqual(MAX_GEMINI_ATTEMPTS, 5)
        self.assertTrue({429, 500, 502, 503, 504}.issubset(RETRYABLE_HTTP_STATUS))
        self.assertNotIn(400, RETRYABLE_HTTP_STATUS)

    def test_review_and_correction_use_shared_optional_source_notes_loader(self):
        from pathlib import Path
        review_source = Path("scripts/review_script.py").read_text(encoding="utf-8")
        correction_source = Path("scripts/correct_script.py").read_text(encoding="utf-8")
        self.assertIn("load_optional_source_notes", review_source)
        self.assertIn("load_optional_source_notes", correction_source)

    def test_missing_or_wrong_fields_preserve_original(self):
        original = "# Keep exactly"
        for payload in (
            {"corrected_script": "", "correction_log": [], "unresolved_items": []},
            {"corrected_script": "# partial", "correction_log": "not an array", "unresolved_items": []},
            {"corrected_script": "# partial", "correction_log": [], "unresolved_items": "not an array"},
        ):
            with self.subTest(payload=payload):
                result = parse_structured_response(json.dumps(payload), original)
                self.assertEqual(result[0], original)
                self.assertTrue(result[3])


if __name__ == "__main__":
    unittest.main()
