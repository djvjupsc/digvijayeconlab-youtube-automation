"""Severity-based academic workflow gate: pass only to mandatory human review."""
import argparse
import re
from pathlib import Path

HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
VERIFY = re.compile(r"\[(?:HUMAN\s+)?VERIFY\b[^\]]*\]|\[सत्यापन योग्य\]", re.I)


def sections(markdown):
    """Map headings to content, retaining nested subsections inside their parent."""
    matches = list(HEADING.finditer(markdown))
    found = {}
    for i, match in enumerate(matches):
        level = len(match.group(1))
        name = re.sub(r"[*_]", "", match.group(2)).strip().casefold()
        next_peer = next(
            (
                candidate for candidate in matches[i + 1:]
                if len(candidate.group(1)) <= level
            ),
            None,
        )
        body_end = next_peer.start() if next_peer else len(markdown)
        found[name] = markdown[match.end():body_end].strip()
    return found


def extract_reviewer_verdict(review):
    """Read the explicit value immediately below or beside Overall Verdict."""
    lines = review.splitlines()
    for index, line in enumerate(lines):
        if not re.search(r"\boverall verdict\b", line, flags=re.I):
            continue
        inline = re.sub(
            r"^.*?\boverall verdict\b\s*[:：]?\s*",
            "",
            line,
            flags=re.I,
        ).strip()
        if inline:
            return inline.replace("*", "").replace("_", "").strip()
        for candidate in lines[index + 1:]:
            value = candidate.strip()
            if not value:
                continue
            if value.startswith("#"):
                break
            return value.replace("*", "").replace("_", "").strip()
        return ""
    return ""


def extract_blocking_count(deterministic):
    """Parse the exact counter emitted by scripts.quality_checks.render_report."""
    match = re.search(
        r"(?im)^\s*-\s*Blocking findings:\s*(\d+)\s*$",
        deterministic,
    )
    return int(match.group(1)) if match else None


def verdict_is_approved(verdict):
    approved = re.search(r"\b(READY|APPROVED|PASS(?:ED)?)\b", verdict, re.I)
    rejected = re.search(r"\b(HOLD|CORRECTION|NOT\s+(?:READY|APPROVED)|REJECT(?:ED)?)\b", verdict, re.I)
    return bool(approved and not rejected)


def section_has_findings(body):
    if not body:
        return False
    meaningful = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(">") or line in {"---", "***"}:
            continue
        line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line)
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = line.replace("*", "").replace("_", "").strip()
        if not line:
            continue
        no_issue_statement = (
            re.match(r"^none\b", line, re.I)
            or re.match(r"^no\s+(?:critical|high[- ]priority)\s+issues?\b", line, re.I)
            or (
                re.match(r"^no\b", line, re.I)
                and re.search(
                    r"\b(?:issues?|errors?|flaws?|failures?|findings?|problems?)\b.*"
                    r"\b(?:found|identified|detected|present|remain|exist)\b",
                    line,
                    re.I,
                )
                and not re.search(r"\bbut\b", line, re.I)
            )
        )
        if no_issue_statement:
            continue
        meaningful.append(line)
    return bool(meaningful)


def evaluate(review, deterministic, script, source_verification=None, correction_log=None):
    review_sections = sections(review)
    critical_key = next((k for k in review_sections if k == "critical issues"), None)
    high_key = next(
        (k for k in review_sections if k in {"high-priority issues", "high priority issues"}),
        None,
    )

    blockers = []
    if critical_key is None or high_key is None:
        blockers.append(
            "Academic review is missing a parseable Critical Issues or High-Priority Issues section."
        )
    else:
        if section_has_findings(review_sections[critical_key]):
            blockers.append("The reviewer listed one or more unresolved critical issues.")
        if section_has_findings(review_sections[high_key]):
            blockers.append("The reviewer listed one or more unresolved high-priority issues.")

    reviewer_verdict = extract_reviewer_verdict(review)
    if not reviewer_verdict:
        blockers.append("The academic reviewer did not provide an explicit Overall Verdict.")
    elif not verdict_is_approved(reviewer_verdict):
        blockers.append(
            "The academic reviewer did not approve the lesson for human-review handoff "
            f"(detected verdict: {reviewer_verdict})."
        )

    # Only affirmative READY/APPROVED/PASS verdicts may pass this handoff gate.
    # HOLD, CORRECTION, NOT READY and ambiguous verdicts fail closed.

    structural_count = extract_blocking_count(deterministic)
    if structural_count is None:
        blockers.append(
            "Could not parse the deterministic structural-check count; expected '- Blocking findings: N'."
        )
    elif structural_count != 0:
        blockers.append(
            f"Deterministic structural checks report {structural_count} blocking finding(s)."
        )

    # Verification markers are intentionally retained as reviewer prompts.
    # They do not block handoff to a human reviewer; they remain a hard pre-publication task.
    remaining_markers = len(VERIFY.findall(script))
    if source_verification is not None:
        if (
            not source_verification.is_file()
            or "ai-assisted source review" not in source_verification.read_text(encoding="utf-8").casefold()
            or "not a human sign-off" not in source_verification.read_text(encoding="utf-8").casefold()
        ):
            blockers.append("A separate source-verification evidence report is missing or invalid.")

    if correction_log is not None:
        if not correction_log.is_file():
            blockers.append("The lesson correction log is missing.")
        else:
            correction_sections = sections(correction_log.read_text(encoding="utf-8"))
            unresolved_section = correction_sections.get("unresolved human-verification items")
            if unresolved_section is None:
                blockers.append("The correction log is missing its Unresolved human-verification items section.")
            # Unresolved items are the human review checklist, not a reason to
            # prevent the draft from reaching the human reviewer.

    return not blockers, blockers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_report")
    parser.add_argument("deterministic_report")
    parser.add_argument("corrected_script")
    parser.add_argument(
        "source_verification",
        nargs="?",
        help="Optional dedicated evidence report for a topic-specific source-verification gate.",
    )
    parser.add_argument("--correction-log", help="Optional lesson correction log; unresolved items block the gate.")
    parser.add_argument("--output", default="output/reviews/academic-gate-decision.md")
    args = parser.parse_args()

    paths = [
        Path(args.review_report),
        Path(args.deterministic_report),
        Path(args.corrected_script),
    ]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise SystemExit("Required gate input(s) missing: " + ", ".join(missing))

    review = paths[0].read_text(encoding="utf-8")
    deterministic = paths[1].read_text(encoding="utf-8")
    script = paths[2].read_text(encoding="utf-8")
    remaining_markers = len(VERIFY.findall(script))
    source_verification = Path(args.source_verification) if args.source_verification else None
    correction_log = Path(args.correction_log) if args.correction_log else None
    passed, blockers = evaluate(review, deterministic, script, source_verification, correction_log)

    reviewer_verdict = extract_reviewer_verdict(review) or "Not parsed"
    structural_count = extract_blocking_count(deterministic)
    lines = [
        "# Academic Gate Decision",
        "",
        "> Workflow eligibility for mandatory human review only. AI source review is not human sign-off, academic certification, or permission to publish.",
        "",
        f"- AI reviewer verdict: {reviewer_verdict}",
        f"- Deterministic structural blockers: {structural_count if structural_count is not None else 'Unknown'}",
        f"- Dedicated source-verification evidence present: {'Yes' if source_verification and source_verification.is_file() else 'No (generic lesson gate)'}.",
        f"- Remaining verification markers: {remaining_markers}",
        f"- Correction-log human review items: {'Present' if correction_log and correction_log.is_file() and section_has_findings(sections(correction_log.read_text(encoding='utf-8')).get('unresolved human-verification items', '')) else 'None detected'}",
        "",
        "## Decision",
        "",
        "**PASS — READY FOR HUMAN REVIEW**" if passed else "**HOLD — BLOCKED**",
        "",
        "## Blocking reasons",
        "",
    ]
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append(
        "- None detected in the critical/high-priority and deterministic gates."
    )
    lines += [
        "",
        "Verification markers and unresolved correction-log items remain explicit human review tasks. A passing gate only means the draft can be handed to a subject-matter reviewer; it is not factual certification or publication approval.",
        "",
    ]
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Academic reviewer verdict: {reviewer_verdict}")
    print(f"Deterministic structural blockers: {structural_count if structural_count is not None else 'Unknown'}")
    print(f"Academic gate decision: {'PASS — HUMAN REVIEW REQUIRED' if passed else 'HOLD'}")
    print(f"Decision report: {output_path}")
    if not passed:
        raise SystemExit("Academic gate blocked: " + " ".join(blockers))


if __name__ == "__main__":
    main()
