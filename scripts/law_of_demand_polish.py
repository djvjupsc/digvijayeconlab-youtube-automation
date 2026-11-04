"""Narrow, deterministic editorial repairs for the Law of Demand pilot.

These are limited to known wording and punctuation defects identified in the
Run #9 academic review. They do not modify economics claims or remove caveats.
"""
import argparse
import re
from pathlib import Path


def apply_law_of_demand_polish(text):
    changes = []

    heading_old = "मांग का नियम की मान्यताएं"
    heading_new = "मांग के नियम की मान्यताएँ"
    if heading_old in text:
        text = text.replace(heading_old, heading_new)
        changes.append("Corrected Hindi genitive/postposition in the assumptions heading.")

    giffen_pattern = re.compile(
        r"गिफ्फेन वस्तु एक ऐसी हीन वस्तु\s*\(inferior good\)\s*है जिसके लिए "
        r"नकारात्मक आय प्रभाव,?\s*प्रतिस्थापन प्रभाव से अधिक मजबूत होता है,?\s*"
        r"जिससे कीमत बढ़ने पर मांग भी बढ़ सकती है[।.。]"
    )
    giffen_replacement = (
        "गिफ्फेन वस्तुएँ ऐसी हीन वस्तुएँ (inferior goods) हैं जिनमें "
        "नकारात्मक आय प्रभाव प्रतिस्थापन प्रभाव से अधिक प्रबल होता है; "
        "इसलिए, विशेष परिस्थितियों में, कीमत बढ़ने पर मांग की मात्रा भी बढ़ सकती है।"
    )
    text, count = giffen_pattern.subn(giffen_replacement, text)
    if count:
        changes.append(
            f"Standardized plural/singular agreement in {count} Hindi Giffen-goods definition(s)."
        )

    # The pilot's original schedule (P=10,20,30,40; Qd=20,15,10,5)
    # is consistent with Qd=25-0.5P, not Qd=40-2P. Keep the worked
    # example, derivative and table heading mathematically consistent.
    if "Q_d = 40 - 2P" in text:
        text = text.replace("Q_d = 40 - 2P", "Q_d = 25 - 0.5P")
        changes.append("Corrected the linear demand function to match the published schedule values.")
    if "dQ_d / dP = -2 < 0" in text:
        text = text.replace("dQ_d / dP = -2 < 0", "dQ_d / dP = -0.5 < 0")
        changes.append("Corrected the derivative to match the revised linear demand function.")

    text = text.replace("उपभोक्ता अब अपेक्षाकृत महंगी वस्तुओं के बजाय इस सस्ती वस्तु को चुनते हैं", "उपभोक्ता अब अपेक्षाकृत महंगी वस्तुओं के बजाय इस अपेक्षाकृत सस्ती वस्तु को चुनते हैं")
    text = text.replace("अपेक्षित रूप से सस्ती कीमत", "अपेक्षाकृत सस्ती कीमत")
    text = text.replace("गिफ्फेन वस्तुएं", "गिफ्फेन वस्तुएँ")
    text = text.replace("वेब्लेन वस्तुएं", "वेब्लेन वस्तुएँ")
    text = text.replace("घटिया वस्तुएं", "हीन वस्तुएँ")
    text = text.replace("घटिया वस्तुएँ", "हीन वस्तुएँ")

    punctuation_count = text.count("。")
    if punctuation_count:
        text = text.replace("。", "।")
        changes.append(
            f"Replaced {punctuation_count} non-standard full-stop punctuation mark(s) with Devanagari danda."
        )

    remaining = []
    if heading_old in text:
        remaining.append("incorrect Hindi assumptions heading")
    giffen_heading = re.search(
        r"\*\*गिफ्फेन वस्तुएँ?\s*\(Giffen Goods\):\*\*",
        text,
    )
    if giffen_heading:
        section = text[giffen_heading.end():]
        next_heading = re.search(r"\n\s*#{1,6}\s|\n\s*\*\*Q\d+\.", section)
        if next_heading:
            section = section[:next_heading.start()]
        if "गिफ्फेन वस्तु एक ऐसी हीन वस्तु" in section:
            remaining.append("singular Giffen definition under a plural heading")
    if "。" in text:
        remaining.append("non-standard full-stop punctuation")
    if remaining:
        raise ValueError(
            "Known Hindi editorial defects remain after deterministic polish: "
            + ", ".join(remaining)
        )

    return text, changes


def main():
    parser = argparse.ArgumentParser(
        description="Apply limited deterministic editorial repairs to the Law of Demand pilot."
    )
    parser.add_argument("script_path")
    args = parser.parse_args()
    path = Path(args.script_path)
    if not path.is_file():
        raise SystemExit(f"Corrected script not found: {path}")
    original = path.read_text(encoding="utf-8")
    revised, changes = apply_law_of_demand_polish(original)
    if changes:
        path.write_text(revised, encoding="utf-8")
        for item in changes:
            print(f"EDITORIAL REPAIR: {item}")
    else:
        print("No known Law of Demand editorial repairs were needed.")
    print("Status: LIMITED TEXT POLISH ONLY — academic review and human approval remain required.")


if __name__ == "__main__":
    main()
