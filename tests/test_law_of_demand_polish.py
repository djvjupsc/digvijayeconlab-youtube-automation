import unittest

from scripts.law_of_demand_polish import apply_law_of_demand_polish


class LawOfDemandPolishTests(unittest.TestCase):
    def test_fixes_hindi_heading_and_giffen_plural_consistency(self):
        source = (
            "## 2. Assumptions (मांग का नियम की मान्यताएं)\n"
            "**गिफ्फेन वस्तुएं (Giffen Goods):** "
            "गिफ्फेन वस्तु एक ऐसी हीन वस्तु (inferior good) है जिसके लिए "
            "नकारात्मक आय प्रभाव, प्रतिस्थापन प्रभाव से अधिक मजबूत होता है, "
            "जिससे कीमत बढ़ने पर मांग भी बढ़ सकती है।"
        )
        result, changes = apply_law_of_demand_polish(source)
        self.assertIn("मांग के नियम की मान्यताएँ", result)
        self.assertIn("गिफ्फेन वस्तुएँ ऐसी हीन वस्तुएँ (inferior goods) हैं", result)
        self.assertNotIn("गिफ्फेन वस्तु एक ऐसी हीन वस्तु", result)
        self.assertEqual(len(changes), 2)

    def test_normalizes_nonstandard_full_stop(self):
        source = "मांग बढ़ जाती है。 कीमत कम होती है。"
        result, changes = apply_law_of_demand_polish(source)
        self.assertEqual(result, "मांग बढ़ जाती है। कीमत कम होती है।")
        self.assertEqual(len(changes), 1)

    def test_fails_closed_if_a_known_defect_remains(self):
        # A deliberately different singular phrasing is not silently certified.
        source = "गिफ्फेन वस्तु एक ऐसी हीन वस्तु का उदाहरण।"
        with self.assertRaisesRegex(ValueError, "singular Giffen definition"):
            apply_law_of_demand_polish(source)

    def test_is_idempotent(self):
        source = (
            "मांग का नियम की मान्यताएं。 "
            "गिफ्फेन वस्तु एक ऐसी हीन वस्तु (inferior good) है जिसके लिए "
            "नकारात्मक आय प्रभाव, प्रतिस्थापन प्रभाव से अधिक मजबूत होता है, "
            "जिससे कीमत बढ़ने पर मांग भी बढ़ सकती है。"
        )
        once, _ = apply_law_of_demand_polish(source)
        twice, changes = apply_law_of_demand_polish(once)
        self.assertEqual(twice, once)
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()
