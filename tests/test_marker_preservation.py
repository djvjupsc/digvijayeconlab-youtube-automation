import unittest

from scripts.correct_script import preserve_original_verification_markers
from scripts.quality_checks import analyze_script


class OriginalVerificationMarkerTests(unittest.TestCase):
    def test_restores_markers_removed_by_correction_model(self):
        original = (
            "Claim one [VERIFY standard Giffen paradox literature]. "
            "Claim two [VERIFY historical origin source]."
        )
        corrected = "# Corrected draft\nNo verification notes were retained."
        updated, changes, unresolved = preserve_original_verification_markers(corrected, original)

        self.assertIn("[VERIFY standard Giffen paradox literature]", updated)
        self.assertIn("[VERIFY historical origin source]", updated)
        self.assertEqual(len(changes), 2)
        self.assertEqual(len(unresolved), 2)

        findings = analyze_script(updated, "Concept Explainer", "English")
        self.assertIn("UNRESOLVED_VERIFY_MARKER", {item["code"] for item in findings})

    def test_preserves_duplicate_occurrences_of_same_marker(self):
        marker = "[VERIFY source needed]"
        updated, changes, unresolved = preserve_original_verification_markers(
            "# Corrected draft without markers.",
            f"First claim {marker}. Second claim {marker}."
        )
        self.assertEqual(updated.count(marker), 2)
        self.assertEqual(len(changes), 2)
        self.assertEqual(len(unresolved), 2)

    def test_does_not_duplicate_exact_markers_already_retained(self):
        marker = "[VERIFY textbook source]"
        updated, changes, unresolved = preserve_original_verification_markers(
            f"# Corrected\n{marker}",
            f"# Original\n{marker}"
        )
        self.assertEqual(updated.count(marker), 1)
        self.assertEqual(changes, [])
        self.assertEqual(unresolved, [])

    def test_restores_original_text_when_model_rewrites_marker(self):
        original_marker = "[VERIFY historical attribution]"
        altered_marker = "[HUMAN VERIFY: historical attribution]"
        updated, changes, unresolved = preserve_original_verification_markers(
            f"# Corrected\n{altered_marker}",
            f"# Original\n{original_marker}"
        )
        self.assertIn(original_marker, updated)
        self.assertIn(altered_marker, updated)
        self.assertEqual(len(changes), 1)
        self.assertEqual(len(unresolved), 1)


if __name__ == "__main__":
    unittest.main()
