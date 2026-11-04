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

if __name__ == "__main__":
    unittest.main()
