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

    def test_repairs_backspace_and_tab_corrupted_latex_commands(self):
        source = (
            "Union $A \x08igcup B$, intersection $A \x08igcap B$, "
            "and label $\t ext{Savings deposits}$."
        )
        cleaned, changes = sanitize_math_notation(source)
        self.assertIn(r"$A \bigcup B$", cleaned)
        self.assertIn(r"$A \bigcap B$", cleaned)
        self.assertIn(r"$\text{Savings deposits}$", cleaned)
        self.assertFalse(any(ord(ch) < 32 and ch not in "\n\r\t" for ch in cleaned))
        self.assertGreaterEqual(len(changes), 3)


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


    def test_accepts_bold_markdown_answer_and_explanation_labels(self):
        source = "Learning Objectives\nDefinition and Concept\nExamples\nRecap\n"
        for number in range(1, 6):
            source += (
                f"\n**Q{number}. Question?**\n"
                "* **Correct Answer:** A\n"
                "* **Explanation:** This is the rationale.\n"
            )
        findings = analyze_script(source, "Concept Explainer", "English")
        codes = {item["code"] for item in findings}
        self.assertNotIn("MCQ_ANSWER_GAP", codes)
        self.assertNotIn("MCQ_EXPLANATION_GAP", codes)
        self.assertNotIn("MCQ_COUNT_BELOW_MINIMUM", codes)


    def test_requires_dedicated_populated_example_or_schedule_heading(self):
        source = """Learning Objectives
Definition and Concept
Examples are discussed below in the general explanation.
Recap
The lesson includes an example and an application in its general text.
"""
        findings = analyze_script(source, "Concept Explainer", "English")
        self.assertIn(
            "WORKED_EXAMPLE_OR_DEMAND_SCHEDULE_MISSING",
            {item["code"] for item in findings}
        )

    def test_accepts_populated_worked_example_section(self):
        source = """## Learning Objectives
Understand demand.
## Definition
Demand is the relationship between price and quantity demanded.
## Worked Example / Application
Assume an illustrative market. When price falls from 10 to 8 currency units,
quantity demanded rises from 20 to 25 units, other factors remaining constant.
This hypothetical example demonstrates the inverse price-quantity relationship.
## Recap
Demand curves slope downward.
"""
        findings = analyze_script(source, "Concept Explainer", "English")
        self.assertNotIn(
            "WORKED_EXAMPLE_OR_DEMAND_SCHEDULE_MISSING",
            {item["code"] for item in findings}
        )

    def test_accepts_demand_schedule_with_nested_bilingual_subheadings(self):
        source = """## Learning Objectives
Understand demand.
## Definition
Demand is the relationship between price and quantity demanded.
## 4. Demand Schedule and Mathematical Derivation
### English
A demand schedule shows the inverse relationship between price and quantity demanded.
The function Qd = 40 - 2P gives the following hypothetical schedule.
### Hindi
मांग अनुसूची कीमत और मांग की मात्रा के बीच विपरीत संबंध दिखाती है।
| Price | Quantity |
|---:|---:|
| 10 | 20 |
| 20 | 15 |
| 30 | 10 |
| 40 | 5 |
## Recap
A lower price is associated with greater quantity demanded, other things equal.
"""
        findings = analyze_script(source, "Concept Explainer", "Bilingual")
        self.assertNotIn(
            "WORKED_EXAMPLE_OR_DEMAND_SCHEDULE_MISSING",
            {item["code"] for item in findings}
        )

    def test_accepts_populated_demand_schedule_table(self):
        source = """## Learning Objectives
Understand demand.
## Definition
Demand describes willingness and ability to buy.
## Demand Schedule
| Price (₹) | Quantity demanded (units) |
|---:|---:|
| 10 | 20 |
| 8 | 25 |
| 6 | 30 |
## Recap
A lower price is associated with greater quantity demanded, other things equal.
"""
        findings = analyze_script(source, "Concept Explainer", "English")
        self.assertNotIn(
            "WORKED_EXAMPLE_OR_DEMAND_SCHEDULE_MISSING",
            {item["code"] for item in findings}
        )


    def test_counts_mcqs_with_markdown_heading_prefixes(self):
        source = """## Learning Objectives
Understand demand.
## Definition
Demand is the relationship between price and quantity demanded.
## Worked Example / Application
Assume a hypothetical market. Price falls from 10 to 8, while quantity rises from 20 to 25 units.
## Recap
Price and quantity demanded are inversely related, other things equal.
"""
        for number in range(1, 6):
            source += (
                f"\n### Q{number}. Question?\n"
                "A) Option A\nB) Option B\nC) Option C\nD) Option D\n"
                "* **Correct Answer:** B\n"
                "* **Explanation:** This is the explanation.\n"
            )
        findings = analyze_script(source, "Concept Explainer", "English")
        codes = {item["code"] for item in findings}
        self.assertNotIn("MCQ_COUNT_BELOW_MINIMUM", codes)
        self.assertNotIn("MCQ_ANSWER_GAP", codes)
        self.assertNotIn("MCQ_EXPLANATION_GAP", codes)


    def test_counts_answer_label_without_correct_prefix(self):
        from scripts.quality_checks import count_mcq_sections
        source = """### Q1. Question
A) Option A
B) Option B
*Answer:* **B**
*Explanation:* This is the rationale.
"""
        self.assertEqual(count_mcq_sections(source), (1, 1, 1))

    def test_bilingual_english_hindi_headings_for_same_question_count_once(self):
        from scripts.quality_checks import count_mcq_sections
        source = """### Q1. English question
### Q1. हिंदी प्रश्न
A) Option A
B) Option B
* **Correct Answer / सही उत्तर:** A
* **Explanation / व्याख्या:** Both versions refer to one MCQ.
### Q2. English question
### Q2. हिंदी प्रश्न
A) Option A
B) Option B
* **Correct Answer / सही उत्तर:** B
* **Explanation / व्याख्या:** Both versions refer to one MCQ.
"""
        self.assertEqual(count_mcq_sections(source), (2, 2, 2))

    def test_hindi_verification_marker_is_detected(self):
        findings = analyze_script(
            "दावा [सत्यापन योग्य]",
            "MCQ Set",
            "Hindi",
        )
        marker = next(item for item in findings if item["code"] == "UNRESOLVED_VERIFY_MARKER")
        self.assertFalse(marker["blocking"])

    def test_verification_markers_are_reported_but_do_not_block_human_review(self):
        findings = analyze_script(
            "A historical claim [VERIFY: check source].",
            "MCQ Set",
            "English",
        )
        marker = next(item for item in findings if item["code"] == "UNRESOLVED_VERIFY_MARKER")
        self.assertEqual(marker["severity"], "High")
        self.assertFalse(marker["blocking"])

    def test_counts_actual_generated_mcq_heading_and_bilingual_labels(self):
        source = """## Learning Objectives
Understand the law of demand.
## Definition
The law describes an inverse price-quantity demanded relationship.
## Worked Example / Application
Assume a hypothetical market. Price falls from ₹10 to ₹8, while quantity demanded rises from 20 to 25 units.
## Recap
Price and quantity demanded move in opposite directions, other things equal.
"""
        for number in range(1, 6):
            source += chr(10).join([
                f"### MCQ {number}",
                "A) Option A",
                "B) Option B",
                "C) Option C",
                "D) Option D",
                "* **Correct Answer / सही उत्तर:** B",
                "* **Explanation (English):** The English rationale.",
                "* **Explanation (Hindi):** हिंदी में व्याख्या।",
            ]) + chr(10)
        from scripts.quality_checks import count_mcq_sections
        self.assertEqual(count_mcq_sections(source), (5, 5, 5))
        findings = analyze_script(source, "Concept Explainer", "English")
        codes = {item["code"] for item in findings}
        self.assertNotIn("MCQ_COUNT_BELOW_MINIMUM", codes)
        self.assertNotIn("MCQ_ANSWER_GAP", codes)
        self.assertNotIn("MCQ_EXPLANATION_GAP", codes)

if __name__ == "__main__":
    unittest.main()
