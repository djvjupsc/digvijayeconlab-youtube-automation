import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from scripts.chatterbox_tts import _join_wav_parts, _write_audio_result, split_text


class ChatterboxTextChunkTests(unittest.TestCase):
    def test_keeps_short_text_as_one_chunk(self):
        self.assertEqual(split_text("नमस्कार। Welcome!"), ["नमस्कार। Welcome!"])

    def test_chunks_at_sentence_and_word_boundaries(self):
        text = ("अर्थशास्त्र का अध्ययन महत्वपूर्ण है। " * 12).strip()
        chunks = split_text(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 300 for chunk in chunks))
        self.assertEqual(" ".join(chunks).replace("  ", " "), text)

    def test_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            split_text("   ")

    def test_long_unbroken_token_is_split_without_exceeding_limit(self):
        chunks = split_text("x" * 650)
        self.assertEqual([300, 300, 50], [len(chunk) for chunk in chunks])


class ChatterboxAudioTests(unittest.TestCase):
    def test_writes_array_result_and_joins_parts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.wav"
            second = root / "second.wav"
            output = root / "joined.wav"
            samples = np.linspace(-0.5, 0.5, 2400, dtype=np.float32)
            _write_audio_result((24000, samples), first)
            _write_audio_result((24000, samples), second)
            _join_wav_parts([first, second], output)
            with wave.open(str(output), "rb") as wav:
                self.assertEqual(wav.getframerate(), 24000)
                self.assertEqual(wav.getnchannels(), 1)
                self.assertGreater(wav.getnframes(), 4800)


if __name__ == "__main__":
    unittest.main()
