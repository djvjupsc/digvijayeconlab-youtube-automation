import unittest

from scripts.quality_checks import analyze_script, sanitize_math_notation


class MathSanitizationTests(unittest.TestCase):
    def test_repairs_corrupted_derivative_and_arrow_macros(self):
        source = (
            "Derivative: \x0crac{dQ_d}{dP} < 0. "
            r"Price rises: $P \raisebox{0.5ex}{\tiny\textuparrow}$; "
            r"quantity falls: $Q_d \raisebox{0.5ex}{\tiny\textdownarrow}$."
        )
        cleaned, changes = sanitize_math_notation(source)
        self.assertIn("dQ_d/dP < 0", cleaned)
        self.assertIn("P ↑", cleaned)
        self.assertIn("Q_d ↓", cleaned)
        self.assertNotIn("\x0c", cleaned)
        self.assertGreaterEqual(len(changes), 2)

    def test_repairs_malformed_latex_prefix_control_characters(self):
        source = "x = \t" + "iny text and " + "\r" + "aisebox{0.5ex}{\t" + "iny\t" + "extuparrow}"
        cleaned, _ = sanitize_math_notation(source)
        self.assertIn("↑", cleaned)
        self.assertNotIn("\t" + "iny", cleaned)


class DeterministicGateTests(unittest.TestCase):
    def test_detects_mixed_devanagari_latin_typo(self):
        findings = analyze_script("अंतlying आर्थिक कारण", "Concept Explainer", "Bilingual")
        self.assertIn("MIXED_SCRIPT_TOKEN", {item["code"] for item in findings})

    def test_concept_explainer_requires_five_mcqs(self):
        source = """Learning Objectives
Definition and Concept
Examples
Recap
"""
        for number in range(1, 4):
            source += f"\n**Q{number}. Question?**\nCorrect Answer: A\nExplanation: Reason.\n"
        findings = analyze_script(source, "Concept Explainer", "English")
        self.assertIn("MCQ_COUNT_BELOW_MINIMUM", {item["code"] for item in findings})

    def test_detects_unresolved_verification_marker(self):
        findings = analyze_script("Economics [HUMAN VERIFY: source needed]", "Concept Explainer", "English")
        self.assertIn("UNRESOLVED_VERIFY_MARKER", {item["code"] for item in findings})

    def test_detects_corrupted_control_character(self):
        findings = analyze_script("bad \x0c token", "MCQ Set", "English")
        self.assertIn("CONTROL_CHARACTER", {item["code"] for item in findings})


if __name__ == "__main__":
    unittest.main()
