"""Verify a genuinely zero-cost independent provider before production is claimed.

Hugging Face routed Inference Providers are intentionally excluded from this
zero-cost path: current Hugging Face pricing grants Free users no included
monthly inference credits. Cloudflare Workers AI Free is the independent
provider supported by this preflight.
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
    hf_token = environ.get("HF_INFERENCE_TOKEN", "").strip()

    providers = []
    warnings = []
    if account_id and cloudflare_token:
        providers.append("cloudflare")
    elif account_id or cloudflare_token:
        warnings.append(
            "Cloudflare skipped: both CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN are required."
        )

    if hf_token:
        warnings.append(
            "Hugging Face routed inference is disabled in strict zero-cost mode: "
            "Free users have no included monthly Inference Provider credits."
        )

    if not providers:
        detail = " ".join(warnings)
        raise RuntimeError(
            "No zero-cost independent fallback is configured. Add CLOUDFLARE_ACCOUNT_ID "
            "and CLOUDFLARE_API_TOKEN for Cloudflare Workers AI on the Workers Free plan. "
            "Hugging Face routed inference is not used because Free users have no included "
            "monthly credits. " + detail
        )
    return providers, warnings


def run_preflight():
    providers, warnings = configured_independent_providers()
    os.environ.setdefault("LLM_PROVIDER", "freellmapi")
    os.environ.setdefault("FREELLMAPI_API_KEY", "provider-preflight-placeholder-key")
    os.environ.setdefault("FREELLMAPI_BASE_URL", "http://127.0.0.1:3999/v1")

    api_key = get_api_key()
    passed = []
    failures = list(warnings)

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
            failures.append(f"{provider}: {exc}")
            print(f"LIVE_{provider.upper()}_PREFLIGHT_FAIL: {exc}")

    if not passed:
        details = "; ".join(failures) or "No provider returned a valid response."
        raise RuntimeError(
            "No zero-cost independent provider passed live preflight. Correct credentials or "
            "wait for the Cloudflare Free daily allocation to reset before claiming production. "
            + details
        )

    chain = ",".join(passed)
    print("LIVE_ZERO_COST_PROVIDER_PREFLIGHT_PASS")
    print("Verified zero-cost independent providers:", chain)
    if failures:
        print("NOTICE: non-zero-cost or unavailable routes excluded:", "; ".join(failures))
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"fallback_chain={chain}\n")
    os.environ["LLM_FALLBACK_PROVIDER"] = chain
    return passed


def main():
    try:
        run_preflight()
    except Exception as exc:
        print(f"PROVIDER_PREFLIGHT_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
