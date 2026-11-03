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
