import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from .gemini_client import generate_content, MAX_GEMINI_ATTEMPTS, RETRYABLE_HTTP_STATUS
except ImportError:
    from gemini_client import generate_content, MAX_GEMINI_ATTEMPTS, RETRYABLE_HTTP_STATUS

try:
    from .quality_checks import sanitize_math_notation
except ImportError:
    from quality_checks import sanitize_math_notation

try:
    from .source_notes import load_optional_source_notes
except ImportError:
    from source_notes import load_optional_source_notes

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "corrected_script": {"type": "STRING"},
        "correction_log": {"type": "ARRAY", "items": {"type": "STRING"}},
        "unresolved_items": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["corrected_script", "correction_log", "unresolved_items"],
}


def call_gemini(api_key, payload):
    try:
        return generate_content(API_URL, api_key, payload, label="Gemini correction", timeout=150)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


def parse_structured_response(raw, original_script):
    """Return (script, correction_log, unresolved_items, fallback_used).

    Never attempt to salvage partial JSON or unstructured model output.
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Response root must be a JSON object.")
        corrected = data.get("corrected_script")
        changes = data.get("correction_log")
        unresolved = data.get("unresolved_items")
        if not isinstance(corrected, str) or not corrected.strip():
            raise ValueError("corrected_script must be a non-empty string.")
        if not isinstance(changes, list) or not all(isinstance(x, str) for x in changes):
            raise ValueError("correction_log must be an array of strings.")
        if not isinstance(unresolved, list) or not all(isinstance(x, str) for x in unresolved):
            raise ValueError("unresolved_items must be an array of strings.")
        return corrected.strip(), changes, unresolved, False
    except (json.JSONDecodeError, ValueError) as exc:
        return (
            original_script,
            [
                "No edits were applied. Gemini did not return a valid structured response; "
                "the original script was retained unchanged.",
                f"Structured-response validation issue: {exc}",
            ],
            [
                "Review the original script manually; the AI correction stage did not "
                "produce a safely validated revision.",
                "Verify factual claims against authoritative sources.",
            ],
            True,
        )




VERIFY_MARKER_PATTERN = re.compile(
    r"\[(?:HUMAN\s+)?VERIFY\b[^\]]*\]|\[सत्यापन योग्य\]",
    re.IGNORECASE,
)


def preserve_original_verification_markers(
    corrected_script,
    original_script,
    unresolved_items=None,
    source_notes_supplied=False,
):
    """Keep markers unless source notes were supplied and the editor resolved every item."""
    if source_notes_supplied and not unresolved_items:
        return corrected_script, [
            "Cleared original verification markers after the source-grounded correction returned no unresolved items."
        ], []
    original_markers = VERIFY_MARKER_PATTERN.findall(original_script)
    corrected_counts = {}
    for marker in VERIFY_MARKER_PATTERN.findall(corrected_script):
        corrected_counts[marker] = corrected_counts.get(marker, 0) + 1

    missing = []
    original_counts = {}
    for marker in original_markers:
        original_counts[marker] = original_counts.get(marker, 0) + 1
    for marker, required_count in original_counts.items():
        missing.extend([marker] * max(0, required_count - corrected_counts.get(marker, 0)))

    if not missing:
        return corrected_script, [], []

    retained_section = (
        "\n\n## Original Verification Markers Retained for Human Sign-off\n\n"
        "> These markers were present in the original draft. The correction model removed or altered them, "
        "so they have been restored automatically and remain unresolved until a human verifies the claims.\n\n"
        + "\n".join(f"- {marker}" for marker in missing)
        + "\n"
    )
    corrected_script = corrected_script.rstrip() + retained_section
    changes = [
        f"Restored original verification marker: {marker}" for marker in missing
    ]
    unresolved = [
        f"Human verification still required for original marker: {marker}" for marker in missing
    ]
    return corrected_script, changes, unresolved


def apply_known_editorial_repairs(text):
    """Repair deterministic placeholders and clear script contamination without changing economics."""
    repairs = [
        ("(বাজার असफलता की परिभाषा)", "(बाजार असफलता की परिभाषा)",
         "Replaced Bengali-script contamination with the correct Devanagari Hindi heading."),
        ("MPPSC region X", "a hypothetical industrial region",
         "Replaced the invented regional placeholder with an explicitly hypothetical industrial region."),
        ("MPPSC क्षेत्र X में", "एक काल्पनिक औद्योगिक क्षेत्र में",
         "Replaced the invented regional placeholder in Hindi with an explicitly hypothetical industrial region."),
        ("negative consumption/production externality", "negative production externality",
         "Clarified that factory pollution is a negative production externality."),
    ]
    changes = []
    for old, new, description in repairs:
        if old in text:
            text = text.replace(old, new)
            changes.append(description)
    return text, changes


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: correct_script.py SCRIPT_PATH REVIEW_PATH [SOURCE_NOTES]")
    script_path, review_path = Path(sys.argv[1]), Path(sys.argv[2])
    source_notes = load_optional_source_notes(sys.argv[3] if len(sys.argv) > 3 else None)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not configured.")
    if not script_path.is_file() or not review_path.is_file():
        raise SystemExit("The original script or academic review report was not found.")

    script = script_path.read_text(encoding="utf-8")
    review = review_path.read_text(encoding="utf-8")
    system_prompt = """You are a careful academic script editor for DigvijayEconLab,
serving MPPSC Assistant Professor Economics aspirants.
Resolve every Critical and High-Priority issue explicitly identified in the academic review.
For the Law of Demand individual-demand explanation, qualify the income/substitution
decomposition as the standard neoclassical Hicks/Slutsky framework; avoid saying it
explains demand entirely across all theoretical approaches. Preserve the distinction
between individual and market demand.
For Giffen-goods bilingual parity, ensure the Hindi version includes the same historical
details as the English version, including Alfred Marshall's Principles of Economics (1895)
and the fact that attribution and the traditional Irish potato example are debated.
Use this natural Hindi wording where suitable: "हालांकि, इस उदाहरण के ऐतिहासिक श्रेय और इसकी अनुभवजन्य पुष्टि को लेकर विद्वानों में बहस है।"
Correct the exact recurring Hindi editorial defects from the Law of Demand review:
- Change "मांग का नियम की मान्यताएं" to "मांग के नियम की मान्यताएँ".
- When the Giffen-goods heading is plural, make the definition plural too: use
  "गिफ्फेन वस्तुएँ ऐसी हीन वस्तुएँ (inferior goods) हैं जिनमें..." rather than
  "गिफ्फेन वस्तु एक ऐसी हीन वस्तु (inferior good) है...".
- Replace non-standard Japanese full-stop characters (。) in Hindi paragraphs with Devanagari danda (।).
Do not change the economics meaning or remove historical caveats when making these language fixes.
For the reported heading hierarchy issue, use ### for a subsection under a numbered ## section.
Remove empty placeholder bullets left after a human verification marker is explicitly attested and cleared; do not delete any unresolved factual caveat.
Use supplied source notes when correcting historical statements; do not invent citations.
Apply only corrections supported by the supplied script, review, or source notes.
Do not browse, invent facts, invent citations, or claim independent verification.
Preserve topic, teaching sequence, examples, MCQs, answer keys, bilingual structure,
and useful detail unless a specific issue requires a change. Correct clear editorial,
notation, grammar, formatting, translation parity, and consistency problems.
Prefer plain Unicode arrows (↑ and ↓) and simple derivative text such as dQ_d/dP.
Avoid nested LaTeX formatting macros such as raisebox and tiny. Do not emit control
characters inside formulas or text.
Resolve [VERIFY] markers only when source notes establish the answer; otherwise
retain a clear [HUMAN VERIFY: ...] marker and list it as unresolved. If a factual
change is not supported by source notes, do not silently apply it. Do not remove
caveats to make the script appear ready. Never label the script fact-checked,
certified, or approved for publication.

Return only a JSON object matching the supplied response schema:
- corrected_script: the complete corrected Markdown script as one string
- correction_log: array of concise strings describing actual changes or why issues
  were retained; do not claim changes that were not made
- unresolved_items: array of strings for every item needing human/source verification
If no safe corrections can be made, return the original script unchanged and explain
that in correction_log. Do not include Markdown fences or commentary outside JSON."""
    user_prompt = f"""SOURCE NOTES:
{source_notes if source_notes.strip() else "[No source notes supplied. Factual claims cannot be independently verified.]"}
ORIGINAL SCRIPT:
{script}
ACADEMIC REVIEW REPORT:
{review}
Apply safe, evidence-grounded corrections. Preserve all material content and the bilingual structure."""

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    result = call_gemini(api_key, payload)
    candidates = result.get("candidates", [])
    if not candidates:
        raise SystemExit("Gemini returned no correction candidate.")
    candidate = candidates[0]
    finish_reason = candidate.get("finishReason", "")
    parts = candidate.get("content", {}).get("parts", [])
    raw = "\n".join(p.get("text", "") for p in parts if p.get("text"))
    if not raw.strip():
        raise SystemExit("Gemini returned an empty correction response.")
    if finish_reason == "MAX_TOKENS":
        raw = ""  # Truncated output must never be accepted as a complete revision.

    corrected, changes, unresolved, fallback_used = parse_structured_response(raw, script)

    # Never permit the correction model to silently drop or rewrite original verification markers.
    corrected, marker_changes, marker_unresolved = preserve_original_verification_markers(
        corrected,
        script,
        unresolved_items=unresolved,
        source_notes_supplied=bool(source_notes.strip()),
    )
    changes.extend(marker_changes)
    unresolved.extend(marker_unresolved)

    # Apply only known, deterministic notation repairs after a valid structured response.
    # On fallback, preserve the original byte-for-byte content and let the gate report issues.
    if not fallback_used:
        corrected, notation_changes = sanitize_math_notation(corrected)
        changes.extend(notation_changes)
        corrected, editorial_changes = apply_known_editorial_repairs(corrected)
        changes.extend(editorial_changes)

    corrected_dir, report_dir = Path("output/corrected_scripts"), Path("output/corrections")
    corrected_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    corrected_path = corrected_dir / script_path.name
    report_path = report_dir / f"{script_path.stem}-correction-log.md"
    corrected_path.write_text(corrected.rstrip() + "\n", encoding="utf-8")

    changes_text = "\n".join(f"- {item}" for item in changes) or "- No changes reported."
    unresolved_text = "\n".join(f"- {item}" for item in unresolved) or (
        "- None reported; human review is still required."
    )
    report = (
        "# Script Correction Log\n\n"
        "> AI-assisted editing only. Not factual certification or publication approval.\n\n"
        "## Changes made / retained issues\n\n" + changes_text + "\n\n"
        "## Unresolved human-verification items\n\n" + unresolved_text +
        "\n\n## Required human action\n\n"
        "Compare the corrected script with the original, verify factual claims against "
        "authoritative sources, and approve all edits before production.\n"
    )
    report_path.write_text(report, encoding="utf-8")
    print(f"Corrected script generated: {corrected_path}")
    print(f"Correction log generated: {report_path}")
    if fallback_used:
        print("WARNING: Structured response validation failed; original script retained unchanged.")
    elif corrected.strip() == script.strip():
        print("NOTICE: No textual changes were made; inspect the correction log.")
    else:
        print("Structured correction response validated successfully.")
    print("Status: EDITED DRAFT ONLY — human comparison, fact-check, and approval required.")


if __name__ == "__main__":
    main()
