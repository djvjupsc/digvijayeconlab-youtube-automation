import unittest

from scripts.generate_script import apply_topic_specific_structure


class TopicSpecificStructureTests(unittest.TestCase):
    def test_unit_10_gets_learning_objectives_before_core_concept(self):
        source = "# Economic Growth in India\n\n## Core Concept\nGrowth means an increase in real GDP.\n"
        result = apply_topic_specific_structure("Economic Growth in India: Pattern and Structure", source)
        self.assertIn("## Learning Objectives / अधिगम उद्देश्य", result)
        self.assertLess(result.index("## Learning Objectives"), result.index("## Core Concept"))
        self.assertIn("रोजगार हिस्सेदारी", result)

    def test_unit_10_preserves_existing_learning_objectives(self):
        source = "# Topic\n\n## Learning Objectives\nAlready present.\n## Core Concept\n"
        result = apply_topic_specific_structure("Economic Growth in India: Pattern and Structure", source)
        self.assertEqual(result.count("## Learning Objectives"), 1)

    def test_unit_5_marks_unsupported_definition_and_adds_exact_syllabus_disclaimer(self):
        source = "# International Trade\n\n## Introduction\nInternational Economics studies the economic interactions between countries.\n"
        result = apply_topic_specific_structure("International Trade: Basic Concepts and Analytical Tools", source)
        self.assertIn("[VERIFY: add a standard textbook citation for the definition of International Economics]", result)
        self.assertIn("Independent verification of MPPSC syllabus alignment is still required.", result)

    def test_unit_5_does_not_duplicate_existing_disclaimer_or_marker(self):
        source = "# International Trade\n\n[VERIFY: add a standard textbook citation for the definition of International Economics]\nIndependent verification of MPPSC syllabus alignment is still required.\n"
        result = apply_topic_specific_structure("International Trade: Basic Concepts and Analytical Tools", source)
        self.assertEqual(result.count("Independent verification of MPPSC syllabus alignment is still required."), 1)
        self.assertEqual(result.count("[VERIFY: add a standard textbook citation for the definition of International Economics]"), 1)


if __name__ == "__main__":
    unittest.main()
