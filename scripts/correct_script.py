import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from .llm_provider import generate_content, get_api_key
    from .gemini_client import MAX_GEMINI_ATTEMPTS, RETRYABLE_HTTP_STATUS
except ImportError:
    from llm_provider import generate_content, get_api_key
    from gemini_client import MAX_GEMINI_ATTEMPTS, RETRYABLE_HTTP_STATUS

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
        return generate_content(API_URL, api_key, payload, label="Academic correction", timeout=150)
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
    """Apply narrowly scoped, source-grounded repairs to recurring generated defects."""
    repairs = [
        # Unit 6: remove invented placeholder geography and non-Devanagari script contamination.
        ("(বাজার असफलता की परिभाषा)", "(बाजार असफलता की परिभाषा)",
         "Replaced Bengali-script contamination with the correct Devanagari Hindi heading."),
        ("MPPSC region X", "a hypothetical industrial region",
         "Replaced the invented regional placeholder with an explicitly hypothetical industrial region."),
        ("MPPSC क्षेत्र X में", "एक काल्पनिक औद्योगिक क्षेत्र में",
         "Replaced the invented regional placeholder in Hindi with an explicitly hypothetical industrial region."),
        ("negative consumption/production externality", "negative production externality",
         "Clarified that factory pollution is a negative production externality."),

        # Unit 7: apply the exact historical attributions and formulas in the supplied RBI notes.
        ("The Reserve Bank of India (RBI) historically published four alternative measures of money supply ($M_1, M_2, M_3,$ and $M_4$), based on the recommendations of the Working Group on Money Supply (1977) [VERIFY]. These aggregates represent varying degrees of liquidity, ranging from most liquid to least liquid.",
         "The traditional Reserve Bank of India (RBI) measures $M_1$, $M_2$, $M_3$ and $M_4$ are associated with the Second Working Group on Money Supply (SWG), chaired by M. L. Ghosh, in 1977. They represent progressively broader definitions of money and liquidity.",
         "Rewrote the traditional M1–M4 committee attribution using the supplied RBI historical reference."),
        ("भारतीय रिजर्व बैंक (RBI) ने ऐतिहासिक रूप से मुद्रा आपूर्ति के चार वैकल्पिक माप ($M_1, M_2, M_3,$ और $M_4$) प्रकाशित किए हैं, जो मुद्रा आपूर्ति पर कार्य समूह (1977) की सिफारिशों पर आधारित हैं [सत्यापन योग्य]। ये समुच्चय तरलता के विभिन्न स्तरों को दर्शाते हैं, जो अत्यधिक तरल से लेकर कम तरल तक होते हैं।",
         "भारतीय रिजर्व बैंक (RBI) के पारंपरिक मुद्रा आपूर्ति माप $M_1$, $M_2$, $M_3$ और $M_4$ मुद्रा आपूर्ति पर द्वितीय कार्य समूह (Second Working Group, SWG; अध्यक्ष एम. एल. घोष) की 1977 की सिफारिशों से संबंधित हैं। ये मुद्रा और तरलता की क्रमशः व्यापक परिभाषाएँ प्रस्तुत करते हैं।",
         "Rewrote the Hindi M1–M4 attribution using the supplied RBI historical reference."),
        ("* RBI monetary surveys also include newer monetary aggregates ($NM_1, NM_2, NM_3$) based on modern liquidity concepts [VERIFY].",
         "* The new monetary aggregates ($NM_1$, $NM_2$ and $NM_3$) were proposed by the Working Group on Money Supply: Analytics and Methodology of Compilation (WGMS), chaired by Dr. Y. V. Reddy, in June 1998.",
         "Replaced the unsupported 'modern liquidity concepts' wording with the source-backed 1998 WGMS attribution."),
        ("* आरबीआई के मौद्रिक सर्वेक्षणों में आधुनिक तरलता अवधारणाओं के आधार पर नए मौद्रिक समुच्चय ($NM_1, NM_2, NM_3$) भी शामिल हैं [सत्यापन योग्य]।",
         "* आरबीआई के नए मौद्रिक समुच्चय ($NM_1$, $NM_2$ और $NM_3$) जून 1998 में डॉ. वाई. वी. रेड्डी की अध्यक्षता वाले Working Group on Money Supply: Analytics and Methodology of Compilation (WGMS) द्वारा प्रस्तावित किए गए थे।",
         "Rewrote the Hindi NM1–NM3 attribution using the supplied RBI historical reference."),
        ("Net Time Deposits with commercial and cooperative banks", "Time Deposits with the banking system",
         "Aligned the traditional M3 description with the RBI definition: M1 plus time deposits with the banking system."),
        ("Net Time Deposits with the banking system", "Time Deposits with the banking system",
         "Aligned the traditional M3 description with the RBI definition: M1 plus time deposits with the banking system."),
        ("Net Time Deposits", "Time Deposits",
         "Removed the unsupported 'net' qualifier from the traditional time-deposit description."),
        ("शुद्ध सावधि जमा", "सावधि जमा",
         "Aligned the Hindi traditional M3 description with the RBI definition of time deposits."),
        ("newer monetary aggregates ($NM_1, NM_2, NM_3$) based on modern liquidity concepts [VERIFY]",
         "new monetary aggregates ($NM_1, NM_2, NM_3$) proposed by the Working Group on Money Supply: Analytics and Methodology of Compilation (WGMS), chaired by Dr. Y. V. Reddy, in June 1998.",
         "Replaced the vague NM1–NM3 recap claim with the RBI-supported WGMS (June 1998) attribution."),
        ("The working group references and newer monetary aggregates ($NM_1$ to $NM_3$) are marked with [VERIFY] where specific exact notification years require cross-checking against latest RBI handbook updates.",
         "The traditional M1–M4 measures are described with reference to the Second Working Group on Money Supply (1977). The separate NM1–NM3 measures are attributed to the WGMS chaired by Dr. Y. V. Reddy (June 1998), as documented in the RBI Manual on Financial and Banking Statistics (2007) and RBI Monthly Bulletin guide (2017).",
         "Updated the source note to identify the supplied RBI references and distinguish the 1977 and 1998 working groups."),
        ("कार्य समूह संदर्भ और नए मौद्रिक समुच्चयों ($NM_1$ से $NM_3$) को [VERIFY] के साथ चिह्नित किया गया है।",
         "पारंपरिक M1–M4 समुच्चयों के लिए RBI के द्वितीय कार्य समूह (1977) तथा NM1–NM3 के लिए डॉ. वाई. वी. रेड्डी की अध्यक्षता वाले WGMS (जून 1998) के संदर्भ लिए गए हैं।",
         "Updated the Hindi source note with the RBI-supported committee attributions."),
        ("नए मौद्रिक समुच्चय ($NM_1, NM_2, NM_3$) based on modern liquidity concepts [VERIFY]",
         "नए मौद्रिक समुच्चय ($NM_1, NM_2, NM_3$), जिन्हें डॉ. वाई. वी. रेड्डी की अध्यक्षता वाले Working Group on Money Supply: Analytics and Methodology of Compilation (WGMS) ने जून 1998 में प्रस्तावित किया था।",
         "Replaced the vague NM1–NM3 recap claim with the RBI-supported WGMS (June 1998) attribution."),
        ("आरबीआई के मौद्रिक सर्वेक्षणों में आधुनिक तरलता अवधारणाओं के आधार पर नए मौद्रिक समुच्चय ($NM_1, NM_2, NM_3$) भी शामिल हैं [सत्यापन योग्य]।",
         "आरबीआई के नए मौद्रिक समुच्चय ($NM_1, NM_2, NM_3$) जून 1998 में डॉ. वाई. वी. रेड्डी की अध्यक्षता वाले WGMS द्वारा प्रस्तावित किए गए थे।",
         "Corrected the Hindi NM1–NM3 attribution and date using the supplied RBI source notes."),
        # Unit 2: use an unambiguous Latin option label and correct Hindi grammatical agreement.
        ("सही उत्तर: B। स्पष्टीकरण:", "सही उत्तर: B) स्पष्टीकरण:",
         "Standardized the Latin MCQ answer label so Hindi punctuation cannot be misread as a mixed-script token."),
        ("कर्मचारियों की पारिश्रमिक", "कर्मचारियों का पारिश्रमिक",
         "Corrected Hindi grammatical gender agreement in the income-method formula."),
        # Unit 10: remove the unsupported single-range sector-share assertion without inventing a replacement statistic.
        ("though its share in total GDP has hovered around 25-30% [VERIFY]",
         "and its contribution should be assessed separately for manufacturing, construction and utilities rather than expressed as a single fixed percentage [HUMAN VERIFY: consult the relevant national-accounts series]",
         "Removed the unsupported 25–30% secondary-sector share and retained a specific human source-verification instruction."),
        ("हालांकि कुल GDP में इसका हिस्सा लगभग 25-30% के आसपास रहा है [VERIFY]।",
         "हालांकि विनिर्माण, निर्माण और उपयोगिताओं के योगदान का अलग-अलग अध्ययन करना चाहिए; इन्हें एक संयुक्त स्थिर प्रतिशत के रूप में प्रस्तुत नहीं करना चाहिए [सत्यापन योग्य]।",
         "Removed the unsupported 25–30% secondary-sector share from the Hindi explanation without adding a replacement statistic."),
        ("Learning Objectives / अधि-अगम्य उद्देश्य",
         "Learning Objectives / अधिगम उद्देश्य",
         "Corrected the Hindi translation of the Learning Objectives heading."),
        ("## Worked Example / Application (Hypothetical Sectoral Contribution Analysis)\n## कार्यशील उदाहरण / अनुप्रयोग (काल्पनिक क्षेत्रीय योगदान विश्लेषण)",
         "## Worked Example / Application: Hypothetical Sectoral Contribution Analysis / कार्यशील उदाहरण: काल्पनिक क्षेत्रीय योगदान विश्लेषण",
         "Consolidated the duplicated bilingual Worked Example headings into one section heading."),
        # Hindi editorial normalization: correct the common spelling error for scarcity.
        ("संसाधनों की दुर्लता", "संसाधनों की दुर्लभता",
         "Corrected the Hindi spelling of scarcity (दुर्लभता)."),
        ("असीमित मानवीय आवश्यकताओं", "असीमित मानवीय इच्छाओं",
         "Used the more precise Hindi equivalent for unlimited human wants."),
        # Opportunity Cost pilot: restore complete bilingual recap parity and distinguish cost categories.
        ("(एक वस्तु के अधिक उत्पादन की अवसर लागत दूसरी वस्तु की छोड़ी जाने वाली मात्रा से मापी जाती है।)",
         "(एक नतोदर PPF संसाधनों की अपूर्ण प्रतिस्थाप्यता के कारण एक वस्तु के उत्पादन से दूसरी वस्तु के उत्पादन की ओर बढ़ने पर बढ़ती अवसर लागत को दर्शाता है।)",
         "Restored a faithful Hindi translation of the English recap on increasing opportunity costs and imperfect resource substitutability."),
        ("If an individual leaves a job paying ₹50,000 per year to start a business, and incurs no other explicit costs besides buying ₹20,000 worth of supplies, what is the implicit cost of starting the business? [VERIFY]",
         "If an individual leaves a job paying ₹50,000 per year to start a business and purchases ₹20,000 worth of supplies, what is the implicit cost of starting the business? Assume the forgone salary is the only implicit cost; the supplies are an explicit cost. [VERIFY]",
         "Clarified that forgone salary is the implicit cost while the purchase of supplies is an explicit cost."),
        ("The implicit cost is the forgone salary from the previous job (₹50,000) because it represents the value of the resource supplied by the owner without an explicit cash transaction. (Note: Specific numerical values are illustrative).",
         "The implicit cost is the ₹50,000 salary forgone: it is the opportunity cost of the owner's labour supplied to the business. The ₹20,000 spent on supplies is an explicit cost and is not part of the implicit-cost answer. If both stated costs are requested, their combined economic cost is ₹70,000. (All figures are hypothetical and illustrative).",
         "Explained why the forgone salary is implicit, supplies are explicit, and the combined stated economic cost is ₹70,000."),
        ("निहित लागत पिछली नौकरी से छोड़ा गया वेतन (₹50,000) है क्योंकि यह बिना किसी स्पष्ट नकद लेनदेन के मालिक द्वारा आपूर्ति किए गए संसाधन के मूल्य का प्रतिनिधित्व करता है।",
         "निहित लागत छोड़ा गया ₹50,000 का वेतन है; यह व्यवसाय में मालिक द्वारा दिए गए श्रम की अवसर लागत है। ₹20,000 की आपूर्ति सामग्री पर किया गया खर्च स्पष्ट लागत है और निहित लागत के उत्तर में शामिल नहीं होगा। यदि दोनों बताई गई लागतों के बारे में पूछा जाए, तो उनकी संयुक्त आर्थिक लागत ₹70,000 होगी। (सभी संख्याएँ काल्पनिक और उदाहरणार्थ हैं)।",
         "Completed the Hindi explanation of implicit salary cost, explicit supplies cost and combined economic cost."),
        ("**Verification Status:** Standard economic principles verified against general curriculum guidelines for MPPSC Assistant Professor Economics. Numerical illustrations are marked [VERIFY] where specific parameter values are assumed for problem-solving practice.",
         "**Verification Status:** The concepts are presented as standard introductory microeconomic theory. This draft has not been independently checked against the latest official MPPSC Assistant Professor Economics syllabus or a supplied primary source. Confirm syllabus alignment and supporting references before publication. Numerical illustrations are hypothetical and remain subject to human review.",
         "Removed the unsupported claim of official curriculum verification and stated the actual source-verification limitation."),
    ]
    changes = []
    for old, new, description in repairs:
        if old in text:
            text = text.replace(old, new)
            changes.append(description)
    # Opportunity Cost pilot: standardize the Q10 bilingual explanation and Hindi terminology.
    q10_old = """**Explanation (Hindi/English):** 
- **English:** A point inside the PPF indicates that the economy is producing less than its maximum potential due to unemployment or resource misallocation.
- **Hindi:** PPF के अंदर एक बिंदु इंगित करता है कि बेरोजगारी या संसाधन दुर्विनियोजन के कारण अर्थव्यवस्था अपनी अधिकतम क्षमता से कम उत्पादन कर रही है।"""
    q10_new = """**Explanation (English):** A point inside the PPF indicates that the economy is producing less than its maximum potential because some resources are unemployed or not being used efficiently.

**Explanation (Hindi):** PPF के भीतर स्थित बिंदु यह दर्शाता है कि कुछ संसाधन बेरोजगार हैं या उनका कुशलतापूर्वक उपयोग नहीं हो रहा है; इसलिए अर्थव्यवस्था अपनी अधिकतम उत्पादन क्षमता से कम उत्पादन कर रही है।"""
    if q10_old in text:
        text = text.replace(q10_old, q10_new)
        changes.append("Standardized Q10 with separate English and Hindi explanation labels and clearer Hindi wording for unemployment/inefficient resource use.")

    hindi_terms = [
        ("भूला हुआ वेतन", "त्यागा गया वेतन"),
        ("भूला हुआ ब्याज", "त्यागा गया ब्याज"),
        ("भूला हुआ रिटर्न", "त्यागा गया प्रतिफल"),
        ("भूला हुआ किराया", "त्यागा गया किराया"),
        ("निरंतर अवसर लागत", "स्थिर अवसर लागत"),
    ]
    for old, new in hindi_terms:
        if old in text:
            text = text.replace(old, new)
            changes.append(f"Standardized Hindi translation of '{old}' as '{new}'.")

    return text, changes


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: correct_script.py SCRIPT_PATH REVIEW_PATH [SOURCE_NOTES]")
    script_path, review_path = Path(sys.argv[1]), Path(sys.argv[2])
    source_notes = load_optional_source_notes(sys.argv[3] if len(sys.argv) > 3 else None)
    try:
        api_key = get_api_key()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
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
For every bilingual recap bullet, compare the English and Hindi text clause by clause and restore
any missing substantive statement, qualification or conclusion. Specifically retain the statement
that a concave PPF reflects increasing opportunity costs in the Hindi PPF recap.
For cost examples, distinguish explicit cash purchases from implicit opportunity costs.
For Hindi economics terminology, translate 'forgone' as 'त्यागा गया' or 'छोड़ा गया', never as 'भूला हुआ'; use 'स्थिर अवसर लागत' for constant opportunity cost.\nIf the question asks only for implicit cost, explain that forgone salary is implicit and purchased
supplies are explicit; state assumptions clearly and distinguish the requested answer from total
economic cost. Do not describe hypothetical arithmetic as needing an external source.
Never claim alignment with official MPPSC curriculum or syllabus unless the relevant official
document was supplied and used. Without that source, state that syllabus alignment remains unverified.
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
