from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProductionProviderWiringTests(unittest.TestCase):
    def test_daily_workflow_defaults_to_freellmapi_and_has_independent_fallbacks(self):
        workflow = (ROOT / ".github/workflows/daily-channel-pack.yml").read_text(encoding="utf-8")
        self.assertIn("llm_provider:", workflow)
        self.assertIn("default: freellmapi", workflow)
        self.assertIn("options:", workflow)
        self.assertIn("- freellmapi", workflow)
        self.assertIn("Set up Node.js for temporary FreeLLMAPI", workflow)
        self.assertIn("Start temporary FreeLLMAPI for production generation", workflow)
        self.assertIn("Retrieve masked temporary FreeLLMAPI key", workflow)
        self.assertIn("Stop temporary FreeLLMAPI after generation", workflow)
        self.assertIn("LLM_FALLBACK_PROVIDER: cloudflare,huggingface,gemini", workflow)
        self.assertIn("HF_TOKEN: ${{ secrets.HF_TOKEN }}", workflow)
        self.assertIn("CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("git push origin HEAD:main", workflow)
        self.assertIn("inputs.llm_provider == 'freellmapi'", workflow)

    def test_free_llm_runtime_is_pinned_to_the_tested_revision(self):
        expected = "fb07845faf7cf986ea9f3692e055076035dd8739"
        for name in ("daily-channel-pack.yml", "freellmapi-smoke-test.yml"):
            workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn(expected, workflow)

    def test_daily_assets_use_the_shared_provider_adapter(self):
        source = (ROOT / "scripts/generate_daily_assets.py").read_text(encoding="utf-8")
        self.assertIn("from .llm_provider import generate_content, get_api_key", source)
        self.assertIn("api_key = get_api_key()", source)
        self.assertIn('label="Daily asset generation"', source)

    def test_smoke_workflow_runs_a_live_independent_provider_probe(self):
        workflow = (ROOT / ".github/workflows/freellmapi-smoke-test.yml").read_text(encoding="utf-8")
        self.assertIn("Verify one live independent provider fallback request", workflow)
        self.assertIn("FREELLMAPI_BASE_URL: http://127.0.0.1:3999/v1", workflow)
        self.assertIn("LLM_FALLBACK_PROVIDER: cloudflare,huggingface", workflow)
        self.assertIn("LIVE_INDEPENDENT_FALLBACK_PASS", workflow)


if __name__ == "__main__":
    unittest.main()
