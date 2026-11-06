import json
import unittest

from scripts.correct_script import (
    apply_known_editorial_repairs,
    apply_topic_specific_repairs,
    parse_structured_response,
    preserve_original_verification_markers,
)


class StructuredCorrectionTests(unittest.TestCase):
    def test_consumer_topic_repairs_remove_unverified_marshall_attribution_and_universal_information_assumption(self):
        source = (
            "3.  **Perfect Information:** Consumers are assumed to have full knowledge of prices and product quality in standard neoclassical models. (पूर्ण जानकारी: मानक नव-शास्त्रीय मॉडलों में यह माना जाता है कि उपभोक्ताओं को कीमतों और उत्पाद की गुणवत्ता की पूर्ण जानकारी होती है।)\\n"
            "Alfred Marshall discussed these in his *Principles of Economics* (1895).\\n"
            "अल्फ्रेड मार्शल ने अपनी पुस्तक *प्रिंसिपल्स ऑफ इकोनॉमिक्स* (1895) में इनकी चर्चा की थी।"
        )
        repaired, changes = apply_topic_specific_repairs(source, "Theory of Consumer Behaviour")
        self.assertIn("not a universal assumption of the law of demand", repaired)
        self.assertNotIn("Alfred Marshall discussed", repaired)
        self.assertNotIn("अल्फ्रेड मार्शल ने", repaired)
        self.assertIn("historically contested", repaired)
        self.assertGreaterEqual(len(changes), 3)

    def test_trade_topic_repairs_do_not_apply_hicks_slutsky_to_ricardian_trade(self):
        source = (
            "This framework relies on the standard neoclassical Hicks/Slutsky approach for analyzing individual demand decomposition, though it does not explain demand entirely across all theoretical approaches.\\n"
            "यह ढांचा व्यक्तिगत मांग अपघटन के विश्लेषण के लिए मानक नवशास्त्रीय हिक्स/स्लुट्स्की दृष्टिकोण पर निर्भर करता है, हालाँकि यह सभी सैद्धांतिक दृष्टिकोणों में मांग की पूरी व्याख्या नहीं करता है।\\n"
            "A concave PPF reflects increasing opportunity costs.\\n"
            "एक अवतल (Concave) PPF बढ़ती अवसर लागत को दर्शाता है।"
        )
        repaired, changes = apply_topic_specific_repairs(source, "International Trade: Basic Concepts and Analytical Tools")
        self.assertNotIn("Hicks/Slutsky", repaired)
        self.assertNotIn("हिक्स/स्लुट्स्की", repaired)
        self.assertIn("production-side explanation", repaired)
        self.assertIn("simplest Ricardian model", repaired)
        self.assertIn("सरल रिकार्डियन मॉडल", repaired)
        self.assertGreaterEqual(len(changes), 4)

    def test_money_supply_topic_gets_bilingual_hypothetical_worked_example(self):
        repaired, changes = apply_topic_specific_repairs(
            "## Components Schedule\\nM1 to M4 definitions.",
            "Components of Money Supply",
        )
        self.assertIn("## Worked Example / Application", repaired)
        self.assertIn("M1 = 500 + 300 + 10 = **₹810 crore**", repaired)
        self.assertIn("M4 = M3 + 35 = **₹1,545 crore**", repaired)
        self.assertIn("ये केवल शिक्षण हेतु बनाई गई काल्पनिक संख्याएँ हैं", repaired)
        self.assertIn("सावधि जमा", repaired)
        self.assertEqual(len(changes), 1)

    def test_indian_growth_replaces_undated_illustrative_table_with_dated_source_data(self):
        source = """## Worked Example: Sectoral Shift / कार्य उदाहरण: क्षेत्रीय बदलाव
*Note: The following values are illustrative of structural trends in the Indian economy.*
| Sector / क्षेत्र | GVA Share (Approx. Historical) / GVA हिस्सा (लगभग ऐतिहासिक) |
| :--- | :--- |
| Agriculture / कृषि | ~18% |
| Industry / उद्योग | ~28% |
| Services / सेवाएँ | ~54% |

## Recap
Some text.
"""
        repaired, changes = apply_topic_specific_repairs(
            source, "Economic Growth in India: Pattern and Structure"
        )
        self.assertNotIn("Approx. Historical", repaired)
        self.assertIn("53.6%", repaired)
        self.assertIn("nominal GDP", repaired)
        self.assertIn("H1 FY2025–26", repaired)
        self.assertIn("GVA growth of 7.0%", repaired)
        self.assertIn("आधार वर्ष 2022–23", repaired)
        self.assertGreaterEqual(len(changes), 1)

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
        source = "\n".join([
            "(एक वस्तु के अधिक उत्पादन की अवसर लागत दूसरी वस्तु की छोड़ी जाने वाली मात्रा से मापी जाती है।)",
            "असीमित मानवीय आवश्यकताओं और संसाधनों की दुर्लता के कारण चयन करना पड़ता है।",
            "If an individual leaves a job paying ₹50,000 per year to start a business, and incurs no other explicit costs besides buying ₹20,000 worth of supplies, what is the implicit cost of starting the business? [VERIFY]",
            "The implicit cost is the forgone salary from the previous job (₹50,000) because it represents the value of the resource supplied by the owner without an explicit cash transaction. (Note: Specific numerical values are illustrative).",
            "निहित लागत पिछली नौकरी से छोड़ा गया वेतन (₹50,000) है क्योंकि यह बिना किसी स्पष्ट नकद लेनदेन के मालिक द्वारा आपूर्ति किए गए संसाधन के मूल्य का प्रतिनिधित्व करता है।",
            "**Verification Status:** Standard economic principles verified against general curriculum guidelines for MPPSC Assistant Professor Economics. Numerical illustrations are marked [VERIFY] where specific parameter values are assumed for problem-solving practice.",
        ])
        repaired, changes = apply_known_editorial_repairs(source)
        self.assertIn("नतोदर PPF संसाधनों की अपूर्ण प्रतिस्थाप्यता", repaired)
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



    def test_repairs_opportunity_cost_q10_bilingual_labels_and_forgone_translation(self):
        source = "\n".join([
            "**Explanation (Hindi/English):** ",
            "- **English:** A point inside the PPF indicates that the economy is producing less than its maximum potential due to unemployment or resource misallocation.",
            "- **Hindi:** PPF के अंदर एक बिंदु इंगित करता है कि बेरोजगारी या संसाधन दुर्विनियोजन के कारण अर्थव्यवस्था अपनी अधिकतम क्षमता से कम उत्पादन कर रही है।",
            "भूला हुआ वेतन और भूला हुआ ब्याज",
            "निरंतर अवसर लागत",
        ])
        repaired, changes = apply_known_editorial_repairs(source)
        self.assertIn("**Explanation (English):**", repaired)
        self.assertIn("**Explanation (Hindi):**", repaired)
        self.assertIn("कुछ संसाधन बेरोजगार हैं", repaired)
        self.assertIn("त्यागा गया वेतन", repaired)
        self.assertIn("त्यागा गया ब्याज", repaired)
        self.assertIn("स्थिर अवसर लागत", repaired)
        self.assertNotIn("Hindi/English", repaired)
        self.assertNotIn("भूला हुआ", repaired)
        self.assertGreaterEqual(len(changes), 4)


if __name__ == "__main__":
    unittest.main()
