"""Generate one bilingual YouTube Short storyboard and one Community post draft."""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "short_title": {"type": "STRING"},
        "short_description": {"type": "STRING"},
        "scenes": {
            "type": "ARRAY",
            "minItems": 4,
            "maxItems": 6,
            "items": {
                "type": "OBJECT",
                "properties": {
                    "screen_title_en": {"type": "STRING"},
                    "screen_title_hi": {"type": "STRING"},
                    "screen_text_en": {"type": "STRING"},
                    "screen_text_hi": {"type": "STRING"},
                    "voiceover_en": {"type": "STRING"},
                    "voiceover_hi": {"type": "STRING"},
                    "visual_direction": {"type": "STRING"},
                },
                "required": [
                    "screen_title_en", "screen_title_hi", "screen_text_en",
                    "screen_text_hi", "voiceover_en", "voiceover_hi",
                    "visual_direction",
                ],
            },
        },
        "outro_en": {"type": "STRING"},
        "outro_hi": {"type": "STRING"},
        "community_post": {"type": "STRING"},
        "poll_question": {"type": "STRING"},
        "poll_options": {
            "type": "ARRAY",
            "minItems": 2,
            "maxItems": 4,
            "items": {"type": "STRING"},
        },
        "pinned_comment": {"type": "STRING"},
        "hashtags": {
            "type": "ARRAY",
            "minItems": 3,
            "maxItems": 8,
            "items": {"type": "STRING"},
        },
    },
    "required": [
        "short_title", "short_description", "scenes", "outro_en",
        "outro_hi", "community_post", "poll_question", "poll_options",
        "pinned_comment", "hashtags",
    ],
}


def call_gemini(api_key, payload):
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise SystemExit(f"Gemini daily-asset generation failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Gemini daily-asset connection failed: {exc}") from exc


def validate(data):
    if not isinstance(data, dict):
        raise ValueError("Response root must be an object.")
    required_strings = [
        "short_title", "short_description", "outro_en", "outro_hi",
        "community_post", "poll_question", "pinned_comment",
    ]
    for key in required_strings:
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Missing or empty field: {key}")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 4 <= len(scenes) <= 6:
        raise ValueError("Short must contain between four and six scenes.")
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index} must be an object.")
        for key in [
            "screen_title_en", "screen_title_hi", "screen_text_en",
            "screen_text_hi", "voiceover_en", "voiceover_hi",
            "visual_direction",
        ]:
            if not isinstance(scene.get(key), str) or not scene[key].strip():
                raise ValueError(f"Scene {index} is missing {key}.")
    if not isinstance(data.get("poll_options"), list) or not 2 <= len(data["poll_options"]) <= 4:
        raise ValueError("Community poll must have two to four options.")
    if not all(isinstance(item, str) and item.strip() for item in data["poll_options"]):
        raise ValueError("Poll options must be non-empty strings.")
    if not isinstance(data.get("hashtags"), list) or not data["hashtags"]:
        raise ValueError("At least one hashtag is required.")
    return data


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: generate_daily_assets.py DAILY_MANIFEST.json")
    manifest_path = Path(sys.argv[1])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not configured.")

    topics = "\n".join(
        f"Unit {item['unit']}: {item['unit_name']} — {item['topic']}"
        for item in manifest["units"]
    )
    focus = manifest["short_focus"]
    system_prompt = """You create clear, accurate and original bilingual educational promotional content
for DigvijayEconLab, aimed at Economics exam aspirants in India.
Use only the supplied topic labels; do not invent data, exam questions, statistics, policy details,
citations, current facts, or textbook quotations.
Create one 45–60 second YouTube Short (vertical video storyboard) that teaches one useful idea
from the focus topic and naturally points viewers to the full unit lesson. It must be bilingual:
each scene contains English and Hindi on-screen text and separate English/Hindi voiceover.
Keep on-screen text short and readable, voiceover natural and concise, and use five scenes ideally.
The final scene should include DigvijayEconLab and a simple educational call to action.
No copyrighted characters, music, movie references, brand imitations or fake claims.
Also create one concise bilingual YouTube Community text post that previews today's ten lessons.
Create a relevant, non-leading poll with two to four short options. Do not claim the videos have
already been published. State that the lessons are today's learning plan/drafts if publication status
is not known. Return only JSON matching the response schema."""
    user_prompt = f"""Publication date: {manifest['publication_date']}
Brand: DigvijayEconLab
Today's ten planned lesson topics:
{topics}

Short focus:
Unit {focus['unit']} — {focus['unit_name']}
Topic: {focus['topic']}

Prepare the bilingual Short storyboard and one Community post with poll.
For the Community post, mention all ten unit areas but avoid adding any unconfirmed video URLs.
The Short must be a genuine lesson, not merely an advertisement."""
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": 6000,
            "responseMimeType": "application/json",
            "responseSchema": SCHEMA,
        },
    }
    result = call_gemini(api_key, payload)
    candidates = result.get("candidates", [])
    if not candidates:
        raise SystemExit("Gemini returned no daily promotional content candidate.")
    raw = "\n".join(
        part.get("text", "")
        for part in candidates[0].get("content", {}).get("parts", [])
        if part.get("text")
    )
    if candidates[0].get("finishReason") == "MAX_TOKENS" or not raw.strip():
        raise SystemExit("Gemini response was empty or truncated; no promo assets accepted.")
    try:
        data = validate(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(f"Gemini daily-asset JSON validation failed: {exc}") from exc

    date = manifest["publication_date"]
    root = Path("output")
    shorts_dir = root / "shorts"
    community_dir = root / "community"
    shorts_dir.mkdir(parents=True, exist_ok=True)
    community_dir.mkdir(parents=True, exist_ok=True)

    storyboard = [
        f"# Daily YouTube Short — {date}",
        "",
        f"**Title:** {data['short_title']}",
        f"**Focus:** Unit {focus['unit']} — {focus['unit_name']} — {focus['topic']}",
        "**Format:** 9:16 vertical, bilingual, 45–60 second target",
        "",
        "## Scene-by-scene storyboard",
        "",
    ]
    for i, scene in enumerate(data["scenes"], start=1):
        storyboard += [
            f"### Scene {i}",
            f"**English screen title:** {scene['screen_title_en']}",
            f"**Hindi screen title:** {scene['screen_title_hi']}",
            f"**English on-screen text:** {scene['screen_text_en']}",
            f"**Hindi on-screen text:** {scene['screen_text_hi']}",
            f"**English voiceover:** {scene['voiceover_en']}",
            f"**Hindi voiceover:** {scene['voiceover_hi']}",
            f"**Visual direction:** {scene['visual_direction']}",
            "",
        ]
    storyboard += [
        "## Outro",
        f"**English:** {data['outro_en']}",
        f"**Hindi:** {data['outro_hi']}",
        "",
        "## Description",
        data["short_description"],
        "",
        " ".join(data["hashtags"]),
        "",
        "> Video rendering uses a local open-source synthetic voice and no music. Review pronunciation, facts and pacing before use.",
    ]
    (shorts_dir / f"{date}-short-storyboard.md").write_text("\n".join(storyboard) + "\n", encoding="utf-8")

    promo_json = {
        "publication_date": date,
        "focus_unit": focus,
        "short_title": data["short_title"],
        "scenes": data["scenes"],
        "outro_en": data["outro_en"],
        "outro_hi": data["outro_hi"],
    }
    (shorts_dir / f"{date}-short.json").write_text(
        json.dumps(promo_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    community = [
        f"# DigvijayEconLab | Daily Economics Learning Plan — {date}",
        "",
        data["community_post"],
        "",
        "## Community Poll",
        data["poll_question"],
        "",
    ]
    community += [f"- {option}" for option in data["poll_options"]]
    community += ["", "## Suggested pinned comment", data["pinned_comment"], ""]
    (community_dir / f"{date}-community-post.md").write_text(
        "\n".join(community) + "\n", encoding="utf-8"
    )
    print(f"Short storyboard and structured scene file saved for {date}.")
    print(f"Community post and poll draft saved for {date}.")


if __name__ == "__main__":
    main()
