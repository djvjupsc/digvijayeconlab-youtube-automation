import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def call_gemini(api_key, payload):
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
the script appear ready. Return valid JSON only with exactly these keys:
corrected_script (complete corrected Markdown script), correction_log (array of
specific changes or reasons retained), unresolved_items (array of human/source
verification items). The script must not include the correction log. Never label
the script fact-checked, certified, or approved for publication."""

    user_prompt = f"""SOURCE NOTES:
{source_notes if source_notes.strip() else "[No source notes supplied. Factual claims cannot be independently verified.]"}
ORIGINAL SCRIPT:
{script}
ACADEMIC REVIEW REPORT:
{review}
Apply safe, evidence-grounded corrections and return the required JSON."""

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
        },
    }
    result = call_gemini(api_key, payload)
    candidates = result.get("candidates", [])
    if not candidates:
        raise SystemExit("Gemini returned no correction candidate.")
    parts = candidates[0].get("content", {}).get("parts", [])
    raw = "\n".join(p.get("text", "") for p in parts if p.get("text"))
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SystemExit(f"Gemini returned invalid correction JSON: {exc}") from exc

    corrected = data.get("corrected_script")
    log = data.get("correction_log", [])
    unresolved = data.get("unresolved_items", [])
    if not isinstance(corrected, str) or not corrected.strip():
        raise SystemExit("Correction response did not contain a complete corrected_script.")
    if not isinstance(log, list) or not isinstance(unresolved, list):
        raise SystemExit("Correction log or unresolved_items has an invalid format.")

    corrected_dir, report_dir = Path("output/corrected_scripts"), Path("output/corrections")
    corrected_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    corrected_path = corrected_dir / script_path.name
    report_path = report_dir / f"{script_path.stem}-correction-log.md"
    corrected_path.write_text(corrected.strip() + "\n", encoding="utf-8")

    lines = [
        "# Script Correction Log", "",
        "> AI-assisted editing only. Not factual certification or publication approval.", "",
        "## Changes made", "",
    ]
    lines.extend([f"- {item}" for item in log] or ["- No specific changes reported."])
    lines.extend(["", "## Unresolved human-verification items", ""])
    lines.extend([f"- {item}" for item in unresolved] or
                 ["- None reported by the correction model; human review is still required."])
    lines.extend([
        "", "## Required human action", "",
        "Compare the corrected script with the original, verify factual claims against "
        "authoritative sources, and approve all edits before production.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Corrected script generated: {corrected_path}")
    print(f"Correction log generated: {report_path}")
    print("Status: EDITED DRAFT ONLY — human comparison, fact-check, and approval required.")


if __name__ == "__main__":
    main()
