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
    def test_requires_cloudflare_for_zero_cost_independent_fallback(self):
        with self.assertRaisesRegex(RuntimeError, "No zero-cost independent fallback"):
            provider_preflight.configured_independent_providers({})

    def test_rejects_huggingface_only_even_when_inference_token_exists(self):
        with self.assertRaisesRegex(RuntimeError, "Free users have no included monthly credits"):
            provider_preflight.configured_independent_providers({
                "HF_INFERENCE_TOKEN": "hf-token",
            })

    def test_skips_partial_cloudflare_and_huggingface_in_zero_cost_mode(self):
        with self.assertRaisesRegex(RuntimeError, "No zero-cost independent fallback"):
            provider_preflight.configured_independent_providers({
                "CLOUDFLARE_ACCOUNT_ID": "account-only",
                "CLOUDFLARE_API_TOKEN": "",
                "HF_INFERENCE_TOKEN": "hf-token",
            })

    def test_cloudflare_is_the_only_zero_cost_independent_provider(self):
        providers, warnings = provider_preflight.configured_independent_providers({
            "CLOUDFLARE_ACCOUNT_ID": "account",
            "CLOUDFLARE_API_TOKEN": "cloudflare-token",
            "HF_INFERENCE_TOKEN": "hf-token",
        })
        self.assertEqual(providers, ["cloudflare"])
        self.assertTrue(any("Hugging Face routed inference is disabled" in item for item in warnings))

    @patch.dict(os.environ, {
        "LLM_PROVIDER": "freellmapi",
        "FREELLMAPI_API_KEY": "placeholder",
        "FREELLMAPI_BASE_URL": "http://127.0.0.1:3999/v1",
        "CLOUDFLARE_ACCOUNT_ID": "account",
        "CLOUDFLARE_API_TOKEN": "cloudflare-token",
        "HF_INFERENCE_TOKEN": "hf-token",
    }, clear=True)
    @patch("scripts.provider_preflight.get_api_key", return_value="placeholder")
    @patch("scripts.provider_preflight.generate_content", return_value=GOOD_RESPONSE)
    def test_live_preflight_tests_only_cloudflare_and_exports_chain(self, generate, _key):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "github-output.txt"
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_path)}):
                passed = provider_preflight.run_preflight()
            self.assertEqual(passed, ["cloudflare"])
            self.assertEqual(generate.call_count, 1)
            self.assertEqual(generate.call_args.kwargs["label"], "Live cloudflare provider preflight")
            self.assertIn("fallback_chain=cloudflare", output_path.read_text(encoding="utf-8"))

    @patch.dict(os.environ, {
        "LLM_PROVIDER": "freellmapi",
        "FREELLMAPI_API_KEY": "placeholder",
        "FREELLMAPI_BASE_URL": "http://127.0.0.1:3999/v1",
        "CLOUDFLARE_ACCOUNT_ID": "account",
        "CLOUDFLARE_API_TOKEN": "cloudflare-token",
    }, clear=True)
    @patch("scripts.provider_preflight.get_api_key", return_value="placeholder")
    @patch("scripts.provider_preflight.generate_content", side_effect=RuntimeError("HTTP 429 daily neuron allocation exhausted"))
    def test_blocks_when_cloudflare_free_capacity_is_exhausted(self, _generate, _key):
        with self.assertRaisesRegex(RuntimeError, "No zero-cost independent provider passed live preflight"):
            provider_preflight.run_preflight()


if __name__ == "__main__":
    unittest.main()
