# Free-first production mode: limits and operating rules

Last reviewed: 5 November 2026

## What “free” means for this repository

The workflow is configured not to buy credits, enable paid billing, or silently turn on a paid AI service. That does **not** create an unlimited or guaranteed free production service. The hosted services below have quotas, shared capacity, and service availability limits. A full ten-unit pack can stop when any quota is exhausted.

| Service | Current free allowance / restriction | Production implication |
|---|---|---|
| Google AI Studio / Gemini API | Free access is limited to eligible models and project-specific rate limits; exact RPM/TPM/RPD limits vary by model and project. | Primary FreeLLMAPI upstream may return 429/503. Direct Gemini fallback shares the same Google project quota. |
| Cloudflare Workers AI | Workers Free currently includes 10,000 neurons per day. On the Free plan, requests beyond that free allocation fail; usage above the allocation on a Workers Paid plan is charged. | Optional independent fallback. Keep the account on the Free plan to make quota exhaustion fail closed. |
| Hugging Face Inference Providers | Current docs list $0.10/month of credits for Free users, subject to change. Extra routed usage requires credit purchase. | Small emergency fallback, not a daily 10-unit capacity guarantee. Do not buy credits to continue. |
| GitHub Actions | Private-repository included minutes and artifact storage depend on the GitHub plan. GitHub Free currently includes 2,000 Actions minutes/month and 500 MB storage; extra usage may be billed unless blocked by a budget. | Keep runs manual until actual monthly runtime and storage are known. Set a zero/stop budget in GitHub billing settings if you need a hard no-charge ceiling. |
| Chatterbox Multilingual V3 Space | Shared Hugging Face ZeroGPU Space; queue, quota and availability are not guaranteed. | Owner-voice synthesis can fail. eSpeak fallback is preview-only and is not upload-eligible in this repository. |
| YouTube Data API | Default quota is 10,000 units/day for most methods, with separate buckets for search and video insertion. | API quota is finite; keep publishing disabled until owner approval and quota checks. |

Official references:
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Cloudflare Workers AI pricing: https://developers.cloudflare.com/workers-ai/platform/pricing/
- Cloudflare Workers AI REST setup and token permissions: https://developers.cloudflare.com/workers-ai/get-started/rest-api/
- Hugging Face Inference Providers pricing: https://huggingface.co/docs/inference-providers/pricing
- GitHub Actions included usage: https://docs.github.com/en/billing/reference/product-usage-included
- YouTube API quota: https://developers.google.com/youtube/data/determine_quota_cost

## Provider chain

When `LLM_PROVIDER=freellmapi`, the adapter tries:
1. FreeLLMAPI connected to the configured Google AI Studio model.
2. Cloudflare Workers AI, if both optional Cloudflare secrets are configured.
3. Hugging Face Inference Providers.
4. Direct Gemini as a final endpoint fallback (same Google project quota as step 1).

The normal ten-unit workflow now defaults to `freellmapi`. Choosing `gemini` explicitly bypasses independent fallbacks and calls Gemini directly.

Cloudflare credentials are optional GitHub repository secrets:
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

Create a narrowly scoped token using Cloudflare's **Workers AI - Read** and **Workers AI - Edit** permissions. Do not put the token in source code, chat, workflow inputs or artifacts. Keep the Cloudflare account on the Workers Free plan if you do not authorize paid usage.

The smoke workflow includes one deliberately short live fallback probe. It makes the local FreeLLMAPI endpoint unavailable for that single test call, then tests Cloudflare first (when configured) and Hugging Face next. It does not use Gemini as part of this probe.

## Voice and video

The existing owner-voice path uses the Chatterbox Space and a private voice-reference dataset. The GitHub runner downloads the voice reference at runtime; it is not committed to the repository. Only use the account owner's own voice or a recording with explicit permission.

If Chatterbox is unavailable, eSpeak can render a complete preview for checking slide pacing and text. It remains marked preview-only and the upload audit blocks it. Do not remove that safeguard merely to make a video upload.

A fully offline neural Hindi/English TTS option could be built around downloadable voice models, but each voice model has its own licence and quality constraints. It is not currently part of the approved upload path. A Termux/llama.cpp or local TTS setup on Android is optional experimentation, not required by the GitHub-hosted workflow and not a reliable always-on production runner.

## Production release gates

- Keep the ten-unit workflow manual until at least one complete run passes and its free usage is measured.
- The daily rotation state is committed back to `main` after each claimed run so the next run does not repeat day zero. The workflow must have GitHub Actions permission to write repository contents; if the push fails, the workflow fails rather than pretending the rotation state was saved.
- A successful automated academic gate means **ready for human review only**. It is not factual certification.
- Verify MCQs, calculations, bilingual parity, source claims, MPPSC syllabus mapping, pronunciation, slide layout and audio before release.
- Public playlist creation, private staging uploads and public video publication remain separately controlled. No public YouTube release is automated by this provider integration.

## F-Droid requirement

No additional F-Droid application is required for this GitHub Actions workflow. FreeLLMAPI runs temporarily on the GitHub runner; it is not a service that must stay running on the Android phone. Termux plus llama.cpp is only an optional local-inference experiment if you later choose to use the phone as a local compute device.
