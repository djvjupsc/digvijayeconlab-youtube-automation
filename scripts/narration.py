"""Safe, explicit whole-video fallback from Chatterbox to eSpeak preview narration."""

import re
import subprocess
from pathlib import Path


def preview_speech_text(value):
    """Remove LaTeX control syntax before passing bilingual text to eSpeak."""
    text = str(value or "")
    text = re.sub(r"\\+text\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[A-Za-z]+", " ", text)
    text = re.sub(r"[$^{}_]", " ", text)
    text = re.sub(r"\\", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def synthesize_audio_batch(
    items,
    *,
    chatterbox_enabled,
    allow_preview_fallback,
    espeak_binary,
    chatterbox_synthesize=None,
):
    """Synthesize a complete set in one voice mode; never leave a mixed-voice render.

    Each item contains text, language ('hi' or 'en'), path, and optional seed/speed.
    If Chatterbox fails part-way through and preview fallback is explicitly enabled,
    all partial Chatterbox files are deleted and every item is regenerated with eSpeak.
    """
    items = list(items)
    if not items:
        raise ValueError("At least one narration item is required.")

    use_chatterbox = bool(chatterbox_enabled)
    providers = []

    if use_chatterbox:
        if chatterbox_synthesize is None:
            raise RuntimeError("Chatterbox is enabled but no synthesis function was supplied.")
        try:
            for item in items:
                target = Path(item["path"])
                target.parent.mkdir(parents=True, exist_ok=True)
                result = chatterbox_synthesize(
                    item["text"],
                    item["language"],
                    target,
                    seed=int(item.get("seed", 7)),
                )
                providers.append(
                    (result or {}).get("provider", "Chatterbox Multilingual V3")
                )
        except Exception as exc:
            if not allow_preview_fallback or not espeak_binary:
                raise RuntimeError(
                    "Chatterbox narration failed. The ZeroGPU Space may be out of free quota "
                    "or temporarily unavailable. Preview fallback is disabled."
                ) from exc

            # A failed Chatterbox attempt may have produced some clips already.
            # Remove every output before creating a consistent eSpeak-only preview.
            for item in items:
                Path(item["path"]).unlink(missing_ok=True)
            print(
                "WARNING: Chatterbox failed "
                f"({type(exc).__name__}: {str(exc).replace(chr(10), ' ')[:240]}). "
                "Restarting the entire narration batch with eSpeak PREVIEW audio. "
                "This render is not the owner's voice and is not upload-eligible.",
                flush=True,
            )
            use_chatterbox = False
            providers = []

    if not use_chatterbox:
        if not espeak_binary:
            raise RuntimeError(
                "eSpeak is required for preview narration but was not found. "
                "Install espeak-ng or disable preview fallback."
            )
        for item in items:
            language = item["language"]
            if language not in {"hi", "en"}:
                raise ValueError(f"Unsupported eSpeak narration language: {language}")
            voice = "hi" if language == "hi" else "en-us"
            target = Path(item["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            command = [
                espeak_binary,
                "-v", voice,
                "-s", str(int(item.get("speed", 145))),
                "-w", str(target),
                "--stdin",
            ]
            speech_text = preview_speech_text(item["text"])
            if not speech_text:
                raise ValueError("Narration text is empty after preview-text cleanup.")
            # --stdin avoids platform argument-length limits and keeps Unicode text
            # out of the process argument vector. LaTeX syntax is stripped above.
            subprocess.run(command, input=speech_text, check=True, capture_output=True, text=True)
            providers.append(f"eSpeak NG ({voice})")

    return use_chatterbox, providers
