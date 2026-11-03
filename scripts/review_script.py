import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: review_script.py SCRIPT_PATH [SOURCE_NOTES]")

    script_path = Path(sys.argv[1])
    source_notes = sys.argv[2] if len(sys.argv) > 2 else ""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not configured.")
    if not script_path.is_file():
        raise SystemExit(f"Script file not found: {script_path}")

    script = script_path.read_text(encoding="utf-8")
    system_prompt = """You are a strict academic quality reviewer for DigvijayEconLab,
serving MPPSC Assistant Professor Economics aspirants.
Review the supplied draft; do not rewrite it and do not add outside facts.
Treat the supplied script and source notes as the only evidence available.
Do not claim that a statement is verified unless the supplied source notes support it.
If source notes are absent, explicitly say independent textbook/source verification is still required.
Check: conceptual accuracy and internal consistency; definitions and assumptions;
correct use of economic terminology; Hindi-English equivalence and clarity;
examples and exceptions; MCQ option quality, answer correctness and explanations;
unsupported claims, fabricated references, and every [VERIFY] marker;
exam-level depth, teaching sequence, and narration readiness.
For each issue give severity (Critical/High/Medium/Low), exact quoted phrase or section,
why it needs attention, and a concrete correction direction without inventing facts.
Separate source-supported observations from general academic concerns.
End with a clear verdict: READY FOR HUMAN EDITING or HOLD FOR CORRECTION.
This is an advisory review, not a factual certification. Never remove the need for human review.
Return readable Markdown with sections: Overall Verdict, Critical Issues,
High-Priority Issues, Other Improvements, MCQ Audit, Verification Gaps,
and Pre-Production Checklist."""

    user_prompt = f"""SOURCE NOTES (may be empty):
{source_notes if source_notes.strip() else "[No source notes supplied. Do not certify factual claims.]"} 

SCRIPT TO REVIEW:
{script}"""

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 8192},
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
        raise SystemExit(f"Gemini review failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Gemini review connection failed: {exc}") from exc

    candidates = result.get("candidates", [])
    if not candidates:
        raise SystemExit("Gemini returned no review candidate.")
    parts = candidates[0].get("content", {}).get("parts", [])
    review = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    if not review.strip():
        raise SystemExit("Gemini returned an empty quality review.")

    output_dir = Path("output/reviews")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{script_path.stem}-quality-review.md"
    output_path.write_text(
        "# Academic Quality-Control Report\n\n"
        "> AI-assisted review only. Not a factual certification. Human verification and approval are mandatory.\n\n"
        + review.strip() + "\n",
        encoding="utf-8",
    )
    print(f"Quality review generated: {output_path}")
    print("Status: ADVISORY ONLY — original script unchanged; human review required.")


if __name__ == "__main__":
    main()
