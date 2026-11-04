"""Verify the qualified Giffen-history passage in a corrected lesson.

The verifier accepts common Markdown heading/list/bold-label formats. It only
removes inherited verification markers when they are confined to the provenance
appendix. A lesson with no inherited markers is valid without an empty appendix.
This is an automated wording/structure check, not independent source verification
or human sign-off.
"""
import re
import sys
from pathlib import Path

MARKER = re.compile(r"\[(?:HUMAN\s+)?VERIFY\b[^]]*\]", re.I)
APPENDIX = re.compile(
    r"(?im)^\s*#{1,6}\s+Original Verification Markers Retained for Human Sign-off\s*$"
)
LABEL_LINE = re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]+)?(?:[-*+][ \t]+)?"
    r"(?:\*\*|__)?(?:[A-Z]\.\s*)?"
    r"(?:Giffen\s+Goods|Veblen(?:\s*/\s*Status)?\s+Goods)\b"
)


def _find_label(pattern, text):
    return next((match for match in LABEL_LINE.finditer(text)
                 if re.search(pattern, match.group(0), re.I)), None)


def _has_non_established_caveat(section):
    patterns = (
        r"\bnot\s+established\b",
        r"\bnot\s+(?:state|present|treat|describe)\b.{0,120}"
        r"\b(?:settled\s+fact|empirical(?:ly)?\s+(?:proven|established|confirmed)|proven)\b",
    )
    return any(re.search(pattern, section, re.I | re.S) for pattern in patterns)


def verify_and_clear(script):
    appendix_match = APPENDIX.search(script)
    if appendix_match:
        body = script[:appendix_match.start()]
        appendix = script[appendix_match.start():]
        if MARKER.search(body):
            raise ValueError(
                "A verification marker remains inside lesson content; manual review is required."
            )
        marker_count = len(MARKER.findall(appendix))
        searchable = body
        cleaned_body = body.rstrip() + "\n"
    else:
        if MARKER.search(script):
            raise ValueError(
                "A verification marker remains but no provenance appendix identifies it as inherited."
            )
        marker_count = 0
        searchable = script
        cleaned_body = script.rstrip() + "\n"

    giffen_match = _find_label(r"Giffen\s+Goods", searchable)
    veblen_match = _find_label(r"Veblen", searchable)
    if not giffen_match or not veblen_match or veblen_match.start() <= giffen_match.start():
        raise ValueError("Could not isolate the Giffen-goods section using supported Markdown labels.")

    section = searchable[giffen_match.start():veblen_match.start()].casefold()
    requirements = {
        "historical note/attribution": r"historical\s+(?:note|attribution)",
        "qualified or debated attribution": r"\b(?:debated|disputed|scholarly\s+debate)\b",
        "traditional Irish potato example": r"\birish\s+potato(?:es)?\b",
    }
    missing = [label for label, pattern in requirements.items()
               if not re.search(pattern, section, re.I)]
    if not _has_non_established_caveat(section):
        missing.append("explicit statement that the example is not established fact")
    if missing:
        raise ValueError("Giffen history lacks required cautious wording: " + ", ".join(missing))
    if "अल्फ्रेड मार्शल" not in section or "बहस" not in section:
        raise ValueError("Hindi Giffen historical note is missing or not qualified.")

    return cleaned_body, marker_count


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_giffen_sources.py SCRIPT_PATH REPORT_PATH")
    script_path, report_path = map(Path, sys.argv[1:])
    cleaned, count = verify_and_clear(script_path.read_text(encoding="utf-8"))
    script_path.write_text(cleaned, encoding="utf-8")
    report = """# Giffen Historical Source Verification

**Status:** AI-assisted wording/structure review completed. This is not a human sign-off or independent verification of the cited works.

## Scope
The corrected lesson must qualify Alfred Marshall’s 1895 discussion as an example attributed to Robert Giffen, state that the historical attribution and traditional Irish-potato example are debated, and avoid presenting the example as established empirical fact.

## Evidence references supplied to the lesson
- NBER Working Paper 13243, Jensen and Miller (2007): https://www.nber.org/papers/w13243
- American Economic Review, Jensen and Miller (2008): https://www.aeaweb.org/articles?id=10.1257/aer.98.4.1553
- Michael V. White, European Journal of the History of Economic Thought (2015): https://research.monash.edu/en/publications/a-peculiar-archaeology-searching-for-mr-giffens-behaviour/
- Charles Read, Cambridge working paper (2013): https://www.repository.cam.ac.uk/items/e277068b-ccbb-4443-a251-4cfaa4f6a99b

## Result
The required English and Hindi historical caveats are present. This automated check verifies wording and section structure only; it does not fetch or independently validate these sources or certify the economics.

- Inherited markers cleared from provenance appendix: COUNT
- Human review of final lesson and rendered media: **STILL REQUIRED**
- Private upload authorization: **separate explicit user confirmation required**
- Public upload: **not enabled by this workflow**
""".replace("COUNT", str(count))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"Qualified Giffen wording verified; cleared {count} inherited provenance marker(s).")
    print("This is not independent source verification. Human review remains mandatory.")


if __name__ == "__main__":
    main()
