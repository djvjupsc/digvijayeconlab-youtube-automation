import tempfile
import unittest
from pathlib import Path

from scripts.source_notes import load_optional_source_notes


class OptionalSourceNotesTests(unittest.TestCase):
    def test_missing_argument_means_no_source_notes(self):
        self.assertEqual(load_optional_source_notes(None), "")

    def test_empty_argument_means_no_source_notes(self):
        self.assertEqual(load_optional_source_notes(""), "")

    def test_whitespace_argument_means_no_source_notes(self):
        self.assertEqual(load_optional_source_notes("   \t"), "")

    def test_reads_existing_source_notes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "references.md"
            path.write_text("Authoritative source notes.", encoding="utf-8")
            self.assertEqual(load_optional_source_notes(str(path)), "Authoritative source notes.")

    def test_nonempty_missing_path_fails_clearly(self):
        with self.assertRaisesRegex(SystemExit, "Source notes file not found: missing-notes.md"):
            load_optional_source_notes("missing-notes.md")


if __name__ == "__main__":
    unittest.main()
