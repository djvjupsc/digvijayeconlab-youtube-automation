import json
import unittest

from scripts.correct_script import parse_structured_response


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

    def test_gemini_retry_policy_covers_temporary_server_and_rate_limit_errors(self):
        from scripts.correct_script import MAX_GEMINI_ATTEMPTS, RETRYABLE_HTTP_STATUS
        self.assertEqual(MAX_GEMINI_ATTEMPTS, 5)
        self.assertTrue({429, 500, 502, 503, 504}.issubset(RETRYABLE_HTTP_STATUS))
        self.assertNotIn(400, RETRYABLE_HTTP_STATUS)

    def test_review_and_correction_load_source_notes_from_file(self):
        # File-reading is covered by the CLI scripts; this regression protects
        # the intended path contract in their usage documentation/prompt.
        from pathlib import Path
        review_source = Path("scripts/review_script.py").read_text(encoding="utf-8")
        correction_source = Path("scripts/correct_script.py").read_text(encoding="utf-8")
        self.assertIn("source_notes_path.read_text(encoding=\"utf-8\")", review_source)
        self.assertIn("source_notes_path.read_text(encoding=\"utf-8\")", correction_source)

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
