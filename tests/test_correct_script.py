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

    def test_rbi_source_repairs_correct_bilingual_committee_attributions_and_aggregates(self):
        source = (
            "The Reserve Bank of India (RBI) historically published four alternative measures "
            "of money supply ($M_1, M_2, M_3,$ and $M_4$), based on the recommendations of the "
            "Working Group on Money Supply (1977) [VERIFY]. These aggregates represent varying "
            "degrees of liquidity, ranging from most liquid to least liquid.\n"
            "भारतीय रिजर्व बैंक (RBI) ने ऐतिहासिक रूप से मुद्रा आपूर्ति के चार वैकल्पिक माप "
            "($M_1, M_2, M_3,$ और $M_4$) प्रकाशित किए हैं, जो मुद्रा आपूर्ति पर कार्य समूह (1977) "
            "की सिफारिशों पर आधारित हैं [सत्यापन योग्य]। ये समुच्चय तरलता के विभिन्न स्तरों को "
            "दर्शाते हैं, जो अत्यधिक तरल से लेकर कम तरल तक होते हैं।\n"
            "* RBI monetary surveys also include newer monetary aggregates ($NM_1, NM_2, NM_3$) "
            "based on modern liquidity concepts [VERIFY].\n"
            "* आरबीआई के मौद्रिक सर्वेक्षणों में आधुनिक तरलता अवधारणाओं के आधार पर नए मौद्रिक "
            "समुच्चय ($NM_1, NM_2, NM_3$) भी शामिल हैं [सत्यापन योग्य]।\n"
            "M3 = M1 + Net Time Deposits with commercial and cooperative banks.\n"
            "M3 में शुद्ध सावधि जमा शामिल है।"
        )
        repaired, changes = apply_known_editorial_repairs(source)
        self.assertIn("Second Working Group on Money Supply (SWG), chaired by M. L. Ghosh, in 1977", repaired)
        self.assertIn("द्वितीय कार्य समूह (Second Working Group, SWG; अध्यक्ष एम. एल. घोष) की 1977", repaired)
        self.assertIn("WGMS), chaired by Dr. Y. V. Reddy, in June 1998", repaired)
        self.assertNotIn("[VERIFY]", repaired)
        self.assertNotIn("[सत्यापन योग्य]", repaired)
        self.assertNotIn("modern liquidity concepts", repaired)
        self.assertNotIn("Net Time Deposits", repaired)
        self.assertNotIn("शुद्ध सावधि जमा", repaired)
        self.assertGreaterEqual(len(changes), 6)

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


    def test_repairs_unit_2_answer_label_and_income_method_hindi_grammar(self):
        source = "\n".join([
            "सही उत्तर: B। स्पष्टीकरण: कारण।",
            "कर्मचारियों की पारिश्रमिक",
        ])
        repaired, changes = apply_known_editorial_repairs(source)
        self.assertIn("सही उत्तर: B) स्पष्टीकरण:", repaired)
        self.assertIn("कर्मचारियों का पारिश्रमिक", repaired)
        self.assertNotIn("सही उत्तर: B।", repaired)
        self.assertEqual(len(changes), 2)

    def test_repairs_unit_10_unsupported_sector_share_and_bilingual_headings(self):
        source = "\n".join([
            "## Learning Objectives / अधि-अगम्य उद्देश्य",
            "The secondary sector, though its share in total GDP has hovered around 25-30% [VERIFY].",
            "हालांकि कुल GDP में इसका हिस्सा लगभग 25-30% के आसपास रहा है [VERIFY]।",
            "## Worked Example / Application (Hypothetical Sectoral Contribution Analysis)",
            "## कार्यशील उदाहरण / अनुप्रयोग (काल्पनिक क्षेत्रीय योगदान विश्लेषण)",
        ])
        repaired, changes = apply_known_editorial_repairs(source)
        self.assertNotIn("25-30%", repaired)
        self.assertIn("assessed separately for manufacturing, construction and utilities", repaired)
        self.assertIn("विनिर्माण, निर्माण और उपयोगिताओं के योगदान का अलग-अलग अध्ययन", repaired)
        self.assertIn("Learning Objectives / अधिगम उद्देश्य", repaired)
        self.assertIn(
            "## Worked Example / Application: Hypothetical Sectoral Contribution Analysis / कार्यशील उदाहरण:",
            repaired,
        )
        self.assertNotIn("अधि-अगम्य", repaired)
        self.assertEqual(len(changes), 4)


    def test_repairs_opportunity_cost_bilingual_parity_cost_types_and_source_claim(self):
        source = "\\n".join([
            "(एक वस्तु के अधिक उत्पादन की अवसर लागत दूसरी वस्तु की छोड़ी जाने वाली मात्रा से मापी जाती है।)",
            "असीमित मानवीय आवश्यकताओं और संसाधनों की दुर्लता के कारण चयन करना पड़ता है।",
            "If an individual leaves a job paying ₹50,000 per year to start a business, and incurs no other explicit costs besides buying ₹20,000 worth of supplies, what is the implicit cost of starting the business? [VERIFY]",
            "The implicit cost is the forgone salary from the previous job (₹50,000) because it represents the value of the resource supplied by the owner without an explicit cash transaction. (Note: Specific numerical values are illustrative).",
            "निहित लागत पिछली नौकरी से छोड़ा गया वेतन (₹50,000) है क्योंकि यह बिना किसी स्पष्ट नकद लेनदेन के मालिक द्वारा आपूर्ति किए गए संसाधन के मूल्य का प्रतिनिधित्व करता है।",
            "**Verification Status:** Standard economic principles verified against general curriculum guidelines for MPPSC Assistant Professor Economics. Numerical illustrations are marked [VERIFY] where specific parameter values are assumed for problem-solving practice.",
        ])
        repaired, changes = apply_known_editorial_repairs(source)
        self.assertIn("अवतल PPF बढ़ती अवसर लागत को दर्शाता है।", repaired)
        self.assertIn("असीमित मानवीय इच्छाओं", repaired)
        self.assertIn("संसाधनों की दुर्लभता", repaired)
        self.assertIn("forgone salary is the only implicit cost", repaired)
        self.assertIn("supplies are an explicit cost", repaired)
        self.assertIn("The ₹20,000 spent on supplies is an explicit cost", repaired)
        self.assertIn("combined economic cost is ₹70,000", repaired)
        self.assertIn("आपूर्ति सामग्री पर किया गया खर्च स्पष्ट लागत है", repaired)
        self.assertIn("संयुक्त आर्थिक लागत ₹70,000 होगी", repaired)
        self.assertIn("has not been independently checked against the latest official MPPSC", repaired)
        self.assertNotIn("verified against general curriculum guidelines", repaired)
        self.assertGreaterEqual(len(changes), 5)



if __name__ == "__main__":
    unittest.main()
