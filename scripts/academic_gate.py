"""Severity-based academic workflow gate: pass only to mandatory human review."""
import argparse
import re
from pathlib import Path

HEADING = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
VERIFY = re.compile(r"\[(?:HUMAN\s+)?VERIFY\b[^\]]*\]", re.I)


def sections(markdown):
    matches = list(HEADING.finditer(markdown))
    found = {}
    for i, match in enumerate(matches):
        name = re.sub(r"[*_]", "", match.group(1)).strip().casefold()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
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
    rejected = re.search(r"\b(HOLD|CORRECTION|NOT READY|REJECT(?:ED)?)\b", verdict, re.I)
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
        line = line.replace("*", "").replace("_", "").strip()
        if not line:
            continue
        if re.match(r"^(?:none\b|no\s+(?:critical|high[- ]priority)\s+issues?\b)", line, re.I):
            continue
        meaningful.append(line)
    return bool(meaningful)


def evaluate(review, deterministic, script, attestation):
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
    elif any(
        phrase in reviewer_verdict.casefold()
        for phrase in ("not ready", "reject", "fail")
    ):
        blockers.append(f"The academic reviewer explicitly rejected the lesson (detected: {reviewer_verdict}).")

    # A HOLD caused only by medium/low editorial recommendations may proceed
    # to mandatory human review. Critical/high findings above still block.
    # This stage never approves publication or public upload.

    structural_count = extract_blocking_count(deterministic)
    if structural_count is None:
        blockers.append(
            "Could not parse the deterministic structural-check count; expected '- Blocking findings: N'."
        )
    elif structural_count != 0:
        blockers.append(
            f"Deterministic structural checks report {structural_count} blocking finding(s)."
        )

    if VERIFY.search(script):
        blockers.append("Human verification markers remain in the corrected lesson.")
    if (
        not attestation.is_file()
        or "user explicitly confirmed" not in attestation.read_text(encoding="utf-8").casefold()
    ):
        blockers.append("A separate human fact-check attestation record is missing.")

    return not blockers, blockers


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_report")
    parser.add_argument("deterministic_report")
    parser.add_argument("corrected_script")
    parser.add_argument("attestation")
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
    attestation = Path(args.attestation)
    passed, blockers = evaluate(review, deterministic, script, attestation)

    reviewer_verdict = extract_reviewer_verdict(review) or "Not parsed"
    structural_count = extract_blocking_count(deterministic)
    lines = [
        "# Academic Gate Decision",
        "",
        "> Workflow eligibility for human review only. This is not academic certification or permission to publish.",
        "",
        f"- AI reviewer verdict: {reviewer_verdict}",
        f"- Deterministic structural blockers: {structural_count if structural_count is not None else 'Unknown'}",
        f"- Separate human attestation present: {'Yes' if attestation.is_file() else 'No'}",
        f"- Remaining verification markers: {len(VERIFY.findall(script))}",
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
        "Medium/low-priority editorial recommendations and verification reminders remain visible in the AI review and must be considered during the final human review. A passing gate does not approve public release.",
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
