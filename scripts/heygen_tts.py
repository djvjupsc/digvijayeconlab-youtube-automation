"""HeyGen Text-to-Speech helper for the user's authorized Professional Voice Clone."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://api.heygen.com/v3/models/audio/tts"


def synthesize(text, language, output_path, seed=7):
    api_key = os.environ.get("HEYGEN_API_KEY")
    voice_id = os.environ.get("HEYGEN_VOICE_ID")
    if not api_key or not voice_id:
        raise RuntimeError("HEYGEN_API_KEY and HEYGEN_VOICE_ID must be configured as GitHub Actions secrets.")

    payload = {
        "voice_id": voice_id,
        "text": text,
        "language": language,
        "seed": seed,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"HeyGen TTS failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"HeyGen TTS connection failed: {exc}") from exc

    audio_url = data.get("data", {}).get("audio_url")
    if not isinstance(audio_url, str) or not audio_url.startswith("https://"):
        raise RuntimeError("HeyGen TTS response did not contain a valid HTTPS audio_url.")

    audio_request = urllib.request.Request(audio_url, headers={"User-Agent": "DigvijayEconLab/1.0"})
    try:
        with urllib.request.urlopen(audio_request, timeout=180) as response:
            audio = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Unable to retrieve HeyGen audio output: {exc}") from exc

    if len(audio) < 128:
        raise RuntimeError("HeyGen returned an unexpectedly small audio file.")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio)
    return {"path": str(output_path), "bytes": len(audio), "language": language}
