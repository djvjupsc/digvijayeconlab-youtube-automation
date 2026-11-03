import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def clean_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return (slug[:60] or "economics-script") + ".md"


def main():
    if len(sys.argv) < 4:
        raise SystemExit("Usage: generate_script.py TOPIC LANGUAGE FORMAT [SOURCE_NOTES]")

    topic, language, content_format = sys.argv[1:4]
    source_notes = sys.argv[4] if len(sys.argv) > 4 else ""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not configured. Add it as a GitHub Actions secret.")

    allowed_languages = {"Hindi", "English", "Bilingual"}
    allowed_formats = {"Concept Explainer", "MCQ Set", "Previous-Year-Question Analysis"}
    if language not in allowed_languages:
        raise SystemExit("Unsupported language selection.")
    if content_format not in allowed_formats:
        raise SystemExit("Unsupported content format.")

    system_prompt = """You are an educational content writer for DigvijayEconLab.
Create original, accurate material for MPPSC Assistant Professor Economics aspirants.
Do not fabricate statistics, quotations, citations, PYQs, dates, policies, or source references.
Use only the supplied source notes for specific factual claims. If notes are absent or insufficient,
mark claims that need verification as [VERIFY] rather than inventing details.
For MCQs, provide four options, the correct answer, and a clear explanation for every question.
Avoid repetitive filler, clickbait, fake engagement, and copyrighted textbook passages.
Return clean Markdown with a title, learning objectives, structured teaching content,
a concise recap, and a short quality-control checklist."""

    user_prompt = f"""Brand: DigvijayEconLab
Audience: MPPSC Assistant Professor Economics aspirants
Topic: {topic}
Language: {language}
Format: {content_format}
Source notes supplied by the user:
{source_notes if source_notes.strip() else "[No source notes supplied. Avoid unsupported factual claims and mark verification gaps.]"}
Target: a useful, classroom-ready first draft. For bilingual output, explain in Hindi and provide
the corresponding English terminology. Include source/verification notes at the end."""

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise SystemExit(f"Gemini API request failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Gemini API connection failed: {exc}") from exc

    candidates = result.get("candidates", [])
    if not candidates:
        feedback = result.get("promptFeedback", {})
        raise SystemExit("Gemini returned no script candidate. Prompt feedback: " +
                         json.dumps(feedback, ensure_ascii=False)[:800])

    parts = candidates[0].get("content", {}).get("parts", [])
    content = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    if not content.strip():
        finish_reason = candidates[0].get("finishReason", "unknown")
        raise SystemExit(f"Gemini returned empty content (finish reason: {finish_reason}).")

    output_dir = Path("output/scripts")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / clean_filename(topic)
    output_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Draft generated: {output_path}")
    print("Status: DRAFT ONLY — human fact-check and approval required.")


if __name__ == "__main__":
    main()
