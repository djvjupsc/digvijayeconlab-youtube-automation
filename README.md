# DigvijayEconLab YouTube Automation

Cloud-based educational video production and YouTube publishing project for DigvijayEconLab.

## Current status

This repository is in **safe setup mode**. Video generation and publishing are not enabled.

## Project layout

- `config/content_plan.json` — brand, audience, content pillars and publishing safeguards.
- `scripts/preflight.py` — validates the project configuration.
- `.github/workflows/preflight.yml` — manually runs the preflight check.
- `.env.example` — names of future configuration values only; contains no credentials.
- `.gitignore` — excludes local credentials and generated media.

## Run the preflight locally

Requires Python 3.12 or newer:

```bash
python scripts/preflight.py
```

Or open **Actions → DigvijayEconLab preflight → Run workflow** in GitHub.

## Security rules

- Never commit Google OAuth client secrets, refresh tokens, access tokens, API keys, passwords, or `.env` files.
- Store deployment credentials only in GitHub Actions Secrets or Cloudflare Worker Secrets.
- Do not make this repository public.
- Do not use or modify the separate PixelToolkit project for this automation.

## Publishing safeguards

Publishing is disabled by default. The initial content plan requires human approval. Do not enable automatic public uploads until OAuth production eligibility, YouTube API compliance, content accuracy, copyright checks, and end-to-end private-upload tests have been addressed.

## Planned components

1. Content planning and source notes.
2. Original bilingual script generation.
3. Hindi narration and captions.
4. Video rendering.
5. YouTube metadata and upload integration.
6. Analytics and failure reporting.

Free-tier quotas and provider policies can change. Workflows should stop safely when quotas or required credentials are unavailable; do not add billing without explicit approval.
