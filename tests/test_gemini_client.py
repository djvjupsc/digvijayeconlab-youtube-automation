import io
import json
import unittest
from unittest.mock import patch

from scripts import gemini_client


class GeminiClientRetryTests(unittest.TestCase):
    @patch("scripts.gemini_client.time.sleep")
    @patch("scripts.gemini_client.urllib.request.urlopen")
    def test_retries_temporary_503_then_succeeds(self, urlopen, sleep):
        success = io.BytesIO(json.dumps({"ok": True}).encode("utf-8"))
        temporary = gemini_client.urllib.error.HTTPError(
            "https://example.invalid", 503, "busy", {}, io.BytesIO(b"temporary")
        )
        urlopen.side_effect = [temporary, success]
        result = gemini_client.generate_content(
            "https://example.invalid", "not-a-real-key", {"hello": "world"}
        )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()

    @patch("scripts.gemini_client.time.sleep")
    @patch("scripts.gemini_client.urllib.request.urlopen")
    def test_does_not_retry_permanent_400(self, urlopen, sleep):
        error = gemini_client.urllib.error.HTTPError(
            "https://example.invalid", 400, "bad request", {}, io.BytesIO(b"bad request")
        )
        urlopen.side_effect = error
        with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
            gemini_client.generate_content(
                "https://example.invalid", "not-a-real-key", {"hello": "world"}
            )
        self.assertEqual(urlopen.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
