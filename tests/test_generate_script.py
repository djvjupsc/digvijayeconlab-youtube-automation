import unittest

from scripts.generate_script import topic_specific_requirements


class TopicSpecificGenerationRequirementsTests(unittest.TestCase):
    def test_consumer_behavior_instructions_restrict_perfect_information_and_giffen_claims(self):
        guidance = topic_specific_requirements("Theory of Consumer Behaviour")
        self.assertIn("not a universal assumption", guidance)
        self.assertIn("Giffen good must be inferior", guidance)
        self.assertIn("Marshall", guidance)

    def test_ricardian_trade_instructions_keep_consumer_theory_separate(self):
        guidance = topic_specific_requirements("International Trade: Basic Concepts and Analytical Tools")
        self.assertIn("production-side", guidance)
        self.assertIn("Do not connect the Ricardian model to Hicks/Slutsky", guidance)
        self.assertIn("linear PPF", guidance)

    def test_market_failure_instructions_cover_public_goods_information_and_externalities(self):
        guidance = topic_specific_requirements("Market Failure and Remedial Measures: Asymmetric Information, Public Goods and Externality")
        self.assertIn("non-excludability and non-rivalry", guidance)
        self.assertIn("adverse selection", guidance)
        self.assertIn("MPC from MSC", guidance)

    def test_money_supply_instructions_require_numeric_bilingual_calculation(self):
        guidance = topic_specific_requirements("Components of Money Supply")
        self.assertIn("M1=₹810 crore", guidance)
        self.assertIn("M4=₹1,545 crore", guidance)
        self.assertIn("काल्पनिक", guidance)

    def test_indian_growth_instructions_preserve_period_and_measure(self):
        guidance = topic_specific_requirements("Economic Growth in India: Pattern and Structure")
        self.assertIn("53.6%", guidance)
        self.assertIn("nominal GDP", guidance)
        self.assertIn("2022–23", guidance)
        self.assertIn("GVA", guidance)

    def test_unrelated_topic_has_no_specialized_requirements(self):
        self.assertEqual(topic_specific_requirements("National Income: Concepts and Measurement"), "")

class TopicSpecificStructureTests(unittest.TestCase):
    def test_unit_10_gets_learning_objectives_before_core_concept(self):
        from scripts.generate_script import apply_topic_specific_structure
        source = "# Economic Growth in India\n\n## Core Concept\nGrowth means an increase in real GDP.\n"
        result = apply_topic_specific_structure("Economic Growth in India: Pattern and Structure", source)
        self.assertIn("## Learning Objectives / अधिगम उद्देश्य", result)
        self.assertLess(result.index("## Learning Objectives"), result.index("## Core Concept"))
        self.assertIn("रोजगार हिस्सेदारी", result)

    def test_unit_10_preserves_existing_learning_objectives(self):
        from scripts.generate_script import apply_topic_specific_structure
        source = "# Topic\n\n## Learning Objectives\nAlready present.\n## Core Concept\n"
        result = apply_topic_specific_structure("Economic Growth in India: Pattern and Structure", source)
        self.assertEqual(result.count("## Learning Objectives"), 1)

    def test_unit_5_marks_unsupported_definition_and_adds_exact_syllabus_disclaimer(self):
        from scripts.generate_script import apply_topic_specific_structure
        source = "# International Trade\n\n## Introduction\nInternational Economics studies the economic interactions between countries.\n"
        result = apply_topic_specific_structure("International Trade: Basic Concepts and Analytical Tools", source)
        self.assertIn("[VERIFY: add a standard textbook citation for the definition of International Economics]", result)
        self.assertIn("Independent verification of MPPSC syllabus alignment is still required.", result)

    def test_unit_5_does_not_duplicate_existing_disclaimer_or_marker(self):
        from scripts.generate_script import apply_topic_specific_structure
        source = "# International Trade\n\n[VERIFY: add a standard textbook citation for the definition of International Economics]\nIndependent verification of MPPSC syllabus alignment is still required.\n"
        result = apply_topic_specific_structure("International Trade: Basic Concepts and Analytical Tools", source)
        self.assertEqual(result.count("Independent verification of MPPSC syllabus alignment is still required."), 1)
        self.assertEqual(result.count("[VERIFY: add a standard textbook citation for the definition of International Economics]"), 1)


if __name__ == "__main__":
    unittest.main()
