"""Verify every configured independent LLM fallback before production work is claimed.

The probe deliberately points FreeLLMAPI at an unused localhost port so each configured
independent provider is called directly through the normal adapter fallback path.
"""
import os
import sys

try:
    from .llm_provider import generate_content, get_api_key
except ImportError:
    from llm_provider import generate_content, get_api_key


PAYLOAD = {
    "systemInstruction": {
        "parts": [{"text": "You are a concise bilingual Economics tutor. Do not invent facts."}]
    },
    "contents": [{
        "role": "user",
        "parts": [{
            "text": "Define opportunity cost in one short sentence in English and one in Hindi."
        }],
    }],
    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 96},
}


def configured_independent_providers(environ=None):
    environ = os.environ if environ is None else environ
    account_id = environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    cloudflare_token = environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    hf_token = environ.get("HF_TOKEN", "").strip()

    if bool(account_id) != bool(cloudflare_token):
        raise RuntimeError(
            "Cloudflare fallback is partially configured. Set both CLOUDFLARE_ACCOUNT_ID "
            "and CLOUDFLARE_API_TOKEN, or remove the incomplete secret."
        )

    providers = []
    if account_id and cloudflare_token:
        providers.append("cloudflare")
    if hf_token:
        providers.append("huggingface")
    if not providers:
        raise RuntimeError(
            "No independent fallback is configured. Add Cloudflare Workers AI credentials "
            "or a Hugging Face token with 'Make calls to Inference Providers' permission."
        )
    return providers


def run_preflight():
    providers = configured_independent_providers()
    os.environ.setdefault("LLM_PROVIDER", "freellmapi")
    os.environ.setdefault("FREELLMAPI_API_KEY", "provider-preflight-placeholder-key")
    os.environ.setdefault("FREELLMAPI_BASE_URL", "http://127.0.0.1:3999/v1")

    api_key = get_api_key()
    passed = []
    failures = []

    for provider in providers:
        os.environ["LLM_FALLBACK_PROVIDER"] = provider
        try:
            result = generate_content(
                "unused",
                api_key,
                PAYLOAD,
                label=f"Live {provider} provider preflight",
                timeout=45,
            )
            candidates = result.get("candidates", [])
            answer = (
                candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                if candidates else ""
            )
            if len(answer.strip()) < 20:
                raise RuntimeError("Provider returned an empty or implausibly short answer.")
            passed.append(provider)
            print(f"LIVE_{provider.upper()}_PREFLIGHT_PASS")
            print(f"{provider} response length: {len(answer)}")
        except Exception as exc:
            failures.append((provider, str(exc)))
            print(f"LIVE_{provider.upper()}_PREFLIGHT_FAIL: {exc}")

    if failures:
        details = "; ".join(f"{provider}: {message}" for provider, message in failures)
        raise RuntimeError(
            "At least one configured independent fallback failed its live preflight. "
            "Correct the provider credentials/permissions before claiming a production pack. "
            + details
        )
    if not passed:
        raise RuntimeError("No independent provider passed live preflight.")

    print("LIVE_INDEPENDENT_PROVIDER_PREFLIGHT_PASS")
    print("Verified independent providers:", ", ".join(passed))
    return passed


def main():
    try:
        run_preflight()
    except Exception as exc:
        print(f"PROVIDER_PREFLIGHT_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
