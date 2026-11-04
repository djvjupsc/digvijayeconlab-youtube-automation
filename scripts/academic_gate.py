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


def section_has_findings(body):
    if not body:
        return False
    meaningful = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith(">") or line in {"---", "***"}:
            continue
        line = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line)
        line = re.sub(r"[*_`]", "", line).strip()
        if not line:
            continue
        if re.match(r"^(?:none\b|no\s+(?:critical|high[- ]priority)\s+issues?\b)", line, re.I):
            continue
        meaningful.append(line)
    return bool(meaningful)


def evaluate(review, deterministic, script, attestation):
    review_sections = sections(review)
    critical_key = next((k for k in review_sections if k in {"critical issues", "critical issues:"}), None)
    high_key = next((k for k in review_sections if k in {"high-priority issues", "high priority issues", "high-priority issues:"}), None)
    if critical_key is None or high_key is None:
        return False, ["Academic review is missing a parseable Critical Issues or High-Priority Issues section."]

    blockers = []
    if section_has_findings(review_sections[critical_key]):
        blockers.append("The reviewer listed one or more unresolved critical issues.")
    if section_has_findings(review_sections[high_key]):
        blockers.append("The reviewer listed one or more unresolved high-priority issues.")

    match = re.search(r"Blocking findings:\s*(\d+)", deterministic, re.I)
    if not match:
        blockers.append("Could not determine the deterministic structural-check result.")
    elif int(match.group(1)) != 0:
        blockers.append(f"Deterministic structural checks report {match.group(1)} blocking finding(s).")

    if VERIFY.search(script):
        blockers.append("Human verification markers remain in the corrected lesson.")
    if not attestation.is_file() or "user explicitly confirmed" not in attestation.read_text(encoding="utf-8").casefold():
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

    paths = [Path(args.review_report), Path(args.deterministic_report), Path(args.corrected_script)]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise SystemExit("Required gate input(s) missing: " + ", ".join(missing))

    review = paths[0].read_text(encoding="utf-8")
    deterministic = paths[1].read_text(encoding="utf-8")
    script = paths[2].read_text(encoding="utf-8")
    attestation = Path(args.attestation)
    passed, blockers = evaluate(review, deterministic, script, attestation)

    verdict_match = re.search(r"Overall Verdict\s*\n+([^\n]+)", review, re.I)
    reviewer_verdict = verdict_match.group(1).strip() if verdict_match else "Not parsed"
    lines = [
        "# Academic Gate Decision",
        "",
        "> Workflow eligibility for human review only. This is not academic certification or permission to publish.",
        "",
        f"- AI reviewer verdict: {reviewer_verdict}",
        f"- Deterministic structural blockers: {re.search(r'Blocking findings:\\s*(\\d+)', deterministic, re.I).group(1) if re.search(r'Blocking findings:\\s*(\\d+)', deterministic, re.I) else 'Unknown'}",
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
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- None detected in the critical/high-priority and deterministic gates.")
    lines += [
        "",
        "Medium/low-priority editorial recommendations and verification reminders remain visible in the AI review and must be considered during the final human review. A passing gate does not approve public release.",
        "",
    ]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Academic gate decision: {'PASS — HUMAN REVIEW REQUIRED' if passed else 'HOLD'}")
    print(f"Decision report: {out}")
    if not passed:
        raise SystemExit("Academic gate blocked: " + " ".join(blockers))


if __name__ == "__main__":
    main()
