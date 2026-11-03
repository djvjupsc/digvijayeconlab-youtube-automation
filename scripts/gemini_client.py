"""Shared retry policy for transient Gemini API failures."""
import json
import time
import urllib.error
import urllib.request

RETRYABLE_HTTP_STATUS = {408, 429, 500, 502, 503, 504}
MAX_GEMINI_ATTEMPTS = 5


def generate_content(api_url, api_key, payload, label="Gemini", timeout=150):
    request = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(1, MAX_GEMINI_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            if exc.code not in RETRYABLE_HTTP_STATUS or attempt == MAX_GEMINI_ATTEMPTS:
                raise RuntimeError(
                    f"{label} failed (HTTP {exc.code}) after {attempt} attempt(s): {detail}"
                ) from exc
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = min(60, max(1, int(retry_after))) if retry_after else min(30, 3 * (2 ** (attempt - 1)))
            except (TypeError, ValueError):
                delay = min(30, 3 * (2 ** (attempt - 1)))
            print(f"{label}: temporary HTTP {exc.code}; retry {attempt + 1}/{MAX_GEMINI_ATTEMPTS} in {delay}s.")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == MAX_GEMINI_ATTEMPTS:
                raise RuntimeError(
                    f"{label} connection failed after {attempt} attempts: {exc}"
                ) from exc
            delay = min(30, 3 * (2 ** (attempt - 1)))
            print(f"{label}: connection issue; retry {attempt + 1}/{MAX_GEMINI_ATTEMPTS} in {delay}s.")
            time.sleep(delay)
