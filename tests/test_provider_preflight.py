import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import provider_preflight


GOOD_RESPONSE = {
    "candidates": [{
        "content": {
            "parts": [{
                "text": "Opportunity cost is the next best alternative. अवसर लागत अगला सर्वोत्तम त्यागा गया विकल्प है।"
            }]
        }
    }]
}


class ProviderPreflightTests(unittest.TestCase):
    def test_requires_at_least_one_independent_provider(self):
        with self.assertRaisesRegex(RuntimeError, "No independent fallback credentials"):
            provider_preflight.configured_independent_providers({})

    def test_skips_partial_cloudflare_credentials_when_huggingface_is_configured(self):
        providers, warnings = provider_preflight.configured_independent_providers({
            "CLOUDFLARE_ACCOUNT_ID": "account-only",
            "CLOUDFLARE_API_TOKEN": "",
            "HF_TOKEN": "hf-token",
        })
        self.assertEqual(providers, ["huggingface"])
        self.assertTrue(any("Cloudflare skipped" in item for item in warnings))

    def test_lists_configured_providers_in_fallback_order(self):
        providers, warnings = provider_preflight.configured_independent_providers({
            "CLOUDFLARE_ACCOUNT_ID": "account",
            "CLOUDFLARE_API_TOKEN": "token",
            "HF_TOKEN": "hf-token",
        })
        self.assertEqual(providers, ["cloudflare", "huggingface"])
        self.assertFalse(warnings)

    @patch.dict(os.environ, {
        "LLM_PROVIDER": "freellmapi",
        "FREELLMAPI_API_KEY": "placeholder",
        "FREELLMAPI_BASE_URL": "http://127.0.0.1:3999/v1",
        "CLOUDFLARE_ACCOUNT_ID": "account",
        "CLOUDFLARE_API_TOKEN": "cloudflare-token",
        "HF_TOKEN": "hf-token",
    }, clear=True)
    @patch("scripts.provider_preflight.get_api_key", return_value="placeholder")
    @patch("scripts.provider_preflight.generate_content", return_value=GOOD_RESPONSE)
    def test_checks_each_configured_independent_provider(self, generate, _key):
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
        "CLOUDFLARE_ACCOUNT_ID": "account",
        "CLOUDFLARE_API_TOKEN": "cloudflare-token",
        "HF_TOKEN": "hf-token",
    }, clear=True)
    @patch("scripts.provider_preflight.get_api_key", return_value="placeholder")
    @patch("scripts.provider_preflight.generate_content")
    def test_uses_only_the_provider_that_passed_and_exports_chain(self, generate, _key):
        def provider_result(*args, **kwargs):
            if kwargs["label"].startswith("Live huggingface"):
                raise RuntimeError("HTTP 403 permission denied")
            return GOOD_RESPONSE

        generate.side_effect = provider_result
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "github-output.txt"
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
                passed = provider_preflight.run_preflight()
            self.assertEqual(passed, ["cloudflare"])
            self.assertIn("fallback_chain=cloudflare", output_path.read_text(encoding="utf-8"))

    @patch.dict(os.environ, {
        "LLM_PROVIDER": "freellmapi",
        "FREELLMAPI_API_KEY": "placeholder",
        "FREELLMAPI_BASE_URL": "http://127.0.0.1:3999/v1",
        "HF_TOKEN": "hf-token",
    }, clear=True)
    @patch("scripts.provider_preflight.get_api_key", return_value="placeholder")
    @patch("scripts.provider_preflight.generate_content", side_effect=RuntimeError("HTTP 403 permission denied"))
    def test_blocks_when_no_configured_provider_passes_live_probe(self, _generate, _key):
        with self.assertRaisesRegex(RuntimeError, "No independent provider passed live preflight"):
            provider_preflight.run_preflight()


if __name__ == "__main__":
    unittest.main()
