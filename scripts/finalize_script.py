"""Deterministic, narrowly scoped editorial normalization for the Law of Demand pilot."""
import argparse
from pathlib import Path


REPLACEMENTS = (
    (
        "मांग का नियम की मान्यताएं",
        "मांग के नियम की मान्यताएं",
        "Corrected Hindi postposition in the Law of Demand assumptions heading.",
    ),
    (
        "गिफ्फेन वस्तुएं (Giffen Goods): गिफ्फेन वस्तु एक ऐसी हीन वस्तु (inferior good) है जिसके लिए",
        "गिफ्फेन वस्तुएं (Giffen Goods): गिफ्फेन वस्तुएं ऐसी हीन वस्तुएं (inferior goods) हैं जिनके लिए",
        "Aligned plural Hindi heading and definition for Giffen goods.",
    ),
)


def normalize_script(text):
    """Apply only the two audited Hindi wording fixes and standard Hindi punctuation."""
    changes = []
    for old, new, description in REPLACEMENTS:
        count = text.count(old)
        if count:
            text = text.replace(old, new)
            changes.append(f"{description} Occurrences: {count}.")

    punctuation_count = text.count("。")
    if punctuation_count:
        text = text.replace("。", "।")
        changes.append(
            f"Replaced {punctuation_count} non-standard ideographic full stop(s) with Devanagari danda."
        )
    return text, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script_path", help="Corrected Markdown script to normalize.")
    parser.add_argument("--log-path", default="output/corrections/editorial-normalization.md")
    args = parser.parse_args()

    script_path = Path(args.script_path)
    if not script_path.is_file():
        raise SystemExit(f"Corrected script not found: {script_path}")

    original = script_path.read_text(encoding="utf-8")
    normalized, changes = normalize_script(original)
    if normalized != original:
        script_path.write_text(normalized, encoding="utf-8")

    log_path = Path(args.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Deterministic Editorial Normalization",
        "",
        "> Narrowly scoped language and typography repairs only. No economic claim or factual caveat is added, removed, or certified.",
        "",
        "## Changes",
        "",
    ]
    lines.extend(f"- {item}" for item in changes)
    if not changes:
        lines.append("- No targeted changes were needed.")
    lines += ["", "## Scope", "", "- Hindi assumptions-heading postposition.", "- Giffen-goods Hindi plural consistency.", "- Devanagari punctuation normalization.", ""]
    log_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Editorial normalization complete: {len(changes)} change type(s).")
    print(f"Audit log: {log_path}")


if __name__ == "__main__":
    main()
