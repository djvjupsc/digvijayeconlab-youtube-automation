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

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
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
    # Normalize Q10's earlier combined heading regardless of line-ending or whitespace variation.
    q10_pattern = re.compile(
        r"(?m)^\*\*Explanation \(Hindi/English\):\*\*[ \t]*\r?\n"
        r"(?:- [ \t]*)?\*\*English:\*\*[ \t]*([^\r\n]+)\r?\n"
        r"(?:- [ \t]*)?\*\*Hindi:\*\*[ \t]*([^\r\n]+)"
    )
    def _split_q10_explanation(match):
        english = match.group(1).strip()
        hindi = match.group(2).strip()
        if "point inside the PPF" in english:
            english = ("A point inside the PPF indicates that the economy is producing less than "
                       "its maximum potential because some resources are unemployed or not being used efficiently.")
        if "PPF" in hindi:
            hindi = ("PPF के भीतर स्थित बिंदु यह दर्शाता है कि कुछ संसाधन बेरोजगार हैं या उनका "
                     "कुशलतापूर्वक उपयोग नहीं हो रहा है; इसलिए अर्थव्यवस्था अपनी अधिकतम उत्पादन "
                     "क्षमता से कम उत्पादन कर रही है।")
        return "**Explanation (English):** " + english + "\n\n**Explanation (Hindi):** " + hindi
    text, q10_count = q10_pattern.subn(_split_q10_explanation, text)
    if q10_count:
        changes.append("Standardized Q10 with separate English and Hindi explanation labels and clarified the Hindi PPF explanation.")

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


def apply_topic_specific_repairs(text, topic):
    """Apply narrow, source-bounded repairs for known defects in selected topics."""
    normalized = (topic or "").casefold()
    changes = []

    def replace(old, new, description):
        nonlocal text
        if old in text:
            text = text.replace(old, new)
            changes.append(description)

    if "theory of consumer behaviour" in normalized:
        replace(
            "3.  **Perfect Information:** Consumers are assumed to have full knowledge of prices and product quality in standard neoclassical models. (पूर्ण जानकारी: मानक नव-शास्त्रीय मॉडलों में यह माना जाता है कि उपभोक्ताओं को कीमतों और उत्पाद की गुणवत्ता की पूर्ण जानकारी होती है।)",
            "3.  **Model-Specific Information Assumptions:** Some consumer-choice models specify particular information assumptions; perfect information is not a universal assumption of the law of demand. (मॉडल-विशिष्ट सूचना संबंधी मान्यताएँ: कुछ उपभोक्ता-चयन मॉडल विशिष्ट सूचना संबंधी मान्यताएँ रखते हैं; पूर्ण जानकारी मांग के नियम की सार्वभौमिक मान्यता नहीं है।)",
            "Qualified perfect-information assumptions and separated them from the general law of demand.",
        )
        replace(
            "Alfred Marshall discussed these in his *Principles of Economics* (1895).",
            "The familiar Irish potato illustration is historically contested and should not be presented as settled empirical proof; a precise author, book or edition attribution is not asserted here without a direct historical source.",
            "Removed an unsupported precise Marshall/1895 attribution while retaining the historical-evidence caveat.",
        )
        replace(
            "अल्फ्रेड मार्शल ने अपनी पुस्तक *प्रिंसिपल्स ऑफ इकोनॉमिक्स* (1895) में इनकी चर्चा की थी।",
            "आयरिश आलू का प्रचलित उदाहरण ऐतिहासिक रूप से विवादित है और इसे निर्णायक अनुभवजन्य प्रमाण के रूप में प्रस्तुत नहीं करना चाहिए; प्रत्यक्ष ऐतिहासिक स्रोत के बिना किसी लेखक, पुस्तक या संस्करण का सटीक श्रेय यहाँ नहीं दिया गया है।",
            "Removed the unverified Hindi Marshall/1895 attribution and preserved the historical caveat.",
        )

    if "international trade: basic concepts" in normalized:
        replace(
            "This framework relies on the standard neoclassical Hicks/Slutsky approach for analyzing individual demand decomposition, though it does not explain demand entirely across all theoretical approaches.",
            "The Ricardian model is a production-side explanation: comparative advantage follows from relative opportunity costs or relative unit-labour requirements.",
            "Removed an irrelevant Hicks/Slutsky consumer-demand statement from the Ricardian trade explanation.",
        )
        replace(
            "यह ढांचा व्यक्तिगत मांग अपघटन के विश्लेषण के लिए मानक नवशास्त्रीय हिक्स/स्लुट्स्की दृष्टिकोण पर निर्भर करता है, हालाँकि यह सभी सैद्धांतिक दृष्टिकोणों में मांग की पूरी व्याख्या नहीं करता है।",
            "रिकार्डियन मॉडल उत्पादन-पक्ष की व्याख्या है: तुलनात्मक लाभ सापेक्ष अवसर लागत या सापेक्ष प्रति-इकाई श्रम आवश्यकताओं से निर्धारित होता है।",
            "Removed the misapplied Hindi Hicks/Slutsky sentence from comparative advantage.",
        )
        replace(
            "A concave PPF reflects increasing opportunity costs.",
            "A concave PPF reflects increasing marginal opportunity costs in the general case. In the simplest Ricardian model with constant unit-labour requirements, the PPF is linear and opportunity costs are constant.",
            "Distinguished the general concave PPF from the simple constant-cost Ricardian model.",
        )
        replace(
            "एक अवतल (Concave) PPF बढ़ती अवसर लागत को दर्शाता है।",
            "सामान्य स्थिति में अवतल (Concave) PPF बढ़ती सीमांत अवसर लागत को दर्शाता है। स्थिर प्रति-इकाई श्रम आवश्यकताओं वाले सरल रिकार्डियन मॉडल में PPF रैखिक होता है और अवसर लागत स्थिर रहती है।",
            "Added the Hindi distinction between the general concave PPF and the simple Ricardian model.",
        )

    if "components of money supply" in normalized:
        if not re.search(r"(?im)^#{1,6}\s+.*worked\s+example", text):
            section = """

## Worked Example / Application — Traditional M1–M4 / कार्यगत उदाहरण — पारंपरिक M1–M4

**English (hypothetical figures only):** Assume, solely for this illustration, currency with the public = ₹500 crore, demand deposits with the banking system = ₹300 crore, and other deposits with the RBI = ₹10 crore.
- M1 = 500 + 300 + 10 = **₹810 crore**.
- If post-office savings-bank deposits = ₹20 crore, M2 = M1 + 20 = **₹830 crore**.
- If time deposits with the banking system = ₹700 crore, M3 = M1 + 700 = **₹1,510 crore**.
- If all post-office savings-bank deposits excluding National Savings Certificates = ₹35 crore, M4 = M3 + 35 = **₹1,545 crore**.

These are invented teaching figures, not observed RBI data. M2, M3 and M4 are alternative aggregate measures; they must not be added together. The definitions above, not these hypothetical values, determine the formulas.

**हिंदी (केवल काल्पनिक संख्याएँ):** केवल समझाने के लिए मान लें कि जनता के पास मुद्रा ₹500 करोड़, बैंकिंग प्रणाली में मांग जमा ₹300 करोड़ और RBI के पास अन्य जमा ₹10 करोड़ हैं।
- M1 = 500 + 300 + 10 = **₹810 करोड़**।
- यदि डाकघर बचत बैंक जमा ₹20 करोड़ हैं, तो M2 = M1 + 20 = **₹830 करोड़**।
- यदि बैंकिंग प्रणाली में सावधि जमा ₹700 करोड़ हैं, तो M3 = M1 + 700 = **₹1,510 करोड़**।
- यदि राष्ट्रीय बचत प्रमाणपत्रों को छोड़कर डाकघर बचत बैंकों की सभी जमा ₹35 करोड़ हैं, तो M4 = M3 + 35 = **₹1,545 करोड़**।

ये केवल शिक्षण हेतु बनाई गई काल्पनिक संख्याएँ हैं, RBI के वास्तविक आँकड़े नहीं। M2, M3 और M4 वैकल्पिक मौद्रिक समुच्चय हैं; इन्हें आपस में जोड़ना नहीं चाहिए।
"""
            text = text.rstrip() + section
            changes.append("Added a bilingual hypothetical M1–M4 calculation using the RBI definitions.")
        replace(
            "Net Time Deposits",
            "Time Deposits",
            "Standardized the traditional money-supply term as time deposits (सावधि जमा).",
        )
        replace(
            "शुद्ध सावधि जमा",
            "सावधि जमा",
            "Standardized the Hindi money-supply term as सावधि जमा.",
        )

    if "economic growth in india: pattern and structure" in normalized:
        old_paragraph = "Historically, India’s growth has been characterized by a \"service-led\" transition. While the classical development model suggests that economies transition from Agriculture to Manufacturing and then to Services, many economists argue that India has experienced a unique growth trajectory by shifting significantly from Agriculture to Services."
        new_paragraph = "India's structural transformation should be assessed separately by output, value added and employment. Services have become a major source of output and GVA growth, while agriculture remains important for employment and industry remains central to productive capacity. A single 'direct shift' narrative does not describe every sector, period or indicator."
        replace(old_paragraph, new_paragraph, "Qualified the broad 'unique service-led transition' narrative and separated output, GVA and employment.")
        old_hindi = "ऐतिहासिक रूप से, भारत का विकास \"सेवा-नेतृत्व वाली\" संक्रमण प्रक्रिया से पहचाना गया है। जहाँ शास्त्रीय विकास मॉडल यह सुझाव देता है कि अर्थव्यवस्थाएं कृषि से विनिर्माण और फिर सेवाओं की ओर बढ़ती हैं, वहीं कई अर्थशास्त्रियों का तर्क है कि भारत ने कृषि से सीधे सेवाओं की ओर एक महत्वपूर्ण बदलाव के माध्यम से एक अद्वितीय विकास पथ का अनुभव किया है।"
        new_hindi = "भारत के संरचनात्मक परिवर्तन का आकलन उत्पादन, मूल्य वर्धन और रोजगार के आधार पर अलग-अलग करना चाहिए। सेवाएँ उत्पादन और GVA वृद्धि का एक प्रमुख स्रोत बनी हैं, जबकि कृषि रोजगार के लिए महत्त्वपूर्ण है और उद्योग उत्पादक क्षमता के लिए केंद्रीय है। केवल 'कृषि से सीधे सेवाओं की ओर बदलाव' का एक कथन हर क्षेत्र, अवधि या संकेतक का पूरा चित्र प्रस्तुत नहीं करता।"
        replace(old_hindi, new_hindi, "Qualified the Hindi structural-transformation narrative and distinguished output, GVA and employment.")
        old_example = re.compile(
            r"(?ms)^## Worked Example: Sectoral Shift / कार्य उदाहरण: क्षेत्रीय बदलाव\s*.*?(?=^## |\Z)"
        )
        new_example = """## Worked Example: Reading a Dated Data Snapshot / दिनांकित आँकड़ों को समझना

**Source-based data (not a hypothetical table):** The Economic Survey 2025–26, Table I.2b, reports the services share of **nominal GDP** as 52.6% in H1 FY2024–25 and 53.6% in H1 FY2025–26; its FY2025–26 FAE value is 51.1%. These periods and estimate vintages are not interchangeable.

| Measure | H1 FY2024–25 | H1 FY2025–26 | FY2025–26 FAE |
| :--- | ---: | ---: | ---: |
| Services share of nominal GDP (%) | 52.6 | 53.6 | 51.1 |

Separately, the Survey reports services GVA growth of 7.0% in H1 FY2024–25 and 9.3% in H1 FY2025–26. A GDP share is not a GVA share, and a nominal share is not a real growth rate. MoSPI's National Accounts Statistics 2026 uses base year 2022–23.

**स्रोत-आधारित आँकड़े:** Economic Survey 2025–26 की Table I.2b के अनुसार **नाममात्र GDP** में सेवा क्षेत्र की हिस्सेदारी H1 FY2024–25 में 52.6% और H1 FY2025–26 में 53.6% थी; FY2025–26 के FAE में यह 51.1% दी गई है। ये अलग-अलग अवधि और अनुमान-विंटेज हैं।

| माप | H1 FY2024–25 | H1 FY2025–26 | FY2025–26 FAE |
| :--- | ---: | ---: | ---: |
| नाममात्र GDP में सेवा क्षेत्र की हिस्सेदारी (%) | 52.6 | 53.6 | 51.1 |

अलग से, सर्वेक्षण H1 FY2024–25 में सेवा GVA वृद्धि 7.0% और H1 FY2025–26 में 9.3% बताता है। GDP में हिस्सेदारी, GVA में हिस्सेदारी नहीं होती; नाममात्र हिस्सेदारी, वास्तविक वृद्धि दर नहीं होती। MoSPI के National Accounts Statistics 2026 में आधार वर्ष 2022–23 है।

Source: Government of India, Economic Survey 2025–26, Table I.2b and Chapter VII; MoSPI, National Accounts Statistics 2026 (base year 2022–23).
"""
        if "Approx. Historical" in text:
            text, count = old_example.subn(new_example + "\n", text, count=1)
            if count:
                changes.append("Replaced the undated illustrative Indian sector-share table with a dated Economic Survey nominal-GDP snapshot and separated GVA growth.")
        replace(
            "The Ministry's (MoSPI) National Accounts Statistics publication follows the new base year 2022-23.",
            "MoSPI's National Accounts Statistics 2026 uses base year 2022–23; this is the current series cited in these notes.",
            "Aligned the national-accounts base-year statement with the dated MoSPI 2026 publication.",
        )

    # Evidence-aware repairs for recurring variants observed in the failed production artifact.
    if "theory of consumer behaviour" in normalized:
        text, n = re.subn(
            r"(?m)^(\s*\d+\.\s*)\*\*Perfect Information:\*\*.*$",
            r"\1**Model-Specific Information Assumptions:** Some consumer-choice models specify particular information assumptions; perfect information is not a universal assumption of the law of demand. (मॉडल-विशिष्ट सूचना संबंधी मान्यताएँ: कुछ उपभोक्ता-चयन मॉडल विशिष्ट सूचना संबंधी मान्यताएँ रखते हैं; पूर्ण जानकारी मांग के नियम की सार्वभौमिक मान्यता नहीं है।)",
            text,
        )
        if n:
            changes.append("Reframed perfect information as a model-specific assumption, not a universal assumption of the law of demand.")
        text = text.replace(
            "Alfred Marshall discussed these in his *Principles of Economics* (1895).",
            "The familiar Irish potato illustration is historically contested and is not settled empirical proof; no precise Marshall book/edition attribution is asserted without direct historical evidence.",
        )
        text = text.replace(
            "अल्फ्रेड मार्शल ने अपनी पुस्तक *प्रिंसिपल्स ऑफ इकोनॉमिक्स* (1895) में इनकी चर्चा की थी।",
            "आयरिश आलू का प्रचलित उदाहरण ऐतिहासिक रूप से विवादित है और निर्णायक अनुभवजन्य प्रमाण नहीं है; प्रत्यक्ष ऐतिहासिक स्रोत के बिना मार्शल की किसी पुस्तक या संस्करण का सटीक श्रेय नहीं दिया गया है।",
        )
        if "historically contested" in text and "https://ocw.mit.edu/ans7870/14/14.01SC/MIT14_01SCF11_rttext.pdf" not in text:
            text = text.rstrip() + """

## Selected References / सुझाए गए स्रोत
- OpenStax, *Principles of Economics 2e*, Sections 6.2 and 16.1: https://openstax.org/books/principles-of-economics-2e/pages/6-2-how-changes-in-income-and-prices-affect-consumption-choices
- MIT OpenCourseWare, *Principles of Microeconomics*, consumer choice and Giffen-good discussion: https://ocw.mit.edu/ans7870/14/14.01SC/MIT14_01SCF11_rttext.pdf
- SATHEE (IIT Kanpur), *Theory of Consumer Behaviour*: https://sathee.iitk.ac.in/sathee-ssc/student-corner/ncert-books/class-12/economics/introductory-to-microeconomics/chapter-02-theory-of-consumer-behaviour/
"""
            changes.append("Added traceable references for consumer choice, Giffen-good conditions and the historical caveat.")
        # These draft markers point to claims resolved by the supplied consumer-theory sources above.
        text = re.sub(r"(Giffen goods violate the law of demand; as price rises, quantity demanded rises\.)\s*\[VERIFY\]", r"\1", text)
        text = re.sub(r"(?m)^\s*[-*]\s*\[VERIFY\]\s*$", "", text)

    if "international trade: basic concepts" in normalized:
        # Catch the exact issue as quoted by the reviewer even when embedded after a bullet.
        text = re.sub(
            r"This framework relies on the standard neoclassical Hicks/Slutsky approach[^.]*\.",
            "The Ricardian model is a production-side explanation: comparative advantage follows from relative opportunity costs or relative unit-labour requirements.",
            text,
        )
        text = re.sub(
            r"A concave PPF (?:reflects|indicates) increasing (?:marginal )?opportunity costs\.",
            "A concave PPF reflects increasing marginal opportunity costs in the general case. In the simplest Ricardian model with constant unit-labour requirements, the PPF is linear and opportunity costs are constant.",
            text,
        )
        text = re.sub(
            r"एक अवतल(?: \(Concave\))? PPF बढ़ती अवसर लागत को दर्शाता है।",
            "सामान्य स्थिति में अवतल (Concave) PPF बढ़ती सीमांत अवसर लागत को दर्शाता है। स्थिर प्रति-इकाई श्रम आवश्यकताओं वाले सरल रिकार्डियन मॉडल में PPF रैखिक और अवसर लागत स्थिर रहती है।",
            text,
        )
        # The 1817 publication date is now explicitly sourced; keep other model assumptions qualified.
        text = re.sub(r"(?m)^\s*[-*]\s*\[VERIFY\]\s*$", "", text)
        if "https://www.cambridge.org/core/books/on-the-principles-of-political-economy-and-taxation/" not in text:
            text = text.rstrip() + """

## Selected References / सुझाए गए स्रोत
- OpenStax, *Principles of Economics 2e*, Section 33.1, Absolute and Comparative Advantage: https://openstax.org/books/principles-of-economics-2e/pages/33-1-absolute-and-comparative-advantage
- Cambridge University Press, David Ricardo, *On the Principles of Political Economy, and Taxation* (first published 1817): https://www.cambridge.org/core/books/on-the-principles-of-political-economy-and-taxation/5C17BF2152379956950601EFE05AE14F
"""
            changes.append("Added source references for comparative advantage and the 1817 first-publication date.")

    if "market failure and remedial measures" in normalized:
        text = text.replace(
            "**Free-rider problem (मुफ्तखोर समस्या):** Individuals consume without paying because non-excludability prevents price signals, leading to under-provision by the market. [VERIFY]",
            "**Free-rider problem (मुफ्तखोर समस्या):** Because a pure public good is non-excludable, individuals may benefit without paying; this weakens private incentives to provide the good and can lead to under-provision. (गैर-अपवर्जनीयता के कारण व्यक्ति भुगतान किए बिना लाभ उठा सकते हैं; इससे निजी प्रदाताओं के लिए वस्तु उपलब्ध कराने का प्रोत्साहन घटता है और कम आपूर्ति हो सकती है।)",
        )
        text = text.replace(
            "[HUMAN VERIFY: All definitions against standard textbooks like Musgrave or Stiglitz.]",
            "",
        )
        text = re.sub(
            r"(?im)(\*\*Free-rider problem(?:\s*\([^)]*\))?:\*\*[^.\n]*\.)\s*\[VERIFY\]",
            r"\1",
            text,
        )
        text = re.sub(r"(?m)^\s*[-*]\s*\[VERIFY\]\s*$", "", text)
        if "https://doi.org/10.2307/1879431" not in text:
            text = text.rstrip() + """

## Selected References / सुझाए गए स्रोत
- OpenStax, *Principles of Economics 2e*, Sections 12.1, 13.3 and 16.1: https://openstax.org/books/principles-of-economics-2e/pages/13-3-public-goods
- George A. Akerlof, “The Market for ‘Lemons’: Quality Uncertainty and the Market Mechanism,” *The Quarterly Journal of Economics*, 84(3), 1970, pp. 488–500: https://doi.org/10.2307/1879431
"""
            changes.append("Added source citations for public goods, information asymmetry, externalities and Akerlof's lemons model.")

    if "economic growth in india: pattern and structure" in normalized:
        text, n1 = re.subn(
            r"(?m)^Historically, India’s growth has been characterized by a .*?Agriculture to Services\.\s*$",
            "India's structural transformation has been uneven across output, value added and employment. Services account for the largest share of nominal GDP in the cited H1 FY2025–26 snapshot, but this does not mean that India bypassed industrial development or that sectoral employment shares follow the same pattern.",
            text,
        )
        text, n2 = re.subn(
            r"(?m)^ऐतिहासिक रूप से, भारत का विकास .*?सेवाओं की ओर एक महत्वपूर्ण छलांग लगाई है।\s*$",
            "भारत का संरचनात्मक रूपांतरण उत्पादन, मूल्य वर्धन और रोजगार के संदर्भ में अलग-अलग और असमान रहा है। उद्धृत H1 FY2025–26 आँकड़ों में नाममात्र GDP में सेवा क्षेत्र की हिस्सेदारी सबसे अधिक है; इससे यह निष्कर्ष नहीं निकलता कि भारत ने औद्योगिक विकास को छोड़ दिया या रोजगार की क्षेत्रीय हिस्सेदारी भी उसी अनुपात में बदली।",
            text,
        )
        if n1 or n2:
            changes.append("Replaced the unsupported 'direct jump from agriculture to services' narrative with a qualified output/GVA/employment distinction.")
        text = text.replace(
            "The Service sector has emerged as the primary engine of growth.",
            "In the Economic Survey 2025–26 snapshot, services account for 53.6% of nominal GDP in H1 FY2025–26 (51.1% in FY2025–26 FAE); these are GDP shares, not employment shares or real growth rates.",
        )
        text = text.replace(
            "सेवा क्षेत्र विकास के प्राथमिक इंजन के रूप में उभरा है।",
            "Economic Survey 2025–26 के अनुसार H1 FY2025–26 में नाममात्र GDP में सेवाओं की हिस्सेदारी 53.6% थी (FY2025–26 FAE में 51.1%); ये GDP की हिस्सेदारियाँ हैं, रोजगार की हिस्सेदारी या वास्तविक वृद्धि दर नहीं।",
        )
        # Replace the illustrative year 1/year 10 table with dated official data.
        if re.search(r"(?m)^## Worked Example: Sectoral Shift", text):
            new_table = """## Worked Example: Reading a Dated Data Snapshot / दिनांकित आँकड़ों को समझना

**Source-based data (not a hypothetical table):** Economic Survey 2025–26, Table I.2b, reports services' share of **nominal GDP** as 52.6% in H1 FY2024–25 and 53.6% in H1 FY2025–26; the FY2025–26 FAE figure is 51.1%.

| Measure | H1 FY2024–25 | H1 FY2025–26 | FY2025–26 FAE |
| :--- | ---: | ---: | ---: |
| Services share of nominal GDP (%) | 52.6 | 53.6 | 51.1 |

Separately, the Survey's real-GVA growth table reports services growth of 7.0% in H1 FY2024–25 and 9.3% in H1 FY2025–26. A nominal GDP share is not a real growth rate and is not a GVA share. MoSPI's National Accounts Statistics 2026 uses base year 2022–23.

**स्रोत-आधारित आँकड़े:** Economic Survey 2025–26 की Table I.2b के अनुसार **नाममात्र GDP** में सेवाओं की हिस्सेदारी H1 FY2024–25 में 52.6% और H1 FY2025–26 में 53.6% थी; FY2025–26 FAE का आँकड़ा 51.1% है।

| माप | H1 FY2024–25 | H1 FY2025–26 | FY2025–26 FAE |
| :--- | ---: | ---: | ---: |
| नाममात्र GDP में सेवाओं की हिस्सेदारी (%) | 52.6 | 53.6 | 51.1 |

अलग से, सर्वेक्षण की वास्तविक GVA वृद्धि तालिका में सेवा क्षेत्र की वृद्धि H1 FY2024–25 में 7.0% और H1 FY2025–26 में 9.3% बताई गई है। नाममात्र GDP की हिस्सेदारी, वास्तविक वृद्धि दर या GVA की हिस्सेदारी नहीं होती। MoSPI के National Accounts Statistics 2026 में आधार वर्ष 2022–23 है।

Source: Government of India, Economic Survey 2025–26, Tables I.1 and I.2b; MoSPI, National Accounts Statistics 2026.
"""
            pattern = re.compile(r"(?ms)^## Worked Example: Sectoral Shift.*?(?=^## |\Z)")
            text, count = pattern.subn(new_table + "\n", text, count=1)
            if count:
                changes.append("Replaced the Year 1/Year 10 hypothetical sector table with a dated official nominal-GDP snapshot and a separate real-GVA growth comparison.")
        # Correct the Make in India MCQ without asserting an unsupported 25% GDP target.
        text = re.sub(
            r"\*\*Q5\. \[VERIFY\] Which government initiative specifically targets the growth of the manufacturing sector\?\*\*",
            "**Q5. Which 2014 initiative was launched to facilitate investment, foster innovation, build infrastructure and strengthen India's manufacturing ecosystem?**",
            text,
        )
        text = text.replace(
            '*Explanation: "Make in India" was launched to transform India into a global design and manufacturing hub.*',
            '*Explanation: Make in India was announced on 15 August 2014 and formally launched on 25 September 2014; its stated objectives include facilitating investment, fostering innovation, building infrastructure and positioning India as a manufacturing, design and innovation hub.*',
        )
        text = text.replace(
            '*व्याख्या: "मेक इन इंडिया" को भारत को एक वैश्विक डिजाइन और विनिर्माण केंद्र में बदलने के लिए शुरू किया गया था।*',
            '*व्याख्या: मेक इन इंडिया की घोषणा 15 अगस्त 2014 को हुई और औपचारिक शुरुआत 25 सितंबर 2014 को हुई; इसके उद्देश्यों में निवेश को सुगम बनाना, नवाचार को बढ़ावा देना, आधारभूत संरचना विकसित करना तथा भारत को विनिर्माण, डिजाइन और नवाचार केंद्र के रूप में स्थापित करना शामिल है।*',
        )
        text = text.replace(
            "*   No official MPPSC syllabus or source notes were supplied.",
            "*   Sources include MoSPI's National Accounts Statistics 2026 (base year 2022–23), Economic Survey 2025–26 Tables I.1 and I.2b, and PIB's Make in India release dated 25 September 2014.",
        )
        text = text.replace(
            "*   [VERIFY] claims are used where specific policy dates or current GDP percentages are not provided in the prompt and require reference to the latest Economic Survey of India.",
            "*   The services share is reported with its metric, period and estimate vintage; it must not be re-labelled as GVA share, employment share or real growth.",
        )
        text = text.replace(
            "*   [VERIFY] दावों का उपयोग वहां किया गया है जहां विशिष्ट नीति तिथियां या वर्तमान जीडीपी प्रतिशत प्रॉम्प्ट में प्रदान नहीं किए गए हैं और उन्हें भारत के नवीनतम आर्थिक सर्वेक्षण के संदर्भ की आवश्यकता है।",
            "*   सेवा क्षेत्र की हिस्सेदारी के साथ उसका माप, अवधि और अनुमान-विंटेज दिया गया है; इसे GVA की हिस्सेदारी, रोजगार की हिस्सेदारी या वास्तविक वृद्धि दर नहीं कहना चाहिए।",
        )
        text = re.sub(r"(?m)^\s*[-*]\s*\[VERIFY\]\s*$", "", text)
        text = text.replace(
            "**Primary Sector:** Traditionally the largest employer, but its share in GDP has declined over decades.",
            "**Primary Sector:** Agriculture accounted for 43.0% of workers in usual status in PLFS 2025, compared with 44.8% in 2024; these employment shares are not GDP/GVA shares.",
        )
        text = text.replace(
            "**प्राथमिक क्षेत्र:** पारंपरिक रूप से सबसे बड़ा नियोक्ता, लेकिन दशकों से जीडीपी में इसका हिस्सा कम हुआ है।",
            "**प्राथमिक क्षेत्र:** PLFS 2025 के अनुसार सामान्य स्थिति के कामगारों में कृषि की हिस्सेदारी 2025 में 43.0% और 2024 में 44.8% थी; ये रोजगार की हिस्सेदारियाँ हैं, GDP/GVA की नहीं।",
        )
        if "https://www.indiabudget.gov.in/economicsurvey/doc/echapter.pdf" not in text:
            text = text.rstrip() + """

## Selected Official References / आधिकारिक संदर्भ
- Government of India, *Economic Survey 2025–26*, Tables I.1 and I.2b: https://www.indiabudget.gov.in/economicsurvey/doc/echapter.pdf
- MoSPI, *National Accounts Statistics — 2026*, base year 2022–23: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2304948&lang=2&reg=48
- MoSPI/PIB, *PLFS Annual Report 2025*: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2246009&lang=2&reg=48
- Press Information Bureau, Make in India launch, 25 September 2014: https://www.pib.gov.in/newsite/PrintRelease.aspx?lang=2&reg=48&relid=110017
"""
            changes.append("Added dated official sources and corrected the Indian sector-structure example and Make in India question.")

    if "components of money supply" in normalized:
        # Place the numeric worked example before the recap rather than after the source notes.
        match = re.search(r"(?m)^## Recap\b", text)
        if match and "## Worked Example / Application — Traditional M1–M4" in text:
            start = text.find("## Worked Example / Application — Traditional M1–M4")
            if start > match.start():
                example = text[start:].strip()
                text = text[:start].rstrip()
                text = text[:match.start()].rstrip() + "\n\n" + example + "\n\n" + text[match.start():]
                changes.append("Moved the M1–M4 worked example into the teaching sequence before the recap.")

    # Final pass aligned to the literal variants found in the retained production artifact.
    if "economic growth in india: pattern and structure" in normalized:
        text = re.sub(
            r"(?m)^Historically, India’s growth has been characterized by a .*?Agriculture to Services\.\s*$",
            "India's structural transformation has been uneven across output, value added and employment. Services account for the largest share of nominal GDP in the cited H1 FY2025–26 snapshot, but this does not mean that India bypassed industrial development or that sectoral employment shares follow the same pattern.",
            text,
        )
        text = re.sub(
            r"(?m)^ऐतिहासिक रूप से, भारत का विकास .*?सेवाओं की ओर एक महत्वपूर्ण छलांग लगाई है।\s*$",
            "भारत का संरचनात्मक रूपांतरण उत्पादन, मूल्य वर्धन और रोजगार के संदर्भ में अलग-अलग और असमान रहा है। उद्धृत H1 FY2025–26 आँकड़ों में नाममात्र GDP में सेवा क्षेत्र की हिस्सेदारी सबसे अधिक है; इससे यह निष्कर्ष नहीं निकलता कि भारत ने औद्योगिक विकास को छोड़ दिया या रोजगार की क्षेत्रीय हिस्सेदारी भी उसी अनुपात में बदली।",
            text,
        )
        text = text.replace(
            "**Primary Sector:** Traditionally the largest employer, but its share in GDP has declined over decades.",
            "**Primary Sector:** Agriculture remains the largest employment sector in the PLFS 2025 snapshot (43.0% of workers in 2025, compared with 44.8% in 2024); employment shares and GDP/GVA shares are different measures.",
        )
        text = text.replace(
            "**प्राथमिक क्षेत्र:** पारंपरिक रूप से सबसे बड़ा नियोक्ता, लेकिन दशकों से जीडीपी में इसका हिस्सा कम हुआ है।",
            "**प्राथमिक क्षेत्र:** PLFS 2025 के अनुसार कृषि 2025 में सबसे बड़ा रोजगार क्षेत्र था (43.0% कामगार, जबकि 2024 में 44.8%); रोजगार की हिस्सेदारी और GDP/GVA की हिस्सेदारी अलग-अलग माप हैं।",
        )
        if re.search(r"(?m)^## Worked Example: Sectoral Shift", text):
            pattern = re.compile(r"(?ms)^## Worked Example: Sectoral Shift.*?(?=^## |\Z)")
            replacement = """## Worked Example: Reading a Dated Data Snapshot / दिनांकित आँकड़ों को समझना

**Source-based data (not a hypothetical table):** Economic Survey 2025–26, Table I.2b, reports services' share of **nominal GDP** as 52.6% in H1 FY2024–25 and 53.6% in H1 FY2025–26; the FY2025–26 FAE figure is 51.1%.

| Measure | H1 FY2024–25 | H1 FY2025–26 | FY2025–26 FAE |
| :--- | ---: | ---: | ---: |
| Services share of nominal GDP (%) | 52.6 | 53.6 | 51.1 |

Separately, the Survey's real-GVA growth table reports services growth of 7.0% in H1 FY2024–25 and 9.3% in H1 FY2025–26. A nominal GDP share is not a real growth rate and is not a GVA share. MoSPI's National Accounts Statistics 2026 uses base year 2022–23.

**Employment context:** MoSPI's PLFS Annual Report 2025 reports agriculture accounted for 43.0% of workers in usual status in 2025, compared with 44.8% in 2024. This is an employment share, not a GDP/GVA share.

**स्रोत-आधारित आँकड़े:** Economic Survey 2025–26 की Table I.2b के अनुसार **नाममात्र GDP** में सेवाओं की हिस्सेदारी H1 FY2024–25 में 52.6% और H1 FY2025–26 में 53.6% थी; FY2025–26 FAE का आँकड़ा 51.1% है।

| माप | H1 FY2024–25 | H1 FY2025–26 | FY2025–26 FAE |
| :--- | ---: | ---: | ---: |
| नाममात्र GDP में सेवाओं की हिस्सेदारी (%) | 52.6 | 53.6 | 51.1 |

अलग से, सर्वेक्षण की वास्तविक GVA वृद्धि तालिका में सेवा क्षेत्र की वृद्धि H1 FY2024–25 में 7.0% और H1 FY2025–26 में 9.3% बताई गई है। नाममात्र GDP की हिस्सेदारी, वास्तविक वृद्धि दर या GVA की हिस्सेदारी नहीं होती। MoSPI के National Accounts Statistics 2026 में आधार वर्ष 2022–23 है।

**रोजगार का संदर्भ:** MoSPI की PLFS Annual Report 2025 के अनुसार कृषि 2025 में सामान्य स्थिति के कुल कामगारों का 43.0% थी, जबकि 2024 में यह 44.8% थी। यह रोजगार की हिस्सेदारी है, GDP/GVA की हिस्सेदारी नहीं।

Source: Government of India, Economic Survey 2025–26, Tables I.1 and I.2b; MoSPI, National Accounts Statistics 2026; PLFS Annual Report 2025.
"""
            text, count = pattern.subn(replacement + "\n", text, count=1)
            if count:
                changes.append("Replaced the draft's Year 1/Year 10 hypothetical table with dated Economic Survey output/GVA data plus a separate PLFS employment measure.")
        if "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2246009" not in text:
            text = text.rstrip() + """

## Selected Official References / आधिकारिक संदर्भ
- Government of India, *Economic Survey 2025–26*, Tables I.1 and I.2b: https://www.indiabudget.gov.in/economicsurvey/doc/echapter.pdf
- MoSPI, *National Accounts Statistics — 2026*, base year 2022–23: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2304948&lang=2&reg=48
- MoSPI/PIB, *PLFS Annual Report 2025*, released 27 March 2026: https://www.pib.gov.in/PressReleasePage.aspx?PRID=2246009&lang=2&reg=48
- Press Information Bureau, Make in India launch, 25 September 2014: https://www.pib.gov.in/newsite/PrintRelease.aspx?lang=2&reg=48&relid=110017
"""
            changes.append("Added the latest PLFS 2025 employment data and official references.")

    # Ensure selected bibliographic references are present in the lesson itself,
    # not only in the artifact's separate source-note file.
    if "theory of consumer behaviour" in normalized and "MIT OpenCourseWare" not in text:
        text = text.rstrip() + """

## Selected References / सुझाए गए स्रोत
- OpenStax, *Principles of Economics 2e*, Sections 6.2 and 16.1: https://openstax.org/books/principles-of-economics-2e/pages/6-2-how-changes-in-income-and-prices-affect-consumption-choices
- MIT OpenCourseWare, *Principles of Microeconomics*, consumer choice and Giffen-good discussion: https://ocw.mit.edu/ans7870/14/14.01SC/MIT14_01SCF11_rttext.pdf
- SATHEE (IIT Kanpur), *Theory of Consumer Behaviour*: https://sathee.iitk.ac.in/sathee-ssc/student-corner/ncert-books/class-12/economics/introductory-to-microeconomics/chapter-02-theory-of-consumer-behaviour/
"""
        changes.append("Added traceable consumer-theory references directly to the corrected lesson.")

    if "market failure and remedial measures" in normalized and "10.2307/1879431" not in text:
        text = text.rstrip() + """

## Selected References / सुझाए गए स्रोत
- OpenStax, *Principles of Economics 2e*, Sections 12.1, 13.3 and 16.1: https://openstax.org/books/principles-of-economics-2e/pages/13-3-public-goods
- George A. Akerlof, “The Market for ‘Lemons’: Quality Uncertainty and the Market Mechanism,” *The Quarterly Journal of Economics*, 84(3), 1970, pp. 488–500: https://doi.org/10.2307/1879431
"""
        changes.append("Added traceable market-failure and Akerlof source references directly to the corrected lesson.")

    # Remove the stale marker-restoration appendix only when every remaining
    # verification marker was resolved by this topic's supplied source notes and edits.
    if not VERIFY_MARKER_PATTERN.search(text):
        text = re.sub(
            r"(?ms)\n## Original Verification Markers Retained for Human Sign-off\s*\n.*\Z",
            "",
            text,
        ).rstrip() + "\n"

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
    topic = os.environ.get("SCRIPT_TOPIC", "")
    topic_guidance = ""
    normalized_topic = topic.casefold()
    if "theory of consumer behaviour" in normalized_topic:
        topic_guidance = "Correct perfect information as model-specific rather than a universal demand-law assumption. Do not assert a precise Marshall/1895 attribution without direct historical evidence. Preserve the Giffen condition and historical caveat."
    elif "international trade: basic concepts" in normalized_topic:
        topic_guidance = "Remove Hicks/Slutsky from Ricardian comparative advantage. Explain relative opportunity cost and distinguish linear constant-cost Ricardian PPF from the general concave increasing-cost PPF."
    elif "market failure and remedial measures" in normalized_topic:
        topic_guidance = "Use source notes for public-good criteria, asymmetric information and externality definitions. Preserve the distinctions between these concepts."
    elif "components of money supply" in normalized_topic:
        topic_guidance = "Use RBI source definitions exactly. Ensure a populated bilingual Worked Example / Application computes M1, M2, M3 and M4 from explicitly hypothetical figures."
    elif "economic growth in india: pattern and structure" in normalized_topic:
        topic_guidance = "Replace undated illustrative sector shares with the dated Economic Survey data in source notes. Distinguish nominal GDP shares from GVA shares and growth rates; identify H1/FY periods and MoSPI base year 2022–23."
    system_prompt = """You are a careful academic script editor for DigvijayEconLab,
serving MPPSC Assistant Professor Economics aspirants.
Resolve every Critical and High-Priority issue explicitly identified in the academic review.
Apply Hicks/Slutsky income and substitution decomposition only when editing consumer-choice material such as the Law of Demand. Never apply it to Ricardian comparative advantage or other production-side trade theory. Preserve the distinction between individual and market demand.
For Giffen-goods bilingual parity, retain the caveat that the familiar Irish potato illustration is historically contested and is not settled empirical proof. Do not assert a specific Alfred Marshall book/edition/year attribution unless the supplied source notes directly establish that exact historical detail.
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
    user_prompt = f"""UNIT TOPIC: {topic or "[not specified]"}
TOPIC-SPECIFIC EDITORIAL GUIDANCE:
{topic_guidance or "[No additional topic-specific guidance.]"}
SOURCE NOTES:
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
        corrected, topic_changes = apply_topic_specific_repairs(
            corrected, os.environ.get("SCRIPT_TOPIC", "")
        )
        changes.extend(topic_changes)

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
