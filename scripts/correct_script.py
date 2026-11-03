import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def call_gemini(api_key, payload):
    import json

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise SystemExit(f"Gemini correction failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Gemini correction connection failed: {exc}") from exc


def extract_section(text, start_marker, end_marker):
    if start_marker not in text or end_marker not in text:
        raise ValueError(f"Missing section marker: {start_marker}")
    return text.split(start_marker, 1)[1].split(end_marker, 1)[0].strip()


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: correct_script.py SCRIPT_PATH REVIEW_PATH [SOURCE_NOTES]")
    script_path, review_path = Path(sys.argv[1]), Path(sys.argv[2])
    source_notes = sys.argv[3] if len(sys.argv) > 3 else ""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not configured.")
    if not script_path.is_file() or not review_path.is_file():
        raise SystemExit("The original script or academic review report was not found.")

    script = script_path.read_text(encoding="utf-8")
    review = review_path.read_text(encoding="utf-8")
    system_prompt = """You are a careful academic script editor for DigvijayEconLab,
serving MPPSC Assistant Professor Economics aspirants.
Apply only corrections supported by the supplied script, review, or source notes.
Do not browse, invent facts, invent citations, or claim independent verification.
Preserve topic, teaching sequence, examples, MCQs, answer keys, bilingual structure,
and useful detail unless a specific issue requires a change. Correct clear editorial,
notation, grammar, formatting, and consistency problems. Resolve [VERIFY] markers
only when source notes establish the answer; otherwise retain a clear
[HUMAN VERIFY: ...] marker and list it as unresolved. If a factual change is not
supported by source notes, do not silently apply it. Do not remove caveats to make
the script appear ready. Never label the script fact-checked, certified, or approved
for publication.

Return plain text using these exact delimiters, with no JSON and no code fences:
<<<CORRECTED_SCRIPT_START>>>
the complete corrected Markdown script
<<<CORRECTED_SCRIPT_END>>>
<<<CORRECTION_LOG_START>>>
one bullet per specific correction or reason an issue was retained
<<<CORRECTION_LOG_END>>>
<<<UNRESOLVED_ITEMS_START>>>
one bullet per item requiring human/source verification, or write "- None reported; human review is still required."
<<<UNRESOLVED_ITEMS_END>>>
Do not omit or rename any delimiter. Do not put commentary outside these sections."""

    user_prompt = f"""SOURCE NOTES:
{source_notes if source_notes.strip() else "[No source notes supplied. Factual claims cannot be independently verified.]"}
ORIGINAL SCRIPT:
{script}
ACADEMIC REVIEW REPORT:
{review}
Apply safe, evidence-grounded corrections and return the delimited response."""

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 8192},
    }
    result = call_gemini(api_key, payload)
    candidates = result.get("candidates", [])
    if not candidates:
        raise SystemExit("Gemini returned no correction candidate.")
    parts = candidates[0].get("content", {}).get("parts", [])
    raw = "\n".join(p.get("text", "") for p in parts if p.get("text"))
    if not raw.strip():
        raise SystemExit("Gemini returned an empty correction response.")

    markers = (
        ("<<<CORRECTED_SCRIPT_START>>>", "<<<CORRECTED_SCRIPT_END>>>"),
        ("<<<CORRECTION_LOG_START>>>", "<<<CORRECTION_LOG_END>>>"),
        ("<<<UNRESOLVED_ITEMS_START>>>", "<<<UNRESOLVED_ITEMS_END>>>"),
    )
    fallback_used = False
    try:
        corrected, log_text, unresolved_text = [
            extract_section(raw, start, end) for start, end in markers
        ]
        if not corrected:
            raise ValueError("Corrected script section was empty.")
    except ValueError as exc:
        # Never guess where an unstructured or truncated model response begins.
        # Preserve the source script verbatim and let the independent second
        # review run on it instead of failing the entire workflow.
        fallback_used = True
        corrected = script
        log_text = (
            "- No edits were applied. Gemini did not return all required "
            "section markers; the original script was retained unchanged.\n"
            f"- Formatting issue: {exc}"
        )
        unresolved_text = (
            "- Review the original script manually; the AI correction stage "
            "did not produce a safely parseable revision.\n"
            "- Verify factual claims against authoritative sources."
        )

    corrected_dir, report_dir = Path("output/corrected_scripts"), Path("output/corrections")
    corrected_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    corrected_path = corrected_dir / script_path.name
    report_path = report_dir / f"{script_path.stem}-correction-log.md"
    corrected_path.write_text(corrected.rstrip() + "\n", encoding="utf-8")

    report = (
        "# Script Correction Log\n\n"
        "> AI-assisted editing only. Not factual certification or publication approval.\n\n"
        "## Changes made\n\n" + (log_text or "- No specific changes reported.") + "\n\n"
        "## Unresolved human-verification items\n\n" +
        (unresolved_text or "- None reported; human review is still required.") +
        "\n\n## Required human action\n\n"
        "Compare the corrected script with the original, verify factual claims against "
        "authoritative sources, and approve all edits before production.\n"
    )
    report_path.write_text(report, encoding="utf-8")
    print(f"Corrected script generated: {corrected_path}")
    print(f"Correction log generated: {report_path}")
    if fallback_used:
        print("WARNING: Gemini response format was invalid; original script retained unchanged.")
    print("Status: EDITED DRAFT ONLY — human comparison, fact-check, and approval required.")


if __name__ == "__main__":
    main()
