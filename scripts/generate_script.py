import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from .llm_provider import generate_content, get_api_key
except ImportError:
    from llm_provider import generate_content, get_api_key

try:
    from .source_notes import resolve_source_notes_argument
except ImportError:
    from source_notes import resolve_source_notes_argument

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"


def clean_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return (slug[:60] or "economics-script") + ".md"


def topic_specific_requirements(topic: str) -> str:
    """Return evidence-bounded instructions for the exact topic being generated."""
    normalized = (topic or "").casefold()
    if "theory of consumer behaviour" in normalized:
        return """- Treat perfect information as a possible model-specific assumption, not a universal assumption of the law of demand.
- Explain that the income effect operates through purchasing power/real income; distinguish normal and inferior goods.
- A Giffen good must be inferior and have an income effect large enough to outweigh the substitution effect. Do not imply this is common.
- Do not state that Alfred Marshall discussed or named Giffen goods in a specific 1895 edition unless the supplied source notes directly verify that precise historical attribution. The familiar Irish potato illustration is contested and is not conclusive empirical proof.
- Keep Hicks/Slutsky decomposition within the consumer-choice discussion; distinguish Giffen goods from Veblen/status goods."""
    if "international trade: basic concepts" in normalized:
        return """- Explain comparative advantage as a production-side concept based on relative opportunity cost (or relative unit-labour requirements). Do not connect the Ricardian model to Hicks/Slutsky consumer-demand decomposition.
- Distinguish the general concave PPF (increasing marginal opportunity cost) from the simplest Ricardian model with constant unit-labour requirements (linear PPF and constant opportunity cost).
- State whether a table reports output per worker/hour or labour required per unit; compute opportunity costs consistently and label all units."""
    if "market failure and remedial measures" in normalized:
        return """- Define a pure public good by both non-excludability and non-rivalry; do not equate government financing with public-good status.
- Distinguish imperfect from asymmetric information, and distinguish adverse selection (hidden information/characteristics) from moral hazard (hidden action/incentive change after agreement).
- Define externalities as effects on third parties outside the transaction. For negative production externalities, distinguish MPC from MSC and state the model assumptions.
- Use the supplied references; label all numerical illustrations hypothetical."""
    if "components of money supply" in normalized:
        return """- Preserve the RBI distinctions between traditional M1–M4 and the separate NM1–NM3 aggregates exactly as stated in the supplied RBI notes.
- Include a separate, populated section headed '## Worked Example / Application' with a bilingual arithmetic example. For illustration only, use currency with public ₹500 crore, demand deposits ₹300 crore, other RBI deposits ₹10 crore, post-office savings deposits ₹20 crore, bank time deposits ₹700 crore, and all post-office savings-bank deposits (excluding NSCs) ₹35 crore. Show M1=₹810 crore, M2=₹830 crore, M3=₹1,510 crore and M4=₹1,545 crore by applying the RBI formulas. State in both languages repeatedly that these figures are hypothetical (काल्पनिक), not observed data. Explain that M2, M3 and M4 are alternative aggregates, not values to be added together.
- Translate 'time deposits' as 'सावधि जमा' consistently."""
    if "economic growth in india: pattern and structure" in normalized:
        return """- Identify the statistical source vintage: MoSPI's National Accounts Statistics 2026 uses base year 2022–23; do not mix it with the superseded 2011–12 series without an explicit bridge.
- You may quote the Economic Survey 2025–26 figure 53.6% only as the services share of nominal GDP in H1 FY2025–26 (the H1 FY2024–25 comparator is 52.6%). The Survey's FY2025–26 FAE figure is 51.1%. Do not label 53.6% as an annual figure or a GVA share.
- The Survey separately reports services GVA growth of 9.3% in H1 FY2025–26 versus 7.0% in H1 FY2024–25. Keep growth rate and share concepts separate.
- Make in India was announced on 15 August 2014 and formally launched on 25 September 2014; do not repeat undated or retired manufacturing-share targets as current policy.
- Qualify claims about 'service-led growth'; distinguish output/GVA shares from employment shares and avoid unsupported long-run sectoral percentages."""
    return ""


def main():
    if len(sys.argv) < 4:
        raise SystemExit("Usage: generate_script.py TOPIC LANGUAGE FORMAT [SOURCE_NOTES]")

    topic, language, content_format = sys.argv[1:4]
    source_notes = resolve_source_notes_argument(sys.argv[4] if len(sys.argv) > 4 else None)
    try:
        api_key = get_api_key()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    allowed_languages = {"Hindi", "English", "Bilingual"}
    allowed_formats = {"Concept Explainer", "MCQ Set", "Previous-Year-Question Analysis"}
    if language not in allowed_languages:
        raise SystemExit("Unsupported language selection.")
    if content_format not in allowed_formats:
        raise SystemExit("Unsupported content format.")

    system_prompt = """You are an educational content writer for DigvijayEconLab.
Create original, accurate material for MPPSC Assistant Professor Economics aspirants.
Do not fabricate statistics, quotations, citations, PYQs, dates, policies, or source references.
Use only the supplied source notes for specific factual claims. If notes are absent or insufficient,
mark claims that need verification as [VERIFY] rather than inventing details.
For MCQs, provide four options, one clearly marked correct answer, and a clear explanation for every question.
Use clean Markdown and robust notation. Prefer readable Unicode arrows (↑ and ↓) and simple
plain-text derivative notation such as dQ_d/dP. Do not use nested formatting macros such as
raisebox or tiny, and do not put control characters inside mathematical expressions.
For Bilingual output, provide the English explanation followed by a faithful Hindi equivalent
for each substantive teaching point or paragraph. Do not blend Latin and Devanagari characters
inside a single word. Keep standard English technical terms in parentheses where useful.
Before finalizing, compare every English recap bullet and explanation with its Hindi counterpart.
The Hindi version must preserve every substantive clause, qualification, relationship and conclusion;
do not omit a second sentence or a concluding implication. In particular, when the English PPF recap
states that a concave PPF reflects increasing opportunity costs, state that same point explicitly in Hindi.
For cost questions, clearly distinguish explicit cash outlays from implicit opportunity costs.
When a question asks for implicit cost only, identify forgone owner salary or labour as implicit cost
and label purchases/supplies as explicit cost; do not confuse the two. State all assumptions and make
hypothetical values explicit. If useful, state total economic cost separately from the requested
implicit-cost answer.
In Source and Verification Notes, never claim that material has been checked against official MPPSC
curriculum or syllabus guidelines unless the corresponding official source was actually supplied and
used. When no official syllabus or source notes are supplied, say that syllabus alignment and source
verification have not been independently checked and require human confirmation.
For a Concept Explainer, include a dedicated, populated Markdown section titled
"## Worked Example / Application" or "## Demand Schedule" (a suitable Hindi-English
equivalent is acceptable). This must contain a worked illustrative example with clear
steps/units or a labelled demand-schedule table with at least two data rows. Clearly label
illustrative numbers as hypothetical; never present invented numbers as real observations.
A passing mention of an example elsewhere in the script is not sufficient.
Avoid repetitive filler, clickbait, fake engagement, and copyrighted textbook passages.
For the specific topic Law of Demand, follow supplied source notes on Giffen goods carefully. State that the historical attribution is debated; do not imply the Irish potato famine example is settled empirical proof. Distinguish Giffen goods from Veblen/status goods. Explain downward-sloping individual demand using substitution and income effects; discuss additional buyers only in the context of market demand. If the supplied notes adequately resolve a historical nuance, do not add a [VERIFY] marker for that exact nuance; retain [VERIFY] only for genuinely unsupported claims elsewhere.
Return clean Markdown with a title, learning objectives, structured teaching content,
a dedicated worked example/application or demand-schedule section, a concise recap,
practice questions, and source/verification notes."""

    if content_format == "Concept Explainer":
        format_requirements = (
            "Concept Explainer requirements: include learning objectives, a clear definition, "
            "assumptions or scope where relevant, step-by-step explanation, suitable examples or "
            "applications, a concise recap, and at least 5 distinct MCQs. Each MCQ needs four options, "
            "one correct answer, and an explanation. Add a labelled schedule/curve description only "
            "where it genuinely helps explain the topic; never invent data."
        )
    elif content_format == "MCQ Set":
        format_requirements = (
            "MCQ Set requirements: provide at least 10 distinct topic-relevant MCQs, each with four "
            "options, one correct answer, and an explanation. Avoid duplicate questions and ambiguous "
            "distractors. Include a short concept map or revision recap."
        )
    else:
        format_requirements = (
            "Previous-Year-Question Analysis requirements: analyze at least 3 questions only when "
            "actual question text or a reliable source is supplied. Never invent or label a question "
            "as an actual PYQ without evidence. If actual PYQs are not supplied, clearly label any "
            "new questions as PYQ-style practice, not previous-year questions. Explain the concept, "
            "reasoning, answer, and exam relevance for each included question."
        )

    unit_context = os.environ.get("SCRIPT_UNIT", "")
    topic_requirements = topic_specific_requirements(topic)
    user_prompt = f"""Brand: DigvijayEconLab\nUnit: {unit_context or "Not specified"}
Audience: MPPSC Assistant Professor Economics aspirants
Topic: {topic}
Language: {language}
Format: {content_format}
Format-specific requirements:
{format_requirements}
Topic-specific requirements:
{topic_requirements if topic_requirements else "[No additional topic-specific instructions.]"}
Source notes supplied by the user:
{source_notes if source_notes.strip() else "[No source notes supplied. Avoid unsupported factual claims and mark verification gaps.]"}
Target: a useful, classroom-ready first draft. For bilingual output, provide corresponding
English and Hindi explanations for each substantive teaching point. Include source/verification notes at the end."""

    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
    }
    try:
        result = generate_content(API_URL, api_key, payload, label="Script generation", timeout=120)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    candidates = result.get("candidates", [])
    if not candidates:
        feedback = result.get("promptFeedback", {})
        raise SystemExit("Gemini returned no script candidate. Prompt feedback: " +
                         json.dumps(feedback, ensure_ascii=False)[:800])

    parts = candidates[0].get("content", {}).get("parts", [])
    content = "\n".join(part.get("text", "") for part in parts if part.get("text"))
    if not content.strip():
        finish_reason = candidates[0].get("finishReason", "unknown")
        raise SystemExit(f"Gemini returned empty content (finish reason: {finish_reason}).")

    output_dir = Path("output/scripts")
    output_dir.mkdir(parents=True, exist_ok=True)
    unit_prefix = os.environ.get("SCRIPT_FILENAME_PREFIX", "").strip()
    filename_topic = f"{unit_prefix} {topic}" if unit_prefix else topic
    output_path = output_dir / clean_filename(filename_topic)
    output_path.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"Draft generated: {output_path}")
    print("Status: DRAFT ONLY — human fact-check and approval required.")


if __name__ == "__main__":
    main()
