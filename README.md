# DigvijayEconLab YouTube Automation

Cloud-based educational video production and YouTube publishing project for DigvijayEconLab.

## Current status

The repository is in **safe setup mode**. Script drafting is available as a manually triggered, draft-only workflow. Video rendering and YouTube publishing are not enabled.

## Project layout

- `config/content_plan.json` — brand, audience, content pillars and publishing safeguards.
- `scripts/preflight.py` — validates the project configuration.
- `scripts/generate_script.py` — creates an educational Markdown draft using the Gemini Developer API.
- `.github/workflows/preflight.yml` — manually runs the configuration check.
- `.github/workflows/script-draft.yml` — manually generates a script draft and stores it as a workflow artifact.
- `.env.example` — names of future configuration values only; contains no credentials.

## Generate a script draft using Gemini

1. Create a Gemini API key in Google AI Studio: https://aistudio.google.com/app/apikey
2. Add a repository Actions secret named `GEMINI_API_KEY` under **Settings → Secrets and variables → Actions**. Never put the key in source files or workflow inputs.
3. Open **Actions → DigvijayEconLab script draft → Run workflow**.
4. Enter a topic, choose the language and format, and optionally provide authoritative source notes.
5. Download the `digvijayeconlab-script-draft` artifact from the completed workflow run.
6. Fact-check and edit the draft before using it in a video.

The workflow defaults to `gemini-3.1-flash-lite`. Google provides a free tier for selected Gemini API models subject to account eligibility, quotas and rate limits. Free-tier prompts and responses may be used by Google to improve its products; do not submit personal, confidential, or sensitive information. Free-tier availability and model limits can change. Check the current AI Studio quota and official pricing before use.

## Run the preflight locally

Requires Python 3.12 or newer:

```bash
python scripts/preflight.py
```

Or open **Actions → DigvijayEconLab preflight → Run workflow** in GitHub.

## Security rules

- Never commit Google OAuth client secrets, refresh tokens, access tokens, API keys, passwords, or `.env` files.
- Store provider credentials only through GitHub Actions Secrets or Cloudflare Worker Secrets.
- Do not make this repository public.
- Do not use or modify the separate PixelToolkit project for this automation.

## Publishing safeguards

Publishing remains disabled. The content plan requires human approval. Do not enable automatic public uploads until OAuth production eligibility, YouTube API compliance, content accuracy, copyright checks, and end-to-end private-upload tests have been addressed.

## Planned components

1. Content planning and source notes.
2. Original bilingual script generation (manual draft workflow).
3. Hindi narration and captions.
4. Video rendering.
5. YouTube metadata and private-upload integration.
6. Analytics and failure reporting.

Free-tier quotas and provider policies can change. Workflows should stop safely when quotas or required credentials are unavailable; do not add billing without explicit approval.
