"""Render consistent 16:9 DigvijayEconLab thumbnails using Pillow only.

No stock images, logos, third-party artwork or external image APIs are used.
"""
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.hindi_typography import find_hindi_font, load_hindi_font

WIDTH, HEIGHT = 1280, 720
PALETTES = [
    ((9, 24, 54), (24, 72, 126), (255, 194, 82)),
    ((15, 31, 58), (40, 89, 130), (93, 208, 218)),
    ((24, 31, 64), (72, 65, 132), (255, 191, 105)),
    ((20, 34, 57), (44, 86, 123), (156, 207, 255)),
    ((9, 35, 59), (20, 100, 130), (255, 191, 92)),
    ((29, 32, 55), (93, 63, 95), (255, 197, 110)),
    ((9, 39, 58), (25, 91, 105), (111, 216, 191)),
    ((21, 41, 71), (51, 92, 133), (255, 207, 102)),
    ((15, 43, 55), (39, 95, 88), (176, 220, 149)),
    ((33, 31, 55), (91, 60, 83), (255, 194, 110)),
]


def find_font(family, candidates):
    try:
        found = subprocess.run(
            ["fc-match", "-f", "%{file}", family],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if found and Path(found).is_file():
            return found
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError(f"Required font family is not installed: {family}")


def wrap_lines(draw, text, font, max_width, max_lines=3):
    words = re.sub(r"\s+", " ", str(text or "")).strip().split()
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


def draw_economics_motif(draw, unit, accent):
    """Draw original abstract chart marks; no external imagery is used."""
    x0, y0, x1, y1 = 850, 175, 1190, 575
    draw.rounded_rectangle((x0, y0, x1, y1), radius=38, fill=(255, 255, 255, 18), outline=accent, width=4)
    draw.line((x0 + 46, y1 - 58, x1 - 36, y1 - 58), fill=(220, 235, 248), width=4)
    draw.line((x0 + 46, y1 - 58, x0 + 46, y0 + 58), fill=(220, 235, 248), width=4)
    heights = [112, 178, 138, 242, 198]
    for idx, height in enumerate(heights):
        bx = x0 + 78 + idx * 54
        draw.rounded_rectangle((bx, y1 - 62 - height, bx + 30, y1 - 62), radius=8,
                               fill=accent if idx == unit % 5 else (105, 170, 210))
    points = []
    for idx, value in enumerate([0.8, 0.64, 0.72, 0.40, 0.48, 0.24]):
        px = x0 + 48 + idx * 54
        py = y0 + 85 + int(value * 230)
        points.append((px, py))
    draw.line(points, fill=(255, 255, 255), width=7, joint="curve")
    for px, py in points:
        draw.ellipse((px - 7, py - 7, px + 7, py + 7), fill=accent)


def render_one(item, output_path, font_regular, font_bold, hindi_font):
    unit = int(item["unit"])
    if not 1 <= unit <= 10:
        raise ValueError(f"Unit number is outside 1–10: {unit}")
    palette = PALETTES[unit - 1]
    base, secondary, accent = palette
    image = Image.new("RGB", (WIDTH, HEIGHT), base)
    draw = ImageDraw.Draw(image)

    # Broad geometric panels provide contrast without distracting from the text.
    draw.rectangle((0, 0, WIDTH, 16), fill=accent)
    draw.ellipse((890, -190, 1370, 285), fill=secondary)
    draw.ellipse((1030, 485, 1460, 905), fill=secondary)
    draw.rounded_rectangle((44, 42, 1236, 678), radius=34, outline=(105, 157, 205), width=3)

    brand_font = ImageFont.truetype(font_bold, 27)
    eyebrow_font = ImageFont.truetype(font_regular, 23)
    badge_font = ImageFont.truetype(font_bold, 24)
    main_font = load_hindi_font(hindi_font, 56)
    unit_font = ImageFont.truetype(font_bold, 34)
    footer_font = ImageFont.truetype(font_regular, 23)

    draw.text((82, 78), "DIGVIJAYECONLAB", font=brand_font, fill=(129, 220, 255))
    draw.text((82, 124), "UGC NET  •  MPPSC ASSISTANT PROFESSOR", font=eyebrow_font, fill=(228, 237, 247))
    draw.rounded_rectangle((82, 190, 300, 244), radius=17, fill=accent)
    draw.text((102, 198), f"UNIT {unit:02d}", font=badge_font, fill=(18, 31, 50))

    headline = item.get("thumbnail_text_options") or []
    headline = headline[0] if headline and isinstance(headline[0], str) else item.get("video_title", "")
    headline = headline.strip()
    if not headline:
        raise ValueError(f"Unit {unit} has no thumbnail headline.")
    lines = wrap_lines(draw, headline, main_font, 690, max_lines=3)
    y = 285
    for line in lines:
        draw.text((82, y), line, font=main_font, fill=(255, 255, 255), stroke_width=1,
                  stroke_fill=(9, 24, 54))
        bbox = draw.textbbox((82, y), line, font=main_font)
        y += bbox[3] - bbox[1] + 14

    unit_name = str(item.get("playlist_title", "")).split("|")[1].strip() if "|" in str(item.get("playlist_title", "")) else "Economics"
    sub_font = load_hindi_font(hindi_font, 28)
    sub_lines = wrap_lines(draw, unit_name + "  |  अर्थशास्त्र", sub_font, 690, max_lines=2)
    y = max(y + 18, 500)
    for line in sub_lines:
        draw.text((82, y), line, font=sub_font, fill=accent)
        y += 42

    draw_economics_motif(draw, unit, accent)
    draw.text((82, 620), "BILINGUAL LESSON  •  HINDI + ENGLISH", font=footer_font, fill=(218, 231, 243))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="JPEG", quality=91, optimize=True, progressive=True)
    with Image.open(output_path) as rendered:
        if rendered.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"Thumbnail dimension validation failed: {output_path}")
        rendered.verify()
    if output_path.stat().st_size > 2_000_000:
        raise RuntimeError(f"Thumbnail exceeds YouTube's 2 MB target: {output_path}")
    return {"unit": unit, "file": str(output_path), "width": WIDTH, "height": HEIGHT,
            "bytes": output_path.stat().st_size}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Render ten original DigvijayEconLab YouTube thumbnails.")
    parser.add_argument("seo_json", nargs="?", default="output/seo")
    parser.add_argument("--output", default="output/thumbnails")
    args = parser.parse_args()

    source = Path(args.seo_json)
    if source.is_dir():
        candidates = sorted(source.glob("*-seo-metadata.json"))
        if not candidates:
            raise SystemExit(f"No SEO metadata JSON found in {source}")
        source = candidates[-1]
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) != 10:
        raise SystemExit("Thumbnail input must contain exactly ten unit SEO records.")
    by_unit = {int(item.get("unit", 0)): item for item in data}
    if set(by_unit) != set(range(1, 11)):
        raise SystemExit("SEO metadata must contain units 1 through 10 exactly once.")

    font_regular = find_font("DejaVu Sans", ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"])
    font_bold = find_font("DejaVu Sans:style=Bold", ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"])
    hindi_font = find_hindi_font()
    output_dir = Path(args.output)
    reports = [
        render_one(by_unit[unit], output_dir / f"unit-{unit:02d}-thumbnail.jpg",
                   font_regular, font_bold, hindi_font)
        for unit in range(1, 11)
    ]
    expected_paths = [output_dir / f"unit-{unit:02d}-thumbnail.jpg" for unit in range(1, 11)]
    invalid = [str(path) for path in expected_paths if not path.is_file() or path.stat().st_size == 0]
    if invalid or len(reports) != 10 or {item["unit"] for item in reports} != set(range(1, 11)):
        raise RuntimeError(f"Thumbnail batch is incomplete; missing or invalid outputs: {invalid}")

    report_path = output_dir / "thumbnail-manifest.json"
    report_path.write_text(json.dumps({"status": "rendered", "count": 10, "thumbnails": reports},
                                      ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({"status": "rendered", "count": len(reports), "output": str(output_dir)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
