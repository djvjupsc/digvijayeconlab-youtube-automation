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


if __name__ == "__main__":
    unittest.main()
