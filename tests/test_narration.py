import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.narration import preview_speech_text, synthesize_audio_batch


class NarrationFallbackTests(unittest.TestCase):
    def make_items(self, root):
        return [
            {"text": "पहला हिंदी वाक्य।", "language": "hi", "path": str(Path(root) / "hi.wav"), "seed": 1, "speed": 142},
            {"text": "An English sentence.", "language": "en", "path": str(Path(root) / "en.wav"), "seed": 2, "speed": 152},
        ]

    def test_preview_text_removes_latex_control_syntax(self):
        cleaned = preview_speech_text(
            r"Correct Answer: B) $M3$ Explanation: $M3 = M1 + \\text{time deposits}$।"
        )
        self.assertIn("M3", cleaned)
        self.assertIn("time deposits", cleaned)
        self.assertNotIn("\\text", cleaned)
        self.assertNotIn("$", cleaned)

    def test_successful_chatterbox_batch_keeps_owner_voice(self):
        with tempfile.TemporaryDirectory() as root:
            items = self.make_items(root)
            calls = []

            def synth(text, language, path, seed):
                calls.append((language, seed))
                Path(path).write_bytes(b"chatterbox")

                return {"provider": "Chatterbox Multilingual V3"}

            with patch("scripts.narration.subprocess.run") as espeak:
                used, providers = synthesize_audio_batch(
                    items,
                    chatterbox_enabled=True,
                    allow_preview_fallback=True,
                    espeak_binary="espeak-ng",
                    chatterbox_synthesize=synth,
                )

            self.assertTrue(used)
            self.assertEqual(calls, [("hi", 1), ("en", 2)])
            self.assertEqual(providers, ["Chatterbox Multilingual V3"] * 2)
            espeak.assert_not_called()

    def test_quota_failure_restarts_all_items_with_preview_voice(self):
        with tempfile.TemporaryDirectory() as root:
            items = self.make_items(root)
            attempts = []

            def synth(text, language, path, seed):
                attempts.append(language)
                if len(attempts) == 1:
                    Path(path).write_bytes(b"partial-chatterbox")
                    return {"provider": "Chatterbox Multilingual V3"}
                raise RuntimeError("free ZeroGPU quota exhausted")

            def fake_run(command, **kwargs):
                self.assertEqual(command[-1], "--stdin")
                self.assertTrue(kwargs.get("input"))
                Path(command[-2]).write_bytes(b"espeak-preview")

            with patch("scripts.narration.subprocess.run", side_effect=fake_run) as espeak:
                used, providers = synthesize_audio_batch(
                    items,
                    chatterbox_enabled=True,
                    allow_preview_fallback=True,
                    espeak_binary="espeak-ng",
                    chatterbox_synthesize=synth,
                )

            self.assertFalse(used)
            self.assertEqual(attempts, ["hi", "en"])
            self.assertEqual(espeak.call_count, 2)
            self.assertEqual(providers, ["eSpeak NG (hi)", "eSpeak NG (en-us)"])
            self.assertEqual([Path(item["path"]).read_bytes() for item in items], [b"espeak-preview"] * 2)

    def test_failure_is_strict_when_preview_fallback_is_disabled(self):
        with tempfile.TemporaryDirectory() as root:
            items = self.make_items(root)

            def synth(*args, **kwargs):
                raise RuntimeError("quota exhausted")

            with patch("scripts.narration.subprocess.run") as espeak:
                with self.assertRaisesRegex(RuntimeError, "Preview fallback is disabled"):
                    synthesize_audio_batch(
                        items,
                        chatterbox_enabled=True,
                        allow_preview_fallback=False,
                        espeak_binary="espeak-ng",
                        chatterbox_synthesize=synth,
                    )
            espeak.assert_not_called()

    def test_eSpeak_mode_is_explicitly_non_chatterbox(self):
        with tempfile.TemporaryDirectory() as root:
            items = self.make_items(root)

            def fake_run(command, **kwargs):
                self.assertEqual(command[-1], "--stdin")
                self.assertTrue(kwargs.get("input"))
                Path(command[-2]).write_bytes(b"preview")

            with patch("scripts.narration.subprocess.run", side_effect=fake_run):
                used, providers = synthesize_audio_batch(
                    items,
                    chatterbox_enabled=False,
                    allow_preview_fallback=True,
                    espeak_binary="espeak-ng",
                )

            self.assertFalse(used)
            self.assertEqual(providers, ["eSpeak NG (hi)", "eSpeak NG (en-us)"])


if __name__ == "__main__":
    unittest.main()
