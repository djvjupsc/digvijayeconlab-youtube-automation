import argparse
import re
from pathlib import Path


def sanitize_math_notation(text):
    """Apply only deterministic, narrowly scoped repairs to known notation corruption."""
    changes = []

    def replace(old, new, label):
        nonlocal text
        if old in text:
            text = text.replace(old, new)
            changes.append(label)

    # JSON can decode a malformed LaTeX command such as "\\frac" into a
    # control character followed by "rac". Repair the known derivative form.
    replace("\x0crac{dQ_d}{dP}", "dQ_d/dP",
            "Repaired a control-character-corrupted demand derivative as dQ_d/dP.")

    # Repair other simple two-argument fractions without retaining fragile TeX.
    fraction_pattern = re.compile(r"\x0crac\{([^{}]+)\}\{([^{}]+)\}")
    text, count = fraction_pattern.subn(r"(\1)/(\2)", text)
    if count:
        changes.append(f"Repaired {count} additional control-character-corrupted fraction expression(s).")

    # Recover known LaTeX command prefixes that JSON may decode as controls.
    replace("\r" + "aisebox", "\\raisebox", "Recovered a corrupted raisebox command prefix.")
    replace("\t" + "iny", "\\tiny", "Recovered a corrupted tiny command prefix.")
    replace("\t" + "extuparrow", "\\textuparrow", "Recovered a corrupted upward-arrow command prefix.")
    replace("\t" + "extdownarrow", "\\textdownarrow", "Recovered a corrupted downward-arrow command prefix.")
    replace("\x08igcup", "\\bigcup", "Recovered a corrupted bigcup command prefix.")
    replace("\x08igcap", "\\bigcap", "Recovered a corrupted bigcap command prefix.")
    text, text_count = re.subn(r"\t\s*ext\{", r"\\text{", text)
    if text_count:
        changes.append(f"Recovered {text_count} corrupted LaTeX text command(s).")

    # Use readable Unicode arrows instead of fragile nested LaTeX formatting.
    arrow_up = re.compile(r"\\raisebox\{[^{}\n]*\}\{\\tiny\\textuparrow\}")
    arrow_down = re.compile(r"\\raisebox\{[^{}\n]*\}\{\\tiny\\textdownarrow\}")
    text, up_count = arrow_up.subn("↑", text)
    text, down_count = arrow_down.subn("↓", text)
    if up_count:
        changes.append(f"Replaced {up_count} fragile upward-arrow LaTeX expression(s) with Unicode arrows.")
    if down_count:
        changes.append(f"Replaced {down_count} fragile downward-arrow LaTeX expression(s) with Unicode arrows.")

    # A simple one-variable derivative should remain robust in Markdown/teleprompters.
    text, derivative_count = re.subn(r"\\frac\{dQ_d\}\{dP\}", "dQ_d/dP", text)
    if derivative_count:
        changes.append("Normalized the demand derivative to the readable form dQ_d/dP.")

    return text, changes




QUESTION_HEADING_PATTERN = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:\*\*\s*)?(?:MCQ\s*|Q(?:uestion)?\s*|प्रश्न\s*)(?P<number>0*\d+)\b"
)
ANSWER_LINE_PATTERN = re.compile(
    r"(?im)^\s*.*\b(?:Correct\s+Answer|Answer|सही\s+उत्तर|उत्तर)\b.*[:：]"
)
EXPLANATION_LINE_PATTERN = re.compile(
    r"^\s*.*(?:\bExplanation\b|व्याख्या).*[:：]",
    flags=re.IGNORECASE | re.MULTILINE,
)


def count_mcq_sections(text):
    """Count MCQs in the practice section, including numbered-list and Q1/MCQ 1 styles.

    Scope plain numbered-list recognition to the Practice MCQs section so numbered
    lesson headings (for example, '1. Core Concept') are never counted as questions.
    """
    scoped_text = text
    practice_heading = re.search(
        r"(?im)^#{1,6}\s+.*(?:practice\s+mcqs|अभ्यास\s+प्रश्न|बहुविकल्पीय\s+प्रश्न).*?$",
        text,
    )
    if practice_heading:
        section_start = practice_heading.end()
        next_heading = re.search(r"(?m)^#{1,6}\s+", text[section_start:])
        scoped_text = text[section_start:section_start + next_heading.start()] if next_heading else text[section_start:]

    matches = list(QUESTION_HEADING_PATTERN.finditer(scoped_text))
    # Numbered list questions such as '1. **Question text**' are valid MCQ labels.
    numbered_pattern = re.compile(
        r"(?m)^\s*(?P<number>0*[1-9]\d*)[.)]\s+(?=\*\*|[A-Z¿¡अ-ह])"
    )
    matches.extend(numbered_pattern.finditer(scoped_text))
    matches.sort(key=lambda match: match.start())

    sections = []
    current_start = None
    current_number = None
    for match in matches:
        number = int(match.group("number"))
        if current_start is None:
            current_start, current_number = match.start(), number
        elif number != current_number:
            sections.append(scoped_text[current_start:match.start()])
            current_start, current_number = match.start(), number
    if current_start is not None:
        sections.append(scoped_text[current_start:])

    answer_count = sum(1 for section in sections if ANSWER_LINE_PATTERN.search(section))
    explanation_count = sum(1 for section in sections if EXPLANATION_LINE_PATTERN.search(section))
    return len(sections), answer_count, explanation_count

def _issue(code, severity, message, snippet="", blocking=None):
    if blocking is None:
        blocking = severity in {"Critical", "High"}
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "snippet": snippet,
        "blocking": blocking,
    }


def analyze_script(text, content_format="Concept Explainer", language="Bilingual"):
    """Return deterministic content and formatting findings; this is not fact-checking."""
    findings = []

    controls = sorted({ord(ch) for ch in text if ord(ch) < 32 and ch not in "\n\r\t"})
    if controls:
        labels = ", ".join(f"U+{value:04X}" for value in controls)
        findings.append(_issue(
            "CONTROL_CHARACTER", "Critical",
            f"Unexpected control character(s) remain in the script: {labels}.",
            "Inspect the affected mathematical or formatted expression."
        ))

    broken_prefixes = [
        ("FORM_FEED_RAC", "\x0crac"),
        ("CARRIAGE_RETURN_AISEBOX", "\r" + "aisebox"),
        ("TAB_TINY", "\t" + "iny"),
        ("TAB_TEXT_ARROW", "\t" + "extuparrow"),
        ("TAB_TEXT_ARROW_DOWN", "\t" + "extdownarrow"),
    ]
    for code, token in broken_prefixes:
        if token in text:
            findings.append(_issue(
                code, "Critical",
                "A known control-character-corrupted mathematical formatting token remains.",
                repr(token)
            ))

    if re.search(r"\\raisebox\{[^{}\n]*\}\{\\tiny\\text(?:up|down)arrow\}", text):
        findings.append(_issue(
            "FRAGILE_LATEX_ARROW", "High",
            "A nested raisebox/tiny arrow command remains; use readable Unicode arrows (↑ or ↓).",
            "raisebox / tiny / textuparrow or textdownarrow"
        ))

    dollar_count = text.count("$")
    if dollar_count % 2:
        findings.append(_issue(
            "UNBALANCED_MATH_DELIMITER", "High",
            "The number of dollar-sign math delimiters is odd; at least one inline or display math delimiter may be unclosed.",
            f"{dollar_count} dollar-sign character(s)"
        ))

    mixed_tokens = re.findall(r"[A-Za-z]+[\u0900-\u0963\u0966-\u097F]+|[\u0900-\u0963\u0966-\u097F]+[A-Za-z]+", text)
    if mixed_tokens:
        sample = ", ".join(dict.fromkeys(mixed_tokens))
        findings.append(_issue(
            "MIXED_SCRIPT_TOKEN", "High",
            "A word appears to combine Latin and Devanagari characters without a separator. Review for typing or translation corruption.",
            sample[:240]
        ))

    marker_matches = re.findall(r"\[(?:HUMAN\s+)?VERIFY\b[^\]]*\]|\[सत्यापन योग्य\]", text, flags=re.IGNORECASE)
    if marker_matches:
        findings.append(_issue(
            "UNRESOLVED_VERIFY_MARKER", "High",
            f"{len(marker_matches)} human-verification marker(s) remain; resolve them during subject-matter review before publication.",
            "; ".join(marker_matches[:3])[:300],
            blocking=False,
        ))

    has_latin = bool(re.search(r"[A-Za-z]", text))
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
    selected_language = (language or "Bilingual").strip().lower()
    if selected_language == "bilingual" and not (has_latin and has_devanagari):
        findings.append(_issue(
            "BILINGUAL_LANGUAGE_MISSING", "High",
            "Bilingual mode was selected, but the script does not visibly contain both Latin and Devanagari text.",
            f"Latin present: {has_latin}; Devanagari present: {has_devanagari}"
        ))
    elif selected_language == "hindi" and not has_devanagari:
        findings.append(_issue(
            "HINDI_SCRIPT_MISSING", "High",
            "Hindi mode was selected, but no Devanagari text was detected."
        ))
    elif selected_language == "english" and not has_latin:
        findings.append(_issue(
            "ENGLISH_TEXT_MISSING", "High",
            "English mode was selected, but no Latin-script text was detected."
        ))

    normalized_format = (content_format or "Concept Explainer").strip().lower()
    if "mcq set" in normalized_format:
        minimum_mcqs = 10
    elif "previous-year" in normalized_format or "previous year" in normalized_format:
        minimum_mcqs = 3
    else:
        minimum_mcqs = 5

    question_count, answer_count, explanation_count = count_mcq_sections(text)

    if question_count < minimum_mcqs:
        findings.append(_issue(
            "MCQ_COUNT_BELOW_MINIMUM", "High",
            f"{content_format} requires at least {minimum_mcqs} numbered practice questions in this workflow; found {question_count}.",
            f"Detected questions: {question_count}; required minimum: {minimum_mcqs}"
        ))
    if question_count and answer_count < question_count:
        findings.append(_issue(
            "MCQ_ANSWER_GAP", "High",
            f"Detected {question_count} question(s) but only {answer_count} explicit 'Correct Answer' label(s).",
            "Every MCQ must have one clearly identified answer."
        ))
    if question_count and explanation_count < question_count:
        findings.append(_issue(
            "MCQ_EXPLANATION_GAP", "High",
            f"Detected {question_count} question(s) but only {explanation_count} explicit explanation label(s).",
            "Every MCQ must include a clear rationale."
        ))

    if "concept explainer" in normalized_format:
        required_sections = [
            (("learning objectives", "objectives", "सीखने के उद्देश्य"), "Learning objectives"),
            (("definition", "core concept", "परिभाषा", "मुख्य परिभाषा", "परिचय"), "Core definition or concept"),
            (("recap", "summary", "conclusion", "सारांश", "निष्कर्ष"), "Recap or conclusion"),
        ]
        lower_text = text.lower()
        for keys, label in required_sections:
            if not any(key in lower_text for key in keys):
                findings.append(_issue(
                    "CONTENT_SECTION_MISSING", "High",
                    f"Required Concept Explainer component was not detected: {label}.",
                    label
                ))

        # Require a dedicated, populated worked-example/application or demand-schedule
        # section. A passing mention of an example elsewhere in the script is not enough.
        headings = list(re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text))
        example_heading = re.compile(
            r"(?:worked\s+example|example|application|demand\s+schedule|"
            r"worked\s+application|उदाहरण|अनुप्रयोग|मांग\s+अनुसूची|मांग\s+सारणी)",
            flags=re.IGNORECASE,
        )
        valid_example_section = False
        example_heading_found = False
        lines = text.splitlines()
        for index, match in enumerate(headings):
            heading_text = match.group(1)
            if not example_heading.search(heading_text):
                continue
            example_heading_found = True
            body_start = match.end()
            # Include nested subsections (for example, ### English / ### Hindi)
            # until the next heading at the same or a higher level.
            current_level = len(match.group(0).split(heading_text, 1)[0].strip())
            next_peer = next(
                (
                    candidate for candidate in headings[index + 1:]
                    if len(candidate.group(0).split(candidate.group(1), 1)[0].strip()) <= current_level
                ),
                None,
            )
            body_end = next_peer.start() if next_peer else len(text)
            body_lines = [
                line.strip() for line in text[body_start:body_end].splitlines()
                if line.strip() and line.strip() not in {"---", "***", "___"}
            ]
            body_text = " ".join(body_lines)
            table_rows = sum(1 for line in body_lines if line.startswith("|"))
            if len(body_text) >= 30 and (
                len(re.findall(r"\w+", body_text, flags=re.UNICODE)) >= 6
                or table_rows >= 3
            ):
                valid_example_section = True
                break

        if not valid_example_section:
            reason = (
                "A dedicated worked-example/application or demand-schedule heading exists, "
                "but its section is empty or too short."
                if example_heading_found else
                "A dedicated worked-example/application or demand-schedule section heading is missing."
            )
            findings.append(_issue(
                "WORKED_EXAMPLE_OR_DEMAND_SCHEDULE_MISSING", "High",
                reason,
                "Add a populated heading such as '## Worked Example / Application' or '## Demand Schedule'."
            ))

    return findings


def render_report(text, findings, content_format="Concept Explainer", language="Bilingual"):
    question_count, answer_count, explanation_count = count_mcq_sections(text)
    latin_count = len(re.findall(r"[A-Za-z]", text))
    devanagari_count = len(re.findall(r"[\u0900-\u097F]", text))
    blockers = [item for item in findings if item["blocking"]]
    lines = [
        "# Deterministic Script Quality Check",
        "",
        "> Automated structural and formatting checks only. This report does not establish academic accuracy.",
        "",
        f"- Selected format: {content_format}",
        f"- Selected language: {language}",
        f"- Numbered questions detected: {question_count}",
        f"- Explicit answer labels detected: {answer_count}",
        f"- Explanation labels detected: {explanation_count}",
        f"- Latin-script letters detected: {latin_count}",
        f"- Devanagari letters detected: {devanagari_count}",
        f"- Blocking findings: {len(blockers)}",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("- No deterministic issues were detected by these checks.")
    else:
        for item in findings:
            lines.append(f"- **{item['severity']} — {item['code']}**: {item['message']}")
            if item["snippet"]:
                lines.append(f"  - Evidence: {item['snippet']}")
    lines += [
        "",
        "## Gate result",
        "",
        "**HOLD FOR CORRECTION**" if blockers else "**STRUCTURAL CHECKS PASSED — HUMAN REVIEW STILL REQUIRED**",
        "",
        "These checks cannot verify economic theory, source reliability, translation accuracy, or exam suitability. A subject-matter reviewer must still check those items.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Deterministic formatting and content checks for an educational script.")
    parser.add_argument("script_path")
    parser.add_argument("--content-format", default="Concept Explainer")
    parser.add_argument("--language", default="Bilingual")
    parser.add_argument("--sanitize", action="store_true", help="Apply only the documented safe notation normalizations.")
    args = parser.parse_args()

    path = Path(args.script_path)
    if not path.is_file():
        raise SystemExit(f"Script file not found: {path}")
    content = path.read_text(encoding="utf-8")

    if args.sanitize:
        content, changes = sanitize_math_notation(content)
        if changes:
            path.write_text(content, encoding="utf-8")
            print("Sanitization changes: " + " ".join(changes))
        else:
            print("No known safe notation repairs were needed.")

    findings = analyze_script(content, args.content_format, args.language)
    report = render_report(content, findings, args.content_format, args.language)
    report_path = Path("output/quality_checks") / f"{path.stem}-deterministic-check.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"Deterministic quality report generated: {report_path}")
    if any(item["blocking"] for item in findings):
        print("QUALITY GATE: HOLD FOR CORRECTION")
    else:
        print("QUALITY GATE: Structural checks passed; human review remains mandatory.")


if __name__ == "__main__":
    main()
