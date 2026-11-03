# DigvijayEconLab YouTube Automation

Cloud-based educational video production and YouTube publishing project for DigvijayEconLab.

## Current status

The repository is in **safe setup mode**. Script generation, academic review, and AI-assisted correction run only when manually triggered. Outputs are drafts; video rendering and YouTube publishing are not enabled.

## Project layout

- `config/content_plan.json` — brand, audience, content pillars and publishing safeguards.
- `scripts/preflight.py` — validates the project configuration.
- `scripts/generate_script.py` — creates an educational Markdown draft through the Google Gemini API.
- `scripts/review_script.py` — creates an academic quality-control report; it does not rewrite the original script.
- `scripts/correct_script.py` — requests schema-constrained JSON from Gemini, validates required fields, applies evidence-grounded editorial corrections, performs narrow deterministic math-notation cleanup, and records unresolved verification items.
- `scripts/quality_checks.py` — detects known notation corruption, mixed Latin/Devanagari words, unresolved verification markers, missing bilingual scripts, MCQ answer/explanation gaps, and required content-structure gaps.
- `tests/test_correct_script.py` and `tests/test_quality_checks.py` — offline tests for structured-response fallback, notation cleanup, and deterministic quality gates.
- `.github/workflows/preflight.yml` — manually runs the configuration check.
- `.github/workflows/script-draft.yml` — runs offline correction/quality tests, then manually generates, reviews, corrects, and re-reviews a script before storing scripts, reviews, correction logs, and deterministic quality reports as a workflow artifact.
- `.env.example` — names of future configuration values only; contains no credentials.

## Generate, review, and correct a script

1. Add a repository Actions secret named `GEMINI_API_KEY` under **Settings → Secrets and variables → Actions**. Never put the key in source files or workflow inputs.
2. Open **Actions → DigvijayEconLab script draft → Run workflow**.
3. Enter a topic, choose the language and format, and optionally provide authoritative source notes.
4. The workflow first runs offline unit tests for structured-response validation and deterministic quality checks.
5. Download the `digvijayeconlab-corrected-script-package` artifact from the completed workflow run.
6. The package contains the original script (`output/scripts/`), first academic review (`output/reviews/original-quality-review.md`), corrected draft (`output/corrected_scripts/`), correction log and unresolved items (`output/corrections/`), and final academic review of the corrected draft (`output/reviews/`).
7. Compare original and corrected scripts. Review both deterministic reports in `output/quality_checks/`. Independently verify factual claims and unresolved items against authoritative textbooks or supplied sources. Human approval is mandatory before production use.

The correction step requests Gemini's structured JSON response mode with a required schema rather than custom text delimiters. Python validates the response before accepting it. If the response is malformed, truncated, or missing required fields, the original script is preserved unchanged and the correction log records the fallback; the workflow can still complete its second review. After a valid structured response, Python applies only narrow, deterministic notation repairs for known corrupted derivative/fraction sequences and fragile up/down-arrow macros. A successful workflow does not guarantee that any AI edits were made: inspect the correction log and compare the two scripts.

The correction step is deliberately conservative: it must not invent facts or citations, and it must retain unresolved verification markers when source notes do not establish the answer. The deterministic quality gate checks formatting controls, known math corruption, mixed Latin/Devanagari words, bilingual-script presence, unresolved `[VERIFY]` markers, numbered MCQ counts, explicit answer and explanation labels, and core Concept Explainer sections. Minimum practice-question counts are 5 for Concept Explainer, 10 for MCQ Set, and 3 for Previous-Year-Question Analysis. Any Critical or High finding forces the final review verdict to `HOLD FOR CORRECTION`; Gemini cannot override that local gate. The bilingual script-presence check does not prove that translations are equivalent, and the structural checks do not verify economics theory, source reliability, MCQ correctness, or academic depth. An AI reviewer or correction report is not factual certification.

The workflow uses Gemini Developer API model `gemini-3.5-flash-lite`. Availability, free-tier eligibility, and rate limits depend on Google's current policies and project. Free-tier requests may be used by Google to improve its products; do not submit personal, confidential, or sensitive information. This workflow does not configure paid billing. A Google AI Pro consumer subscription is separate from Gemini Developer API access and does not automatically provide API credits or free-tier eligibility.

## Run the preflight locally

Requires Python 3.12 or newer:

```bash
python scripts/preflight.py
python -m unittest discover -s tests -v
```

Or open **Actions → DigvijayEconLab preflight → Run workflow** in GitHub.

## Security rules

- Never commit Google OAuth client secrets, refresh tokens, access tokens, API keys, passwords, or `.env` files.
- Store deployment credentials only through GitHub Actions Secrets or Cloudflare Worker Secrets.
- Do not make this repository public.
- Do not use or modify the separate PixelToolkit project for this automation.

## Publishing safeguards

Publishing remains disabled. The content plan requires human approval. Do not enable automatic public uploads until OAuth production eligibility, YouTube API compliance, content accuracy, copyright checks, and end-to-end private-upload tests have been addressed.

## Planned components

1. Content planning and source notes.
2. Original bilingual script generation.
3. Academic review, schema-validated conservative correction, and second review (manual draft workflow).
4. Hindi narration and captions.
5. Video rendering.
6. YouTube metadata and private-upload integration.
7. Analytics and failure reporting.

Free-tier quotas and provider policies can change. Workflows should stop safely when quotas or required credentials are unavailable; do not add billing without explicit approval.
