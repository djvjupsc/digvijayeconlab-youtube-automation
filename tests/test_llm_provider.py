import io
import json
import os
import unittest
from unittest.mock import patch

from scripts import llm_provider


class FreeLLMAPIAdapterTests(unittest.TestCase):
    def test_maps_gemini_payload_to_openai_chat_format(self):
        payload = {
            "systemInstruction": {"parts": [{"text": "Be accurate."}]},
            "contents": [{"role": "user", "parts": [{"text": "Define opportunity cost."}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512},
        }
        mapped = llm_provider._to_openai_payload(payload)
        self.assertEqual(mapped["messages"][0], {"role": "system", "content": "Be accurate."})
        self.assertEqual(mapped["messages"][1], {"role": "user", "content": "Define opportunity cost."})
        self.assertEqual(mapped["temperature"], 0.3)
        self.assertEqual(mapped["max_tokens"], 512)

    def test_requests_json_object_for_structured_gemini_payload(self):
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Return JSON."}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": {"type": "OBJECT"}},
        }
        self.assertEqual(llm_provider._to_openai_payload(payload)["response_format"], {"type": "json_object"})

    def test_normalizes_openai_response_to_existing_gemini_shape(self):
        result = llm_provider._normalize_openai_response({
            "model": "test-model",
            "choices": [{"message": {"content": "A useful answer."}, "finish_reason": "stop"}],
        })
        self.assertEqual(result["candidates"][0]["content"]["parts"][0]["text"], "A useful answer.")
        self.assertEqual(result["candidates"][0]["finishReason"], "STOP")

    @patch.dict(os.environ, {"LLM_PROVIDER": "freellmapi", "FREELLMAPI_API_KEY": "temporary-test-key",
                             "FREELLMAPI_BASE_URL": "http://127.0.0.1:3001/v1",
                             "FREELLMAPI_MODEL": "gemini-3.5-flash-lite"})
    @patch("scripts.llm_provider.urllib.request.urlopen")
    def test_posts_openai_request_with_bearer_key(self, urlopen):
        body = json.dumps({"choices": [{"message": {"content": "Opportunity cost is the next best alternative forgone."},
                                       "finish_reason": "stop"}]}).encode()
        urlopen.return_value.__enter__.return_value.read.return_value = body
        payload = {
            "systemInstruction": {"parts": [{"text": "Be concise."}]},
            "contents": [{"role": "user", "parts": [{"text": "Define opportunity cost."}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100},
        }
        result = llm_provider.generate_content("unused", None, payload, label="test", timeout=5)
        self.assertIn("Opportunity cost", result["candidates"][0]["content"]["parts"][0]["text"])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:3001/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer temporary-test-key")


if __name__ == "__main__":
    unittest.main()
