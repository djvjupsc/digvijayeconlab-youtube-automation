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
        self.assertIn("LLM_FALLBACK_PROVIDER: ${{ steps.provider_preflight.outputs.fallback_chain }},gemini", workflow)
        self.assertIn("HF_TOKEN: ${{ secrets.HF_TOKEN }}", workflow)
        self.assertIn("CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("git push origin HEAD:main", workflow)
        self.assertIn("inputs.llm_provider == 'freellmapi'", workflow)
        preflight = workflow.index("Verify independent providers before claiming production pack")
        claim = workflow.index("Claim today's production pack")
        self.assertLess(preflight, claim)
        self.assertIn("python scripts/provider_preflight.py", workflow)
        self.assertIn("id: provider_preflight", workflow)

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
        self.assertIn("Verify every configured independent provider before FreeLLMAPI setup", workflow)
        self.assertIn("FREELLMAPI_BASE_URL: http://127.0.0.1:3999/v1", workflow)
        self.assertIn("CLOUDFLARE_FALLBACK_MODEL: \"@cf/meta/llama-3.2-3b-instruct\"", workflow)
        self.assertIn("python scripts/provider_preflight.py", workflow)
        self.assertIn("id: provider_preflight", workflow)
        self.assertIn("id: provider_preflight", workflow)
        preflight_script = (ROOT / "scripts/provider_preflight.py").read_text(encoding="utf-8")
        self.assertIn("Make calls to Inference Providers", preflight_script)
        self.assertIn("LIVE_INDEPENDENT_PROVIDER_PREFLIGHT_PASS", preflight_script)

    def test_live_fallback_preflight_runs_before_node_build_and_dependency_install(self):
        workflow = (ROOT / ".github/workflows/freellmapi-smoke-test.yml").read_text(encoding="utf-8")
        probe = workflow.index("Verify every configured independent provider before FreeLLMAPI setup")
        node = workflow.index("Set up Node.js")
        freeapi_build = workflow.index("Download and build FreeLLMAPI")
        font_install = workflow.index("Install Devanagari font and eSpeak test tools")
        dependency_install = workflow.index("Install Python test dependencies")
        preflight_script = (ROOT / "scripts/provider_preflight.py").read_text(encoding="utf-8")
        self.assertLess(probe, node)
        self.assertLess(probe, freeapi_build)
        self.assertLess(probe, font_install)
        self.assertLess(probe, dependency_install)
        self.assertIn("Make calls to Inference Providers", preflight_script)


if __name__ == "__main__":
    unittest.main()
