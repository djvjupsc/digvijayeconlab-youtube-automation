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

    punctuation_count = text.count("。")
    if punctuation_count:
        text = text.replace("。", "।")
        changes.append(
            f"Replaced {punctuation_count} non-standard full-stop punctuation mark(s) with Devanagari danda."
        )

    remaining = []
    if heading_old in text:
        remaining.append("incorrect Hindi assumptions heading")
    if re.search(
        r"\*\*गिफ्फेन वस्तुएं\s*\(Giffen Goods\):\*\*\s*"
        r"गिफ्फेन वस्तु एक ऐसी हीन वस्तु",
        text,
    ):
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
