"""Render a bilingual 9:16 Short draft using Chatterbox or eSpeak placeholder narration.

Chatterbox is the free reference-voice provider when explicitly enabled. The private
reference recording is fetched at runtime and never stored in this repository.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    from .narration import synthesize_audio_batch
except ImportError:
    from narration import synthesize_audio_batch

WIDTH, HEIGHT = 1080, 1920


def find_font(family, fallbacks):
    try:
        found = subprocess.run(
            ["fc-match", "-f", "%{file}", family],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if found and Path(found).is_file():
            return found
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    for candidate in fallbacks:
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError(f"Required font not found: {family}")


def wrap_text(draw, text, font, max_width):
    words = str(text).split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def draw_wrapped(draw, text, xy, font, fill, max_width, line_gap=18, max_lines=4):
    x, y = xy
    lines = wrap_text(draw, text, font, max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        if lines:
            lines[-1] = lines[-1].rstrip(" .") + "…"
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill, stroke_width=0)
        bbox = draw.textbbox((x, y), line, font=font)
        y += bbox[3] - bbox[1] + line_gap
    return y


def make_slide(scene, index, total, unit, english_font_path, hindi_font_path, path):
    image = Image.new("RGB", (WIDTH, HEIGHT), (10, 22, 45))
    pixels = image.load()
    for y in range(HEIGHT):
        mix = y / HEIGHT
        r = int(10 + 13 * mix)
        g = int(22 + 24 * mix)
        b = int(45 + 42 * mix)
        for x in range(WIDTH):
            pixels[x, y] = (r, g, b)

    draw = ImageDraw.Draw(image)
    english_bold = ImageFont.truetype(english_font_path, 40)
    english_title = ImageFont.truetype(english_font_path, 62)
    english_body = ImageFont.truetype(english_font_path, 48)
    hindi_title = ImageFont.truetype(hindi_font_path, 54)
    hindi_body = ImageFont.truetype(hindi_font_path, 42)
    small = ImageFont.truetype(english_font_path, 30)

    margin = 84
    draw.rounded_rectangle((54, 70, WIDTH - 54, HEIGHT - 72), radius=44, outline=(90, 160, 220), width=4)
    draw.text((margin, 125), "DIGVIJAYECONLAB", font=english_bold, fill=(110, 205, 255))
    draw.text((margin, 195), f"UNIT {unit:02d}  •  ECONOMICS", font=small, fill=(215, 225, 238))
    draw.text((WIDTH - 190, 195), f"{index + 1}/{total}", font=small, fill=(215, 225, 238))

    y = 390
    y = draw_wrapped(draw, scene["screen_title_en"], (margin, y), english_title, (255, 255, 255), WIDTH - 2 * margin, 18, 3)
    y += 40
    y = draw_wrapped(draw, scene["screen_title_hi"], (margin, y), hindi_title, (255, 205, 110), WIDTH - 2 * margin, 20, 3)
    y += 70
    draw.rounded_rectangle((margin, y, WIDTH - margin, y + 4), radius=2, fill=(75, 170, 235))
    y += 68
    y = draw_wrapped(draw, scene["screen_text_en"], (margin, y), english_body, (235, 242, 250), WIDTH - 2 * margin, 20, 5)
    y += 60
    y = draw_wrapped(draw, scene["screen_text_hi"], (margin, y), hindi_body, (255, 229, 170), WIDTH - 2 * margin, 20, 5)

    footer = "UGC NET ECONOMICS  •  MPPSC ASSISTANT PROFESSOR"
    draw.text((margin, HEIGHT - 190), footer, font=small, fill=(185, 205, 230))
    draw.text((margin, HEIGHT - 130), "Learn • Understand • Practice", font=small, fill=(110, 205, 255))
    image.save(path, quality=94)


def run(command, label):
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing system tool while {label}: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "")[-1800:]
        raise RuntimeError(f"Failed while {label}: {detail}") from exc


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: render_short_video.py DAILY_MANIFEST.json")
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    date = manifest["publication_date"]
    source_json = Path("output/shorts") / f"{date}-short.json"
    if not source_json.is_file():
        raise SystemExit(f"Short scene JSON not found: {source_json}")
    data = json.loads(source_json.read_text(encoding="utf-8"))
    scenes = data.get("scenes", [])
    if not 4 <= len(scenes) <= 6:
        raise SystemExit("Short renderer requires four to six scenes.")

    tts = shutil.which("espeak-ng") or shutil.which("espeak")
    ffmpeg = shutil.which("ffmpeg")
    chatterbox_enabled = os.environ.get("CHATTERBOX_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    preview_fallback = os.environ.get("CHATTERBOX_PREVIEW_FALLBACK", "").strip().lower() in {"1", "true", "yes"}
    if not ffmpeg:
        raise SystemExit("This renderer requires ffmpeg.")
    if not chatterbox_enabled and not tts:
        raise SystemExit("Enable free Chatterbox or install eSpeak NG for preview narration.")
    if chatterbox_enabled:
        from chatterbox_tts import synthesize as chatterbox_synthesize
        print("Narration provider: free Chatterbox Multilingual V3.")
        if preview_fallback:
            print("Chatterbox fallback is enabled: quota/service failure will restart the complete Short using eSpeak preview audio.")
    else:
        chatterbox_synthesize = None
        print("WARNING: Using generic eSpeak placeholder narration; this is preview-only and not the owner's voice.")

    eng_font = find_font("DejaVu Sans", [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ])
    hi_font = find_font("Noto Sans Devanagari", [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    ])
    output_dir = Path("output/shorts")
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / f"{date}-digvijayeconlab-short.mp4"

    focus_unit = int(data["focus_unit"]["unit"])
    with tempfile.TemporaryDirectory(prefix="digvijay-short-") as tmp:
        temp = Path(tmp)
        scene_specs = []
        narration_items = []
        for i, scene in enumerate(scenes):
            image_path = temp / f"scene-{i:02d}.png"
            hindi_path = temp / f"scene-{i:02d}-hi.wav"
            english_path = temp / f"scene-{i:02d}-en.wav"
            audio_path = temp / f"scene-{i:02d}-mix.wav"
            video_path = temp / f"scene-{i:02d}.mp4"

            make_slide(scene, i, len(scenes), focus_unit, eng_font, hi_font, image_path)
            voice_hi = scene["voiceover_hi"].strip()
            voice_en = scene["voiceover_en"].strip()
            if i == len(scenes) - 1:
                voice_hi += " " + data.get("outro_hi", "")
                voice_en += " " + data.get("outro_en", "")
            narration_items.extend([
                {"text": voice_hi, "language": "hi", "path": str(hindi_path), "seed": 7100 + i, "speed": 142},
                {"text": voice_en, "language": "en", "path": str(english_path), "seed": 7200 + i, "speed": 152},
            ])
            scene_specs.append({
                "image_path": image_path,
                "hindi_path": hindi_path,
                "english_path": english_path,
                "audio_path": audio_path,
                "video_path": video_path,
            })

        voice_clone_used, voice_providers = synthesize_audio_batch(
            narration_items,
            chatterbox_enabled=chatterbox_enabled,
            allow_preview_fallback=preview_fallback,
            espeak_binary=tts,
            chatterbox_synthesize=chatterbox_synthesize,
        )
        voice_provider = (
            "Chatterbox Multilingual V3 (private reference voice)"
            if voice_clone_used
            else "eSpeak generic placeholder (PREVIEW ONLY; not the owner's voice)"
        )

        segments = []
        for spec in scene_specs:
            audio_path = spec["audio_path"]
            video_path = spec["video_path"]
            run([
                ffmpeg, "-y", "-i", str(spec["hindi_path"]), "-i", str(spec["english_path"]),
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[out]",
                "-map", "[out]", str(audio_path),
            ], "joining bilingual narration")
            run([
                ffmpeg, "-y", "-loop", "1", "-framerate", "30", "-i", str(spec["image_path"]),
                "-i", str(audio_path), "-c:v", "libx264", "-preset", "veryfast",
                "-tune", "stillimage", "-vf", "format=yuv420p", "-c:a", "aac",
                "-b:a", "128k", "-shortest", str(video_path),
            ], "rendering a vertical scene")
            segments.append(video_path)

        concat_list = temp / "segments.txt"
        concat_list.write_text(
            "".join(f"file '{path.as_posix()}'\n" for path in segments),
            encoding="utf-8",
        )
        run([
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart", str(final_path),
        ], "assembling the final Short MP4")

    report = {
        "video": str(final_path),
        "format": "1080x1920 vertical",
        "voice_provider": voice_provider,
        "voice_providers": sorted(set(voice_providers)),
        "voice_clone_used": voice_clone_used,
        "narration_mode": "production" if voice_clone_used else "preview",
        "preview_only": not voice_clone_used,
        "upload_eligible": voice_clone_used,
        "voice_reference_stored_in_repository": False,
        "music": "none",
        "review_required": True,
        "upload_block_reason": None if voice_clone_used else "Generic eSpeak narration is preview-only and is not the owner's voice.",
    }
    (output_dir / f"{date}-short-render.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Rendered Shorts draft: {final_path}")
    print(f"Voice provider: {voice_provider}")
    if not voice_clone_used:
        print("PREVIEW ONLY: this MP4 is not the owner's voice and is not upload-eligible.")
    print("Review voice likeness, Hindi/English pronunciation, factual claims, and pacing before publishing.")


if __name__ == "__main__":
    main()
