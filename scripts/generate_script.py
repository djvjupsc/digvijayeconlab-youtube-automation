import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from .gemini_client import generate_content
except ImportError:
    from gemini_client import generate_content

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
For MCQs, provide four options, one clearly marked correct answer, and a clear explanation for every question.
Use clean Markdown and robust notation. Prefer readable Unicode arrows (↑ and ↓) and simple
plain-text derivative notation such as dQ_d/dP. Do not use nested formatting macros such as
raisebox or tiny, and do not put control characters inside mathematical expressions.
For Bilingual output, provide the English explanation followed by a faithful Hindi equivalent
for each substantive teaching point or paragraph. Do not blend Latin and Devanagari characters
inside a single word. Keep standard English technical terms in parentheses where useful.
For a Concept Explainer, include a dedicated, populated Markdown section titled
"## Worked Example / Application" or "## Demand Schedule" (a suitable Hindi-English
equivalent is acceptable). This must contain a worked illustrative example with clear
steps/units or a labelled demand-schedule table with at least two data rows. Clearly label
illustrative numbers as hypothetical; never present invented numbers as real observations.
A passing mention of an example elsewhere in the script is not sufficient.
Avoid repetitive filler, clickbait, fake engagement, and copyrighted textbook passages.
For the specific topic Law of Demand, follow supplied source notes on Giffen goods carefully. State that the historical attribution is debated; do not imply the Irish potato famine example is settled empirical proof. Distinguish Giffen goods from Veblen/status goods. Explain downward-sloping individual demand using substitution and income effects; discuss additional buyers only in the context of market demand. If the supplied notes adequately resolve a historical nuance, do not add a [VERIFY] marker for that exact nuance; retain [VERIFY] only for genuinely unsupported claims elsewhere.
Return clean Markdown with a title, learning objectives, structured teaching content,
a dedicated worked example/application or demand-schedule section, a concise recap,
practice questions, and source/verification notes."""

    if content_format == "Concept Explainer":
        format_requirements = (
            "Concept Explainer requirements: include learning objectives, a clear definition, "
            "assumptions or scope where relevant, step-by-step explanation, suitable examples or "
            "applications, a concise recap, and at least 5 distinct MCQs. Each MCQ needs four options, "
            "one correct answer, and an explanation. Add a labelled schedule/curve description only "
            "where it genuinely helps explain the topic; never invent data."
        )
    elif content_format == "MCQ Set":
        format_requirements = (
            "MCQ Set requirements: provide at least 10 distinct topic-relevant MCQs, each with four "
            "options, one correct answer, and an explanation. Avoid duplicate questions and ambiguous "
            "distractors. Include a short concept map or revision recap."
        )
    else:
        format_requirements = (
            "Previous-Year-Question Analysis requirements: analyze at least 3 questions only when "
            "actual question text or a reliable source is supplied. Never invent or label a question "
            "as an actual PYQ without evidence. If actual PYQs are not supplied, clearly label any "
            "new questions as PYQ-style practice, not previous-year questions. Explain the concept, "
            "reasoning, answer, and exam relevance for each included question."
        )

    unit_context = os.environ.get("SCRIPT_UNIT", "")
    user_prompt = f"""Brand: DigvijayEconLab\nUnit: {unit_context or "Not specified"}
Audience: MPPSC Assistant Professor Economics aspirants
Topic: {topic}
Language: {language}
Format: {content_format}
Format-specific requirements:
{format_requirements}
Source notes supplied by the user:
{source_notes if source_notes.strip() else "[No source notes supplied. Avoid unsupported factual claims and mark verification gaps.]"}
Target: a useful, classroom-ready first draft. For bilingual output, provide corresponding
English and Hindi explanations for each substantive teaching point. Include source/verification notes at the end."""

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
    }
    try:
        result = generate_content(API_URL, api_key, payload, label="Gemini script generation", timeout=120)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

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
    unit_prefix = os.environ.get("SCRIPT_FILENAME_PREFIX", "").strip()
    filename_topic = f"{unit_prefix} {topic}" if unit_prefix else topic
    output_path = output_dir / clean_filename(filename_topic)
    output_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Draft generated: {output_path}")
    print("Status: DRAFT ONLY — human fact-check and approval required.")


if __name__ == "__main__":
    main()
