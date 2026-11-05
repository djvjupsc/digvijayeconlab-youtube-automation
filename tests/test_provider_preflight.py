import os
import unittest
from unittest.mock import patch

from scripts import provider_preflight


class ProviderPreflightTests(unittest.TestCase):
    def test_requires_at_least_one_independent_provider(self):
        with self.assertRaisesRegex(RuntimeError, "No independent fallback is configured"):
            provider_preflight.configured_independent_providers({})

    def test_rejects_partial_cloudflare_credentials(self):
        with self.assertRaisesRegex(RuntimeError, "partially configured"):
            provider_preflight.configured_independent_providers({
                "CLOUDFLARE_ACCOUNT_ID": "account-only",
                "CLOUDFLARE_API_TOKEN": "",
                "HF_TOKEN": "",
            })

    def test_lists_configured_providers_in_fallback_order(self):
        providers = provider_preflight.configured_independent_providers({
            "CLOUDFLARE_ACCOUNT_ID": "account",
            "CLOUDFLARE_API_TOKEN": "token",
            "HF_TOKEN": "hf-token",
        })
        self.assertEqual(providers, ["cloudflare", "huggingface"])

    @patch.dict(os.environ, {
        "LLM_PROVIDER": "freellmapi",
        "FREELLMAPI_API_KEY": "placeholder",
        "FREELLMAPI_BASE_URL": "http://127.0.0.1:3999/v1",
        "CLOUDFLARE_ACCOUNT_ID": "account",
        "CLOUDFLARE_API_TOKEN": "cloudflare-token",
        "HF_TOKEN": "hf-token",
    }, clear=True)
    @patch("scripts.provider_preflight.get_api_key", return_value="placeholder")
    @patch("scripts.provider_preflight.generate_content")
    def test_checks_each_configured_independent_provider(self, generate, _key):
        generate.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Opportunity cost is the next best alternative. अवसर लागत अगला सर्वोत्तम त्यागा गया विकल्प है।"}]}}]
        }
        passed = provider_preflight.run_preflight()
        self.assertEqual(passed, ["cloudflare", "huggingface"])
        calls = [call.kwargs["label"] for call in generate.call_args_list]
        self.assertEqual(calls, [
            "Live cloudflare provider preflight",
            "Live huggingface provider preflight",
        ])

    @patch.dict(os.environ, {
        "LLM_PROVIDER": "freellmapi",
        "FREELLMAPI_API_KEY": "placeholder",
        "FREELLMAPI_BASE_URL": "http://127.0.0.1:3999/v1",
        "HF_TOKEN": "hf-token",
    }, clear=True)
    @patch("scripts.provider_preflight.get_api_key", return_value="placeholder")
    @patch("scripts.provider_preflight.generate_content", side_effect=RuntimeError("HTTP 403 permission denied"))
    def test_blocks_when_configured_provider_fails_live_probe(self, _generate, _key):
        with self.assertRaisesRegex(RuntimeError, "failed its live preflight"):
            provider_preflight.run_preflight()


if __name__ == "__main__":
    unittest.main()
