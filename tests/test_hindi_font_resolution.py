import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.render_thumbnails import find_hindi_font


class HindiFontResolutionTests(unittest.TestCase):
    @patch("scripts.render_thumbnails.subprocess.run")
    def test_rejects_latin_only_fontconfig_fallback(self, run):
        with tempfile.NamedTemporaryFile() as font:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=f"DejaVu Sans\n{font.name}", stderr=""
            )
            with self.assertRaisesRegex(RuntimeError, "Noto Sans Devanagari"):
                find_hindi_font()

    @patch("scripts.render_thumbnails.subprocess.run")
    def test_accepts_actual_devanagari_font(self, run):
        with tempfile.NamedTemporaryFile() as font:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=f"Noto Sans Devanagari\n{font.name}", stderr=""
            )
            self.assertEqual(find_hindi_font(), font.name)


if __name__ == "__main__":
    unittest.main()
