import unittest

from scripts.finalize_script import normalize_script


class LawOfDemandEditorialNormalizationTests(unittest.TestCase):
    def test_fixes_assumptions_heading_hindi_grammar(self):
        text = "## 2. Assumptions (मांग का नियम की मान्यताएं)"
        normalized, changes = normalize_script(text)
        self.assertIn("मांग के नियम की मान्यताएं", normalized)
        self.assertEqual(len(changes), 1)

    def test_makes_giffen_heading_and_definition_plural_consistent(self):
        text = (
            "गिफ्फेन वस्तुएं (Giffen Goods): "
            "गिफ्फेन वस्तु एक ऐसी हीन वस्तु (inferior good) है जिसके लिए "
            "नकारात्मक आय प्रभाव अधिक मजबूत होता है।"
        )
        normalized, changes = normalize_script(text)
        self.assertIn(
            "गिफ्फेन वस्तुएं (Giffen Goods): गिफ्फेन वस्तुएं ऐसी हीन वस्तुएं (inferior goods) हैं जिनके लिए",
            normalized,
        )
        self.assertEqual(len(changes), 1)

    def test_standardizes_ideographic_full_stops(self):
        text = "मांग बढ़ जाती है。 यह विपरीत संबंध है。"
        normalized, changes = normalize_script(text)
        self.assertEqual(normalized, "मांग बढ़ जाती है। यह विपरीत संबंध है।")
        self.assertIn("2 non-standard", changes[0])

    def test_is_idempotent_and_does_not_change_unrelated_text(self):
        text = "The Law of Demand. मांग का नियम।"
        once, _ = normalize_script(text)
        twice, changes = normalize_script(once)
        self.assertEqual(once, twice)
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()
