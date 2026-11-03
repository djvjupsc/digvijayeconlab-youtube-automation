"""Free Chatterbox Multilingual V3 TTS through the official Hugging Face Space.

The voice reference is downloaded from a PRIVATE Hugging Face dataset repository.
It is never committed to this GitHub repository. The public Space is a shared
ZeroGPU demo, so availability and queue time are not guaranteed.
"""

import os
import re
import shutil
import tempfile
import wave
from pathlib import Path

import numpy as np

SPACE_DEFAULT = "ResembleAI/Chatterbox-Multilingual-TTS-V3"
API_DEFAULT = "/generate_tts_audio"
MAX_CHARS = 300
_CLIENT = None
_REFERENCE_AUDIO = None


def split_text(text, max_chars=MAX_CHARS):
    """Split text at sentence/word boundaries without exceeding the Space limit."""
    text = " ".join(str(text or "").split())
    if not text:
        raise ValueError("Chatterbox cannot synthesize empty text.")
    if max_chars < 1 or max_chars > MAX_CHARS:
        raise ValueError(f"max_chars must be between 1 and {MAX_CHARS}.")

    sentences = re.split(r"(?<=[.!?।॥])\s+", text)
    chunks = []
    current = ""

    def add_piece(piece):
        nonlocal current
        if not piece:
            return
        candidate = f"{current} {piece}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = piece

    for sentence in sentences:
        if len(sentence) <= max_chars:
            add_piece(sentence)
            continue
        words = sentence.split()
        for word in words:
            if len(word) > max_chars:
                if current:
                    chunks.append(current)
                    current = ""
                for offset in range(0, len(word), max_chars):
                    part = word[offset:offset + max_chars]
                    if len(part) == max_chars:
                        chunks.append(part)
                    else:
                        current = part
            else:
                add_piece(word)

    if current:
        chunks.append(current)
    return chunks


def _get_reference_audio():
    global _REFERENCE_AUDIO
    if _REFERENCE_AUDIO and Path(_REFERENCE_AUDIO).is_file():
        return _REFERENCE_AUDIO

    repo_id = os.environ.get("CHATTERBOX_REFERENCE_REPO", "").strip()
    filename = os.environ.get("CHATTERBOX_REFERENCE_FILENAME", "voice-reference.wav").strip()
    token = os.environ.get("HF_TOKEN", "").strip()
    if not repo_id or not token:
        raise RuntimeError(
            "Configure CHATTERBOX_REFERENCE_REPO (a private Hugging Face dataset) "
            "and the HF_TOKEN GitHub Actions secret before enabling Chatterbox."
        )

    try:
        from huggingface_hub import hf_hub_download
        _REFERENCE_AUDIO = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            token=token,
        )
    except Exception as exc:
        raise RuntimeError(
            "Unable to download the private Chatterbox reference audio from Hugging Face. "
            "Check HF_TOKEN access and CHATTERBOX_REFERENCE_REPO/CHATTERBOX_REFERENCE_FILENAME."
        ) from exc
    return _REFERENCE_AUDIO


def _get_client():
    global _CLIENT
    if _CLIENT is None:
        space = os.environ.get("CHATTERBOX_SPACE", SPACE_DEFAULT).strip()
        token = os.environ.get("HF_TOKEN", "").strip() or None
        try:
            from gradio_client import Client
            _CLIENT = Client(space, hf_token=token, verbose=False)
        except Exception as exc:
            raise RuntimeError(
                f"Unable to connect to the free Chatterbox Space {space}. "
                "The shared ZeroGPU Space may be sleeping, busy or temporarily unavailable."
            ) from exc
    return _CLIENT


def _write_audio_result(result, destination):
    """Normalize Gradio Audio outputs (filepath or (sample_rate, numpy array)) to WAV."""
    if isinstance(result, list) and len(result) == 1:
        result = result[0]

    if isinstance(result, dict):
        result = result.get("path") or result.get("name") or result.get("url")

    if isinstance(result, (str, Path)):
        source = Path(result)
        if not source.is_file():
            raise RuntimeError("Chatterbox Space returned an audio path that is not available locally.")
        shutil.copyfile(source, destination)
        return

    if isinstance(result, tuple) and len(result) == 2:
        sample_rate, samples = result
        if not isinstance(sample_rate, (int, np.integer)):
            raise RuntimeError("Chatterbox returned an unsupported audio sample-rate value.")
        samples = np.asarray(samples).squeeze()
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        if samples.ndim != 1 or samples.size == 0:
            raise RuntimeError("Chatterbox returned empty or unsupported audio samples.")
        samples = np.clip(samples, -1.0, 1.0)
        pcm = (samples * 32767.0).astype("<i2")
        with wave.open(str(destination), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(int(sample_rate))
            wav.writeframes(pcm.tobytes())
        return

    raise RuntimeError(f"Chatterbox returned an unsupported audio result: {type(result).__name__}")


def _join_wav_parts(parts, output_path, pause_seconds=0.16):
    if not parts:
        raise RuntimeError("Chatterbox produced no audio segments.")
    with wave.open(str(parts[0]), "rb") as first:
        params = first.getparams()
    frames = []
    for part in parts:
        with wave.open(str(part), "rb") as wav:
            current = wav.getparams()
            if (current.nchannels, current.sampwidth, current.framerate, current.comptype) != (
                params.nchannels, params.sampwidth, params.framerate, params.comptype
            ):
                raise RuntimeError("Chatterbox returned inconsistent audio formats between text chunks.")
            frames.append(wav.readframes(wav.getnframes()))

    silence_frames = int(params.framerate * pause_seconds)
    silence = b"\x00" * silence_frames * params.nchannels * params.sampwidth
    with wave.open(str(output_path), "wb") as output:
        output.setparams(params)
        for index, audio_frames in enumerate(frames):
            if index:
                output.writeframes(silence)
            output.writeframes(audio_frames)


def synthesize(text, language, output_path, seed=7):
    """Synthesize Hindi or English using the user's private reference voice sample."""
    if language not in {"hi", "en"}:
        raise ValueError("DigvijayEconLab Chatterbox supports only the configured hi/en narration path.")
    chunks = split_text(text)
    reference_audio = _get_reference_audio()
    client = _get_client()
    api_name = os.environ.get("CHATTERBOX_API_NAME", API_DEFAULT)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="digvijay-chatterbox-") as tmp:
        temp = Path(tmp)
        parts = []
        for index, chunk in enumerate(chunks):
            try:
                from gradio_client import handle_file
                result = client.predict(
                    chunk,
                    handle_file(reference_audio),
                    language,
                    0.5,             # exaggeration: neutral
                    0.8,             # temperature
                    int(seed) + index,
                    0.5,             # CFG / pace
                    api_name=api_name,
                )
            except Exception as exc:
                raise RuntimeError(
                    "Chatterbox generation failed. The free Hugging Face Space may be queued, "
                    "sleeping, rate-limited or temporarily unavailable. No placeholder voice "
                    "will be silently substituted when Chatterbox is explicitly enabled."
                ) from exc
            part_path = temp / f"part-{index:03d}.wav"
            _write_audio_result(result, part_path)
            parts.append(part_path)

        _join_wav_parts(parts, output_path)

    return {
        "path": str(output_path),
        "language": language,
        "chunks": len(chunks),
        "provider": "Chatterbox Multilingual V3 (Hugging Face ZeroGPU Space)",
        "voice_clone_used": True,
    }
