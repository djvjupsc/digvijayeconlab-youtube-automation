import unittest
from scripts.verify_giffen_sources import verify_and_clear


class GiffenSourceVerificationTests(unittest.TestCase):
    def test_clears_only_provenance_markers_after_caveat_checks(self):
        source = """### A. Giffen Goods
Historical attribution to Robert Giffen is debated and not established. The traditional Irish potato example is debated.
ऐतिहासिक नोट: अल्फ्रेड मार्शल के उदाहरण पर विद्वानों में बहस है।
### B. Veblen Goods
Status-signalling luxury goods.
## Original Verification Markers Retained for Human Sign-off
- [VERIFY]
- [VERIFY]
"""
        cleaned, count = verify_and_clear(source)
        self.assertEqual(count, 2)
        self.assertNotIn("[VERIFY]", cleaned)
        self.assertNotIn("Original Verification Markers Retained", cleaned)

    def test_accepts_bold_bullet_labels_and_no_marker_appendix(self):
        source = """## 5. Exceptions to the Law of Demand
* **Giffen Goods:** Historical Note: Alfred Marshall's example attributed to Robert Giffen is debated. We do not state as settled fact that the traditional Irish potato example was empirically proven.
ऐतिहासिक नोट: अल्फ्रेड मार्शल की चर्चा के ऐतिहासिक श्रेय को लेकर विद्वानों में बहस है।
* **Veblen / Status Goods:** Status signalling and conspicuous consumption.
"""
        cleaned, count = verify_and_clear(source)
        self.assertEqual(count, 0)
        self.assertEqual(cleaned, source.rstrip() + "\n")

    def test_rejects_marker_inside_lesson_body(self):
        source = """### A. Giffen Goods
Historical attribution is debated and not established; Irish potato example.
ऐतिहासिक नोट: अल्फ्रेड मार्शल के उदाहरण पर बहस है। [VERIFY]
### B. Veblen Goods
## Original Verification Markers Retained for Human Sign-off
- [VERIFY]
"""
        with self.assertRaisesRegex(ValueError, "inside lesson content"):
            verify_and_clear(source)

    def test_rejects_marker_without_provenance_appendix(self):
        source = """### Giffen Goods
Historical attribution is debated and not established; Irish potato example.
ऐतिहासिक नोट: अल्फ्रेड मार्शल के उदाहरण पर बहस है। [VERIFY]
### Veblen Goods
"""
        with self.assertRaisesRegex(ValueError, "no provenance appendix"):
            verify_and_clear(source)

    def test_rejects_missing_giffen_section(self):
        source = """### A. Marshallian Demand
A discussion without the Giffen exception.
### B. Veblen Goods
## Original Verification Markers Retained for Human Sign-off
- [VERIFY]
"""
        with self.assertRaisesRegex(ValueError, "isolate the Giffen-goods section"):
            verify_and_clear(source)

    def test_rejects_missing_historical_caveat(self):
        source = """### A. Giffen Goods
Historical Note: Alfred Marshall described the Irish potato example as proven.
ऐतिहासिक नोट: अल्फ्रेड मार्शल ने उदाहरण दिया।
### B. Veblen Goods
## Original Verification Markers Retained for Human Sign-off
- [VERIFY]
"""
        with self.assertRaisesRegex(ValueError, "cautious wording"):
            verify_and_clear(source)


if __name__ == "__main__":
    unittest.main()
