from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProductionProviderWiringTests(unittest.TestCase):
    def test_daily_workflow_has_opt_in_freellmapi_and_keeps_gemini_default(self):
        workflow = (ROOT / ".github/workflows/daily-channel-pack.yml").read_text(encoding="utf-8")
        self.assertIn("llm_provider:", workflow)
        self.assertIn("default: gemini", workflow)
        self.assertIn("options:", workflow)
        self.assertIn("- freellmapi", workflow)
        self.assertIn("Set up Node.js for temporary FreeLLMAPI", workflow)
        self.assertIn("Start temporary FreeLLMAPI for production generation", workflow)
        self.assertIn("Retrieve masked temporary FreeLLMAPI key", workflow)
        self.assertIn("Stop temporary FreeLLMAPI after generation", workflow)
        self.assertIn("LLM_FALLBACK_PROVIDER: huggingface,gemini", workflow)
        self.assertIn("HF_TOKEN: ${{ secrets.HF_TOKEN }}", workflow)
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


if __name__ == "__main__":
    unittest.main()
