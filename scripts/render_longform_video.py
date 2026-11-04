"""Render one featured bilingual economics lesson as a 16:9 narrated MP4.

The renderer uses only generated typography slides, the checked lesson draft, FFmpeg,
and either the configured free Chatterbox reference voice or a clearly marked eSpeak
placeholder. It adds no music or third-party media.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from narration import synthesize_audio_batch

WIDTH, HEIGHT = 1920, 1080
MAX_GROUP_CHARS = 780
PALETTES = [
    ((8, 22, 48), (21, 58, 95), (255, 196, 90)),
    ((10, 29, 53), (31, 75, 104), (104, 214, 220)),
    ((20, 27, 59), (56, 57, 101), (255, 188, 101)),
    ((16, 34, 58), (44, 79, 111), (155, 206, 255)),
    ((9, 35, 56), (20, 83, 111), (255, 191, 93)),
    ((26, 30, 54), (78, 55, 81), (255, 194, 107)),
    ((8, 39, 56), (24, 78, 92), (111, 216, 191)),
    ((18, 37, 66), (46, 81, 117), (255, 207, 103)),
    ((13, 41, 52), (37, 87, 80), (176, 220, 149)),
    ((30, 28, 53), (81, 56, 76), (255, 194, 110)),
]
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")
VERIFY_RE = re.compile(r"\[(?:HUMAN\s+)?VERIFY\b[^]]*\]", re.IGNORECASE)


def find_font(family, candidates):
    try:
        found = subprocess.run(["fc-match", "-f", "%{file}", family],
                               check=True, capture_output=True, text=True).stdout.strip()
        if found and Path(found).is_file():
            return found
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError(f"Required font is not installed: {family}")


def plain_text(value):
    value = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[*_\`~]", "", value)
    value = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()

def language_for(text):
    devanagari = len(re.findall(r"[\u0900-\u097f]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if devanagari and devanagari >= max(4, latin * 0.12):
        return "hi"
    return "en"


def parse_lesson(markdown):
    """Extract readable paragraphs; omit tables, code blocks and source-only notes."""
    sections = []
    heading = "Lesson overview"
    paragraphs = []
    paragraph_lines = []
    in_code = False
    skip_section = False

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            text = plain_text(" ".join(paragraph_lines))
            if text and len(text) >= 12 and not VERIFY_RE.search(text):
                paragraphs.append(text)
            paragraph_lines = []

    def flush_section():
        flush_paragraph()
        if paragraphs:
            sections.append((heading, paragraphs[:]))
            paragraphs.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("```") or line.startswith("~~~"):
            flush_paragraph()
            in_code = not in_code
            continue
        if in_code:
            continue
        if not line:
            flush_paragraph()
            continue
        match = HEADING_RE.match(line)
        if match:
            flush_section()
            heading = plain_text(match.group(1))
            normalized = heading.casefold()
            skip_section = any(term in normalized for term in (
                "source note", "verification note", "reference", "bibliography"
            ))
            continue
        if skip_section or line.startswith("|") or re.fullmatch(r"[-:| ]{3,}", line):
            continue
        if line.startswith(">"):
            line = line.lstrip("> ")
        if re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)", line):
            flush_paragraph()
        paragraph_lines.append(line)

    flush_section()
    if not sections:
        raise ValueError("No narratable lesson content was found in the corrected Markdown.")
    return sections


def group_sections(sections, max_chars=MAX_GROUP_CHARS):
    """Group paragraphs by heading and language without dropping lesson content."""
    groups = []
    for heading, paragraphs in sections:
        current, current_len, current_language = [], 0, None
        for paragraph in paragraphs:
            paragraph_language = language_for(paragraph)
            language_changed = current and paragraph_language != current_language
            would_overflow = current and current_len + len(paragraph) > max_chars
            if language_changed or would_overflow:
                groups.append({
                    "heading": heading,
                    "paragraphs": current,
                    "language": current_language,
                })
                current, current_len = [], 0
            if not current:
                current_language = paragraph_language
            current.append(paragraph)
            current_len += len(paragraph)
        if current:
            groups.append({
                "heading": heading,
                "paragraphs": current,
                "language": current_language,
            })
    if not groups:
        raise ValueError("The corrected script did not contain usable paragraph groups.")
    if len(groups) > 36:
        raise ValueError(
            f"The lesson creates {len(groups)} narration groups; simplify the video draft "
            "or split the lesson before rendering. No content has been discarded."
        )
    return groups

def wrap_lines(draw, text, font, max_width, max_lines=5):
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
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1].rstrip() + "…"
    return lines


def draw_slide(group, index, total, unit, unit_name, topic, font_regular, font_bold, hindi_font, path):
    base, secondary, accent = PALETTES[(unit - 1) % 10]
    image = Image.new("RGB", (WIDTH, HEIGHT), base)
    draw = ImageDraw.Draw(image)
    draw.ellipse((1420, -300, 2140, 420), fill=secondary)
    draw.ellipse((1500, 760, 2180, 1440), fill=secondary)
    draw.rounded_rectangle((54, 54, WIDTH - 54, HEIGHT - 54), radius=38,
                           outline=(87, 145, 190), width=3)
    brand = ImageFont.truetype(font_bold, 30)
    eyebrow = ImageFont.truetype(font_regular, 25)
    title_font = ImageFont.truetype(hindi_font, 54)
    body_font = ImageFont.truetype(hindi_font, 42)
    footer = ImageFont.truetype(font_regular, 24)

    draw.text((104, 94), "DIGVIJAYECONLAB", font=brand, fill=(120, 215, 255))
    draw.text((104, 144), f"UGC NET ECONOMICS  •  MPPSC ASSISTANT PROFESSOR  •  UNIT {unit:02d}",
              font=eyebrow, fill=(224, 235, 246))
    draw.text((WIDTH - 240, 104), f"{index + 1:02d} / {total:02d}", font=eyebrow, fill=accent)

    title_lines = wrap_lines(draw, group["heading"] or topic, title_font, WIDTH - 260, max_lines=2)
    y = 260
    for line in title_lines:
        draw.text((104, y), line, font=title_font, fill=(255, 255, 255))
        y += 76

    draw.rounded_rectangle((104, y + 12, WIDTH - 104, y + 17), radius=2, fill=accent)
    y += 62
    show_demand_graph = any(
        "demand" in str(value).casefold() or "मांग" in str(value)
        for value in (group.get("heading", ""), topic)
    )
    display = []
    for paragraph in group["paragraphs"]:
        # Keep each slide readable; the complete paragraph remains in narration.
        sentences = re.split(r"(?<=[.!?।॥])\s+", paragraph)
        display.append(sentences[0] if sentences else paragraph)
    text_width = 1040 if show_demand_graph else WIDTH - 250
    for point in display[:4]:
        lines = wrap_lines(draw, point, body_font, text_width, max_lines=3)
        draw.ellipse((112, y + 16, 130, y + 34), fill=accent)
        for line in lines:
            draw.text((160, y), line, font=body_font, fill=(239, 245, 251))
            bbox = draw.textbbox((160, y), line, font=body_font)
            y += bbox[3] - bbox[1] + 12
        y += 26
        if y > 820:
            break

    if y < 840:
        sub = ImageFont.truetype(hindi_font, 30)
        draw.text((104, 875), f"{unit_name}  |  {topic}", font=sub, fill=accent)
    if show_demand_graph:
        draw_demand_curve(draw, accent)
    draw.text((104, 985), "BILINGUAL ECONOMICS LESSON  •  हिंदी + ENGLISH", font=footer,
              fill=(205, 222, 237))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def synthesize_audio(text, language, output_path, seed, chatterbox_enabled, espeak):
    if chatterbox_enabled:
        from chatterbox_tts import synthesize
        return synthesize(text, language, output_path, seed=seed)
    voice = "hi" if language == "hi" else "en-us"
    command = [espeak, "-v", voice, "-s", "145", "-w", str(output_path), text]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return {"path": str(output_path), "provider": f"eSpeak NG ({voice})", "voice_clone_used": False}


def run_ffmpeg(command, label):
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing FFmpeg while {label}.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "")[-2000:]
        raise RuntimeError(f"FFmpeg failed while {label}: {detail}") from exc

def render_voice_policy(chatterbox_enabled, providers, has_unresolved_markers):
    """Return an explicit safe status for production voice or preview narration."""
    voice_clone_used = bool(
        chatterbox_enabled and providers and all("Chatterbox" in provider for provider in providers)
    )
    if has_unresolved_markers:
        return {
            "voice_clone_used": voice_clone_used,
            "audit_status": "blocked",
            "upload_eligible": False,
            "preview_only": not voice_clone_used,
        }
    if voice_clone_used:
        return {
            "voice_clone_used": True,
            "audit_status": "pass",
            "upload_eligible": True,
            "preview_only": False,
        }
    return {
        "voice_clone_used": False,
        "audit_status": "preview",
        "upload_eligible": False,
        "preview_only": True,
    }


def audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise RuntimeError("Narration audio duration is invalid.")
    return duration


def caption_chunks(text, max_chars=88):
    chunks, current = [], ""
    for word in str(text).split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def srt_timestamp(seconds):
    ms = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_group_srt(text, duration, path):
    chunks = caption_chunks(text)
    total = sum(len(item) for item in chunks) or 1
    cursor, entries = 0.0, []
    for index, chunk in enumerate(chunks):
        end = duration if index == len(chunks) - 1 else cursor + duration * len(chunk) / total
        words, lines, line = chunk.split(), [], ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if line and len(candidate) > 44:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        entries.append(
            f"{index + 1}\n{srt_timestamp(cursor)} --> {srt_timestamp(end)}\n"
            + "\n".join(lines[:2])
        )
        cursor = end
    Path(path).write_text("\n\n".join(entries) + "\n", encoding="utf-8")


def escape_filter_path(path):
    return str(Path(path).resolve()).replace("\\\\", "/").replace(":", "\\\\:").replace("'", "\\\\'")


def draw_demand_curve(draw, accent):
    left, top, right, bottom = 1260, 350, 1780, 790
    draw.rounded_rectangle((left, top, right, bottom), radius=24,
                           fill=(13, 35, 62), outline=accent, width=3)
    x0, y0, x1, y1 = left + 78, bottom - 72, right - 38, top + 52
    axis = (225, 237, 248)
    draw.line((x0, y0, x1, y0), fill=axis, width=5)
    draw.line((x0, y0, x0, y1), fill=axis, width=5)
    draw.polygon([(x1, y0), (x1 - 18, y0 - 10), (x1 - 18, y0 + 10)], fill=axis)
    draw.polygon([(x0, y1), (x0 - 10, y1 + 18), (x0 + 10, y1 + 18)], fill=axis)
    points = [(x0 + 55 + step / 30 * 350, y1 + 38 + step / 30 * 245) for step in range(31)]
    draw.line(points, fill=accent, width=9, joint="curve")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 27)
    draw.text((left + 24, top + 18), "LAW OF DEMAND", font=font, fill=(255, 255, 255))
    draw.text((x0 - 30, y1 - 8), "P", font=font, fill=(255, 255, 255))
    draw.text((x1 - 5, y0 + 14), "Q", font=font, fill=(255, 255, 255))
    draw.text((points[13][0] + 15, points[13][1] - 38), "D", font=font, fill=accent)


def ffprobe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    video = next((x for x in data.get("streams", []) if x.get("codec_type") == "video"), None)
    audio = [x for x in data.get("streams", []) if x.get("codec_type") == "audio"]
    if not video or not audio:
        raise RuntimeError("Long-form MP4 must contain both video and narration audio.")
    if (video.get("width"), video.get("height")) != (WIDTH, HEIGHT):
        raise RuntimeError("Long-form video must be 1920x1080 landscape.")
    if video.get("codec_name") != "h264":
        raise RuntimeError("Long-form video must use H.264.")
    duration = float(data.get("format", {}).get("duration", 0))
    if duration <= 0:
        raise RuntimeError("Long-form video duration is invalid.")
    return {"duration_seconds": round(duration, 2), "width": WIDTH, "height": HEIGHT,
            "video_codec": "h264", "audio_streams": len(audio)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Render one featured 16:9 economics lesson.")
    parser.add_argument("manifest", nargs="?", default="output/daily_manifest.json")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root)
    manifest = json.loads((root / args.manifest).read_text(encoding="utf-8"))
    date = manifest["publication_date"]
    focus = manifest["short_focus"]
    unit = int(focus["unit"])
    topic = str(focus["topic"])
    unit_name = str(focus["unit_name"])
    script_matches = sorted((root / "output/corrected_scripts").glob(f"unit-{unit:02d}-*.md"))
    if len(script_matches) != 1:
        raise SystemExit(f"Expected one corrected script for featured Unit {unit}; found {len(script_matches)}.")
    script_path = script_matches[0]
    markdown = script_path.read_text(encoding="utf-8")
    review_path = root / "output/reviews" / f"{script_path.stem}-quality-review.md"
    if not review_path.is_file():
        raise SystemExit("Long-form render blocked: corrected academic review report is missing.")
    review_text = review_path.read_text(encoding="utf-8")
    verdict = ""
    review_lines = review_text.splitlines()
    for line_index, line in enumerate(review_lines):
        if "overall verdict" in line.casefold():
            verdict = next((entry.strip() for entry in review_lines[line_index + 1:] if entry.strip()), "")
            break
    if not any(word in verdict.casefold() for word in ("ready", "approved", "pass")):
        raise SystemExit("Long-form render blocked: corrected academic review has no explicit READY/APPROVED verdict.")
    if VERIFY_RE.search(markdown):
        raise SystemExit("Long-form render blocked: unresolved [VERIFY] marker exists in corrected lesson.")
    if len(markdown) < 1200:
        raise SystemExit("Long-form render blocked: corrected lesson is unexpectedly short.")
    sections = parse_lesson(markdown)
    groups = group_sections(sections)

    seo_path = root / "output/seo" / f"{date}-seo-metadata.json"
    seo_rows = json.loads(seo_path.read_text(encoding="utf-8"))
    seo = next((item for item in seo_rows if int(item.get("unit", 0)) == unit), None)
    if not seo:
        raise SystemExit(f"SEO metadata missing for featured Unit {unit}.")
    title = str(seo.get("video_title") or f"{unit_name}: {topic} | DigvijayEconLab")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if not ffmpeg or not ffprobe_bin:
        raise SystemExit("FFmpeg and FFprobe must be installed.")
    chatterbox_enabled = os.environ.get("CHATTERBOX_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    if not chatterbox_enabled and not espeak:
        raise SystemExit("Enable Chatterbox or install eSpeak NG for preview narration.")

    font_regular = find_font("DejaVu Sans", ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    font_bold = find_font("DejaVu Sans:style=Bold", ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"])
    hindi_font = find_font("Noto Sans Devanagari", ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"])

    output_dir = root / "output/longform"
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", topic.casefold()).strip("-")[:48] or f"unit-{unit:02d}"
    final_path = output_dir / f"{date}-unit-{unit:02d}-{slug}.mp4"

    preview_fallback = os.environ.get("CHATTERBOX_PREVIEW_FALLBACK", "").strip().lower() in {"1", "true", "yes"}
    chatterbox_synthesize = None
    if chatterbox_enabled:
        from chatterbox_tts import synthesize as chatterbox_synthesize

    providers, segments = [], []
    with tempfile.TemporaryDirectory(prefix="digvijay-longform-") as tmp:
        temp = Path(tmp)
        render_specs = []
        narration_items = []
        for index, group in enumerate(groups):
            paragraph_text = " ".join(group["paragraphs"])
            language = group.get("language") or language_for(paragraph_text)
            image_path = temp / f"slide-{index:02d}.png"
            audio_path = temp / f"narration-{index:02d}.wav"
            segment_path = temp / f"segment-{index:02d}.mp4"
            subtitle_path = temp / f"captions-{index:02d}.srt"
            draw_slide(group, index, len(groups), unit, unit_name, topic,
                       font_regular, font_bold, hindi_font, image_path)
            narration_items.append({
                "text": paragraph_text,
                "language": language,
                "path": str(audio_path),
                "seed": 9100 + index,
                "speed": 145,
            })
            render_specs.append({
                "image_path": image_path,
                "audio_path": audio_path,
                "segment_path": segment_path,
                "subtitle_path": subtitle_path,
                "paragraph_text": paragraph_text,
                "index": index,
            })

        chatterbox_enabled, providers = synthesize_audio_batch(
            narration_items,
            chatterbox_enabled=chatterbox_enabled,
            allow_preview_fallback=preview_fallback,
            espeak_binary=espeak,
            chatterbox_synthesize=chatterbox_synthesize,
        )

        for spec in render_specs:
            index = spec["index"]
            write_group_srt(
                spec["paragraph_text"],
                audio_duration(spec["audio_path"]),
                spec["subtitle_path"],
            )
            subtitle_filter = (
                f"zoompan=z='min(zoom+0.00035,1.035)':d=1:s={WIDTH}x{HEIGHT}:fps=30,"
                f"subtitles='{escape_filter_path(spec['subtitle_path'])}':"
                "force_style='FontName=Noto Sans Devanagari,FontSize=22,"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00102030,"
                "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=52'"
            )
            run_ffmpeg([
                ffmpeg, "-y", "-loop", "1", "-framerate", "30", "-i", str(spec["image_path"]),
                "-i", str(spec["audio_path"]), "-vf", subtitle_filter,
                "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-shortest", "-movflags", "+faststart", str(spec["segment_path"]),
            ], f"rendering lesson section {index + 1} with motion and captions")
            segments.append(spec["segment_path"])

        concat_file = temp / "segments.txt"
        concat_file.write_text(
            "".join(f"file '{path.as_posix()}'\\n" for path in segments),
            encoding="utf-8",
        )
        run_ffmpeg([
            ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c", "copy", "-movflags", "+faststart", str(final_path),
        ], "assembling the complete long-form lesson")

    technical = ffprobe(final_path)
    policy = render_voice_policy(chatterbox_enabled, providers, bool(VERIFY_RE.search(markdown)))
    voice_clone_used = policy["voice_clone_used"]
    report = {
        "status": "rendered",
        **policy,
        "narration_mode": "production" if voice_clone_used else "preview",
        "audit_status": policy["audit_status"],
        "publication_date": date,
        "unit": unit,
        "topic": topic,
        "video": str(final_path),
        "title": title,
        "format": "1920x1080 landscape",
        "voice_providers": sorted(set(providers)),
        "voice_clone_used": voice_clone_used,
        "voice_reference_stored_in_repository": False,
        "music": "none",
        "review_required": True,
        "technical": technical,
        "limitations": [
            "Demand-focused lessons include an original downward-sloping demand-curve teaching diagram.",
            "Slides use subtle Ken Burns motion and burned-in phrase-timed captions; timing is estimated from narration length, not word-level forced alignment.",
            "The renderer uses original typography slides and diagrams; it does not add stock footage or music.",
            "Review slide pacing, pronunciation, equations, diagrams, captions and academic accuracy before publication.",
            "A successful render is not a copyright or academic-quality certification.",
        ],
    }
    report_path = output_dir / f"{date}-longform-render.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
