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


    @patch.dict(os.environ, {"LLM_PROVIDER": "freellmapi", "FREELLMAPI_API_KEY": "temporary-test-key",
                             "FREELLMAPI_BASE_URL": "http://127.0.0.1:3001/v1"})
    @patch("scripts.llm_provider.time.sleep")
    @patch("scripts.llm_provider.time.time", return_value=1000.0)
    @patch("scripts.llm_provider.urllib.request.urlopen")
    def test_waits_until_provider_retry_at_timestamp_after_429(self, urlopen, _clock, sleep):
        rate_limit_body = json.dumps({
            "error": {
                "message": "All models exhausted. Soonest reset ~56s.",
                "type": "rate_limit_error",
                "retryAtMs": 1056000,
            }
        }).encode("utf-8")
        rate_limited = llm_provider.urllib.error.HTTPError(
            "http://127.0.0.1:3001/v1/chat/completions",
            429,
            "rate limited",
            {},
            io.BytesIO(rate_limit_body),
        )
        success = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Retry succeeded."}, "finish_reason": "stop"}]
        }).encode("utf-8"))
        urlopen.side_effect = [rate_limited, success]
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Say retry succeeded."}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 40},
        }
        result = llm_provider.generate_content("unused", None, payload, label="retry test", timeout=5)
        self.assertEqual(result["candidates"][0]["content"]["parts"][0]["text"], "Retry succeeded.")
        sleep.assert_called_once_with(56)
        self.assertEqual(urlopen.call_count, 2)

    def test_parses_human_readable_reset_when_timestamp_is_absent(self):
        error = llm_provider.urllib.error.HTTPError(
            "https://example.invalid", 429, "busy", {}, io.BytesIO(b"")
        )
        self.assertEqual(llm_provider._retry_delay_seconds(error, "Soonest reset ~56s.", 2), 56)


    @patch.dict(os.environ, {
        "LLM_PROVIDER": "freellmapi",
        "LLM_FALLBACK_PROVIDER": "gemini",
        "FREELLMAPI_API_KEY": "temporary-unified-key",
        "FREELLMAPI_BASE_URL": "http://127.0.0.1:3001/v1",
        "GEMINI_API_KEY": "temporary-google-key",
    })
    @patch("scripts.gemini_client.generate_content", return_value={"candidates": [{"content": {"parts": [{"text": "Gemini fallback answer."}]}}]})
    @patch("scripts.llm_provider.time.sleep")
    @patch("scripts.llm_provider.urllib.request.urlopen")
    def test_falls_back_to_direct_gemini_after_freellmapi_retries_fail(self, urlopen, _sleep, gemini):
        unavailable = llm_provider.urllib.error.HTTPError(
            "http://127.0.0.1:3001/v1/chat/completions",
            503, "Unavailable", {}, io.BytesIO(b"temporary failure"),
        )
        urlopen.side_effect = unavailable
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Explain opportunity cost."}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100},
        }
        result = llm_provider.generate_content("https://gemini.invalid", None, payload, label="fallback test")
        self.assertEqual(result["candidates"][0]["content"]["parts"][0]["text"], "Gemini fallback answer.")
        self.assertEqual(urlopen.call_count, llm_provider.MAX_ATTEMPTS)
        gemini.assert_called_once()
        self.assertEqual(gemini.call_args.args[1], "temporary-google-key")


    @patch.dict(os.environ, {
        "LLM_PROVIDER": "freellmapi",
        "LLM_FALLBACK_PROVIDER": "huggingface,gemini",
        "FREELLMAPI_API_KEY": "temporary-unified-key",
        "FREELLMAPI_BASE_URL": "http://127.0.0.1:3001/v1",
        "HF_TOKEN": "temporary-hf-token",
        "HF_FALLBACK_MODEL": "Qwen/Qwen3-4B-Instruct-2507:cheapest",
    })
    @patch("scripts.llm_provider.time.sleep")
    @patch("scripts.llm_provider.urllib.request.urlopen")
    def test_uses_independent_huggingface_fallback_after_freellmapi_failure(self, urlopen, _sleep):
        primary_error = llm_provider.urllib.error.HTTPError(
            "http://127.0.0.1:3001/v1/chat/completions",
            503, "Unavailable", {}, io.BytesIO(b"temporary failure"),
        )
        success = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Independent fallback answer."}, "finish_reason": "stop"}]
        }).encode("utf-8"))
        urlopen.side_effect = [primary_error] * llm_provider.MAX_ATTEMPTS + [success]
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Explain opportunity cost."}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100},
        }
        result = llm_provider.generate_content("unused", None, payload, label="HF fallback test")
        self.assertEqual(
            result["candidates"][0]["content"]["parts"][0]["text"],
            "Independent fallback answer.",
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://router.huggingface.co/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer temporary-hf-token")
        body = json.loads(request.data.decode("utf-8"))
        self.assertEqual(body["model"], "Qwen/Qwen3-4B-Instruct-2507:cheapest")

    @patch.dict(os.environ, {"HF_TOKEN": "temporary-hf-token"})
    @patch("scripts.llm_provider.urllib.request.urlopen")
    def test_huggingface_fallback_honors_retry_after(self, urlopen):
        limited = llm_provider.urllib.error.HTTPError(
            "https://router.huggingface.co/v1/chat/completions",
            429, "rate limited", {"Retry-After": "7"}, io.BytesIO(b"{}"),
        )
        success = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": "Recovered."}, "finish_reason": "stop"}]
        }).encode("utf-8"))
        urlopen.side_effect = [limited, success]
        with patch("scripts.llm_provider.time.sleep") as sleep:
            result = llm_provider._generate_huggingface(
                {"contents": [{"role": "user", "parts": [{"text": "test"}]}]}
            )
        self.assertEqual(result["candidates"][0]["content"]["parts"][0]["text"], "Recovered.")
        sleep.assert_called_once_with(7)


if __name__ == "__main__":
    unittest.main()
