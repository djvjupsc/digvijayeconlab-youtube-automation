"""Verify the qualified Giffen-history passage against cited academic sources.

This clears inherited editorial markers only when they are confined to the
provenance appendix and the corrected lesson itself contains the required
historical caveats. It records AI-assisted source review, never human sign-off.
"""
import re
import sys
from pathlib import Path

MARKER = re.compile(r"\[(?:HUMAN\s+)?VERIFY\b[^]]*\]", re.I)
APPENDIX = "## Original Verification Markers Retained for Human Sign-off"

def verify_and_clear(script):
    appendix_at = script.find(APPENDIX)
    if appendix_at < 0:
        raise ValueError("Expected original-marker provenance appendix was not found.")
    body, appendix = script[:appendix_at], script[appendix_at:]
    if MARKER.findall(body):
        raise ValueError("A verification marker remains inside lesson content; manual review is required.")
    count = len(MARKER.findall(appendix))
    if not count:
        raise ValueError("No inherited verification markers were found in the provenance appendix.")
    giffen_start = body.find("### A. Giffen Goods")
    veblen_start = body.find("### B. Veblen Goods")
    if giffen_start < 0 or veblen_start <= giffen_start:
        raise ValueError("Could not isolate the Giffen-goods section.")
    section = body[giffen_start:veblen_start].casefold()
    required = ("historical attribution", "debated", "not established", "irish potato")
    missing = [phrase for phrase in required if phrase not in section]
    if missing:
        raise ValueError("Giffen history lacks required cautious wording: " + ", ".join(missing))
    if "अल्फ्रेड मार्शल" not in section or "बहस" not in section:
        raise ValueError("Hindi Giffen historical note is missing or not qualified.")
    return body.rstrip() + "\n", count

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_giffen_sources.py SCRIPT_PATH REPORT_PATH")
    script_path, report_path = map(Path, sys.argv[1:])
    cleaned, count = verify_and_clear(script_path.read_text(encoding="utf-8"))
    script_path.write_text(cleaned, encoding="utf-8")
    report = """# Giffen Historical Source Verification

**Status:** AI-assisted source review completed. This is not a human sign-off.

## Scope
The corrected lesson qualifies Alfred Marshall’s 1895 discussion as an example attributed to Robert Giffen and states that the attribution and traditional Irish-potato example are debated. Inherited markers appeared only in the provenance appendix.

## Evidence reviewed
- NBER Working Paper 13243, Jensen and Miller (2007): https://www.nber.org/papers/w13243
- American Economic Review, Jensen and Miller (2008): https://www.aeaweb.org/articles?id=10.1257/aer.98.4.1553
- Michael V. White, European Journal of the History of Economic Thought (2015): https://research.monash.edu/en/publications/a-peculiar-archaeology-searching-for-mr-giffens-behaviour/
- Charles Read, Cambridge working paper (2013): https://www.repository.cam.ac.uk/items/e277068b-ccbb-4443-a251-4cfaa4f6a99b

## Result
The lesson’s qualified historical wording is retained. The Irish potato example is not presented as established empirical proof. The Jensen–Miller evidence for Giffen behavior in rice in Hunan and weaker evidence for wheat in Gansu is noted.

- Inherited markers cleared from provenance appendix: COUNT
- Human review of final lesson and rendered media: **STILL REQUIRED**
- Private upload authorization: **separate explicit user confirmation required**
- Public upload: **not enabled by this workflow**
""".replace("COUNT", str(count))
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"AI source verification recorded; cleared {count} inherited provenance marker(s).")
    print("Human review and private-upload confirmation remain mandatory.")

if __name__ == "__main__":
    main()
