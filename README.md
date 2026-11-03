# DigvijayEconLab YouTube Automation

Cloud-based educational video production and YouTube publishing project for DigvijayEconLab.

## Current status

Script generation, academic review, and AI-assisted correction can now run automatically from a controlled topic queue:
- Daily scheduled run at **08:00 Asia/Kolkata** (GitHub cron: 02:30 UTC).
- Queue-triggered run whenever `config/topic_queue.json` is changed on `main`.
- One unique queue item is claimed per run. Claim and final status are committed to the repository to prevent the same topic from being generated twice.
- A run with no pending topic exits without calling Gemini.
- Publishing remains disabled. All outputs are drafts and require human verification and approval.

## Project layout

- `config/content_plan.json` — brand, audience, content pillars and publishing safeguards.
- `config/topic_queue.json` — controlled topic queue and processing status.
- `scripts/preflight.py` — validates the project configuration.
- `scripts/topic_queue.py` — validates topic uniqueness, claims one pending topic, recovers stale claims, and records completed/failed runs.
- `scripts/generate_script.py` — creates an educational Markdown draft through the Google Gemini API.
- `scripts/review_script.py` — creates an academic quality-control report; it does not rewrite the original script.
- `scripts/correct_script.py` — requests schema-constrained JSON from Gemini, validates required fields, preserves every original `[VERIFY ...]` marker, applies evidence-grounded editorial corrections and narrow deterministic math-notation cleanup, and records unresolved items.
- `scripts/quality_checks.py` — detects known notation corruption, mixed Latin/Devanagari words, unresolved verification markers, missing bilingual scripts, MCQ answer/explanation gaps, required content-structure gaps, and missing worked-example/application sections.
- `tests/` — offline queue, correction, formatting, and deterministic quality-gate tests.
- `.github/workflows/script-draft.yml` — daily, queue-triggered, and manually triggerable draft workflow.
- `.github/workflows/quality-tests.yml` — runs offline tests on pull requests and pushes to main.

## How automatic generation works

1. The workflow runs at 08:00 India time each day. GitHub Actions can occasionally start scheduled jobs a little later than the exact minute.
2. Adding a new queue item to `config/topic_queue.json` and committing it to `main` starts an additional queue-triggered run.
3. The workflow validates the whole queue, claims the first `pending` item, and commits its `processing` status before making any Gemini request.
4. It generates the script, performs the original academic review, applies schema-validated conservative correction, preserves the original review, and reviews the corrected draft.
5. The completed script, original and corrected reviews, correction log, and deterministic quality reports are stored as a GitHub Actions artifact for 14 days.
6. The queue item is marked `completed` only when the earlier workflow steps and artifact packaging succeed; otherwise it is marked `failed`. A `failed` item is not automatically retried. To retry it, change its status to `pending` after checking the failed run.
7. A processing claim older than six hours is considered stale and can be returned to `pending` on the next run.

## Add a topic to the queue

Edit `config/topic_queue.json` on `main` and add a new object inside `items`:

```json
{
  "id": "macro-national-income",
  "topic": "National Income: Concepts and Measurement",
  "language": "Bilingual",
  "content_format": "Concept Explainer",
  "source_notes": "Optional notes from an authoritative textbook or official source.",
  "status": "pending"
}
```

Use a new lowercase ID with hyphens. Topic names must be unique even when capitalization or punctuation differs. Supported languages are `Bilingual`, `Hindi`, and `English`; supported formats are `Concept Explainer`, `MCQ Set`, and `Previous-Year-Question Analysis`. Do not reuse or reset a completed topic under a new ID. Completed and failed entries remain in the queue as the duplicate-prevention history.

The initial queue contains ten Microeconomics topics. It intentionally excludes Law of Demand because that topic was already used for the earlier test draft.

## Academic quality and human approval

The workflow runs offline unit tests before calling Gemini. The original and corrected drafts are each reviewed with deterministic structural checks and an AI-assisted academic audit. Critical or High deterministic findings force a HOLD verdict. Original `[VERIFY]` markers are preserved in the corrected draft even if the correction model removes or alters them.

A successful GitHub Actions run means the workflow executed; it does **not** certify economics accuracy, source reliability, translation equivalence, MCQ correctness, or exam suitability. Review the original and corrected scripts, both academic reports, correction log, and deterministic quality reports. Independently verify claims against authoritative textbooks or supplied sources. A report showing HOLD must not be treated as ready for production. Human approval is mandatory.

## Gemini API

The workflow uses Gemini Developer API model `gemini-3.5-flash-lite` through the GitHub Actions secret `GEMINI_API_KEY`. Gemini Developer API access is separate from a Google AI Pro consumer subscription. Availability, free-tier eligibility, and rate limits depend on Google's current policies. Free-tier requests may be used by Google to improve its products; do not submit personal, confidential, or sensitive information. No paid billing is configured by this repository.

## Publishing safeguards

Publishing remains disabled. There are no YouTube upload or publish steps in this workflow. The content plan keeps human approval mandatory. Do not enable automatic public uploads until OAuth production eligibility, YouTube API compliance, content accuracy, copyright checks, and end-to-end private-upload tests have been addressed.

## Security rules

- Never commit Google OAuth client secrets, refresh tokens, access tokens, API keys, passwords, or `.env` files.
- Store deployment credentials only through GitHub Actions Secrets or Cloudflare Worker Secrets.
- Do not make this repository public.
- Do not use or modify the separate PixelToolkit project for this automation.
