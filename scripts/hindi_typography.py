"""Reliable Devanagari font discovery and shaping for Pillow renderers."""
import subprocess
from pathlib import Path
from PIL import ImageFont, features

def find_hindi_font():
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{family}\\n%{file}", "Noto Sans Devanagari:lang=hi"],
            check=True, capture_output=True, text=True,
        ).stdout.strip().splitlines()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Fontconfig is required to locate a Hindi-capable Devanagari font.") from exc
    if len(result) < 2 or "Noto Sans Devanagari" not in result[0]:
        raise RuntimeError("Noto Sans Devanagari is missing or Fontconfig selected a fallback.")
    font_path = Path(result[1])
    if not font_path.is_file():
        raise RuntimeError(f"Resolved Devanagari font file does not exist: {font_path}")
    return str(font_path)

def load_hindi_font(font_path, size):
    if not features.check_feature("raqm"):
        raise RuntimeError("Pillow lacks libraqm; proper Devanagari shaping is unavailable.")
    font = ImageFont.truetype(str(font_path), size=size, layout_engine=ImageFont.Layout.RAQM)
    if font.getmask("हिन्दी अर्थशास्त्र").getbbox() is None:
        raise RuntimeError("Devanagari font produced an empty glyph mask.")
    return font
