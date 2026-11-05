"""Provider adapter for Gemini and FreeLLMAPI's OpenAI-compatible endpoint.

Set LLM_PROVIDER=freellmapi to use FreeLLMAPI. The default remains Gemini
so existing production workflows are unchanged until explicitly configured.
"""
import json
import os
import time
import urllib.error
import urllib.request

RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3
MAX_RATE_LIMIT_WAIT_SECONDS = 120


def _retry_delay_seconds(exc, detail, attempt=1):
    """Honor the provider's exact cooldown timestamp when it supplies one."""
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    if retry_after:
        try:
            return max(1, int(retry_after))
        except (TypeError, ValueError):
            pass

    try:
        body = json.loads(detail)
        error = body.get("error", body) if isinstance(body, dict) else {}
        retry_at_ms = error.get("retryAtMs") if isinstance(error, dict) else None
        if isinstance(retry_at_ms, (int, float)):
            return max(1, int((retry_at_ms - time.time() * 1000 + 999) // 1000))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    import re
    reset_match = re.search(r"reset\s*~\s*(\d+)\s*s", detail, re.IGNORECASE)
    if reset_match:
        return max(1, int(reset_match.group(1)))

    return min(30, 2 ** attempt)


def get_api_key():
    provider = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
    if provider == "freellmapi":
        key = os.environ.get("FREELLMAPI_API_KEY")
        if not key:
            raise RuntimeError("FREELLMAPI_API_KEY is required when LLM_PROVIDER=freellmapi.")
        return key
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini.")
    return key


def _to_openai_payload(payload):
    system_parts = payload.get("systemInstruction", {}).get("parts", [])
    system_text = "\n".join(p.get("text", "") for p in system_parts if p.get("text"))
    messages = []
    if system_text:
        messages.append({"role": "system", "content": system_text})
    for item in payload.get("contents", []):
        role = "assistant" if item.get("role") == "model" else item.get("role", "user")
        parts = item.get("parts", [])
        content = "\n".join(p.get("text", "") for p in parts if p.get("text"))
        if content:
            messages.append({"role": role, "content": content})
    if not messages:
        raise RuntimeError("No text messages were present in the model request.")

    generation = payload.get("generationConfig", {})
    request = {
        "model": os.environ.get("FREELLMAPI_MODEL", "gemini-3.5-flash-lite"),
        "messages": messages,
        "temperature": generation.get("temperature", 0.2),
        "max_tokens": generation.get("maxOutputTokens", 4096),
    }
    if generation.get("responseMimeType") == "application/json" or generation.get("responseSchema"):
        request["response_format"] = {"type": "json_object"}
    return request


def _normalize_openai_response(response):
    choices = response.get("choices") or []
    if not choices:
        raise RuntimeError("FreeLLMAPI returned no completion choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        content = "\n".join(
            item.get("text", "") for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("FreeLLMAPI returned an empty assistant response.")
    finish = choices[0].get("finish_reason") or "stop"
    return {
        "candidates": [{
            "content": {"parts": [{"text": content}]},
            "finishReason": "MAX_TOKENS" if finish == "length" else "STOP",
        }],
        "modelVersion": response.get("model", ""),
    }


def generate_content(api_url, api_key, payload, label="LLM request", timeout=150):
    """Return the Gemini-shaped response expected by existing pipeline scripts."""
    provider = os.environ.get("LLM_PROVIDER", "gemini").strip().lower()
    if provider != "freellmapi":
        try:
            from .gemini_client import generate_content as gemini_generate
        except ImportError:
            from gemini_client import generate_content as gemini_generate
        return gemini_generate(api_url, api_key, payload, label=label, timeout=timeout)

    unified_key = get_api_key()
    base_url = os.environ.get("FREELLMAPI_BASE_URL", "http://127.0.0.1:3001/v1").rstrip("/")
    url = base_url + "/chat/completions"
    request_data = json.dumps(_to_openai_payload(payload)).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=request_data,
        headers={
            "Authorization": f"Bearer {unified_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return _normalize_openai_response(json.loads(response.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            if exc.code not in RETRYABLE_HTTP_STATUS or attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"{label} via FreeLLMAPI failed (HTTP {exc.code}): {detail}") from exc
            delay = _retry_delay_seconds(exc, detail, attempt) if exc.code == 429 else min(30, 2 ** attempt)
            if delay > MAX_RATE_LIMIT_WAIT_SECONDS:
                raise RuntimeError(
                    f"{label} via FreeLLMAPI is rate-limited for {delay}s, exceeding the "
                    f"configured wait ceiling of {MAX_RATE_LIMIT_WAIT_SECONDS}s: {detail}"
                ) from exc
            print(f"{label}: FreeLLMAPI temporary HTTP {exc.code}; retrying in {delay}s.")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(f"{label} via FreeLLMAPI connection failed: {exc}") from exc
            delay = 2 ** attempt
            print(f"{label}: FreeLLMAPI connection issue; retrying in {delay}s.")
            time.sleep(delay)
