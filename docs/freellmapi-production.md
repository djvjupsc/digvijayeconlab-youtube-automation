# FreeLLMAPI production workflow

## Scope

The daily ten-unit workflow defaults to FreeLLMAPI and uses independent Cloudflare Workers AI and Hugging Face fallbacks before the direct Gemini endpoint. It remains manual-only until live reliability and full-pack validation are complete. The workflow does not publish videos or create public playlists unless separate opt-ins are selected.

## Run configuration

1. Open **Actions → DigvijayEconLab daily ten-unit production pack → Run workflow**.
2. The default is now `freellmapi`, which activates the independent fallback chain. Selecting `gemini` bypasses Cloudflare/Hugging Face fallback and uses only direct Gemini.
3. Keep **Create public playlists** and **Authorize private staging uploads** disabled unless separately intended.
4. Inspect the complete artifact and human-review reports before any release.

When FreeLLMAPI is selected, the runner:
- starts a temporary FreeLLMAPI process bound only to `127.0.0.1`;
- provisions a temporary random admin password, encryption key and database;
- uses `GOOGLE_AI_STUDIO_API_KEY`, or the existing `GEMINI_API_KEY` secret as a fallback, as the Google provider credential;
- retrieves a short-lived unified key from the local dashboard API and masks it in GitHub Actions;
- runs lesson generation, first review, correction, second review, Shorts/Community/SEO asset generation through the shared provider adapter;
- stops the local process and removes the temporary SQLite database after generation.

The FreeLLMAPI source is pinned to upstream commit `fb07845faf7cf986ea9f3692e055076035dd8739`, which was the tested source revision.

## Fallback behavior

Before a FreeLLMAPI production pack is claimed, `scripts/provider_preflight.py` tests every configured independent provider using a small bilingual Economics request. The daily workflow stops before claiming work if no independent provider passes. Each configured provider is tested separately; failed optional providers are logged and excluded from that run's fallback chain. The smoke workflow runs the same preflight before building FreeLLMAPI. The probe deliberately forces the FreeLLMAPI endpoint unavailable so it verifies the independent route, not the Google-backed primary route.

At runtime, if FreeLLMAPI cannot serve a request after its bounded retry policy, the adapter tries the configured fallback chain in order: Cloudflare Workers AI, Hugging Face Inference Providers, then direct Gemini.

- **Cloudflare Workers AI** uses the optional `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` repository secrets and the OpenAI-compatible account endpoint. The default model is `@cf/meta/llama-3.2-3b-instruct` (the previous `@cf/meta/llama-3.1-8b-instruct` model was deprecated on May 30, 2026). Create a token with the minimum Workers AI permissions required by the Cloudflare API.
- **Hugging Face** uses the dedicated `HF_INFERENCE_TOKEN` secret and `https://router.huggingface.co/v1/chat/completions`. Keep the existing `HF_TOKEN` separate for Chatterbox/Space access; do not overwrite it just to add inference permissions. The default fallback model is `Qwen/Qwen3-4B-Instruct-2507:cheapest`. Create a separate fine-grained token with the **Make calls to Inference Providers** permission and save it as `HF_INFERENCE_TOKEN` in GitHub Actions secrets. The live test previously showed that the existing `HF_TOKEN` lacks this permission (HTTP 403). A general Hub read token alone is insufficient.
- **Gemini** remains the final endpoint fallback and shares the Google AI Studio credential/quota with FreeLLMAPI. It is not an independent quota pool.
- Cloudflare Workers Free currently includes 10,000 Workers AI neurons per day. To keep that route at zero cost, the Cloudflare account must remain on the Free plan; Workers Paid charges $0.011 per 1,000 neurons above the daily free allocation. The repository cannot detect or override the account's billing plan, so do not upgrade or attach paid billing for this workflow. Hugging Face currently lists $0.10/month of Inference Provider credits for Free users, subject to change; additional usage requires purchased credits. Gemini free-tier limits are project/model-specific and capacity is not guaranteed. None of these providers guarantees enough free capacity for a 10-unit daily batch.
- The workflow does not purchase credits or enable a paid plan. If free capacity is exhausted, the request should fail visibly and the batch remains incomplete. Do not add a paid billing method to bypass quotas.
- Retries are bounded and respect provider retry hints. The pipeline stops with an explicit error if all configured providers fail.

Cloudflare credentials are optional. Without them, Cloudflare is skipped and the adapter proceeds to Hugging Face. The preflight checks all configured provider credentials individually; if a configured token is invalid, it is excluded from that run; at least one independent provider must pass. Fix its permission or remove an incomplete/unused secret to restore it to the chain.

## Android and narration dependencies

- No additional F-Droid application is required for GitHub Actions. GitHub-hosted Ubuntu runners install the required tools and start FreeLLMAPI locally on the runner; a FreeLLMAPI server on the Android phone's `127.0.0.1` is not reachable from GitHub-hosted runners.
- Chatterbox/ZeroGPU availability is quota-limited. If the free Space quota is exhausted, the current workflow can render eSpeak preview narration only. That preview is not the owner's voice and is not upload-eligible; the publishing gate must remain closed until an approved narration path succeeds.

## Cost and publication safeguards

- No billing setup or paid service is enabled by this workflow.
- GitHub Actions usage remains subject to the repository owner's included compute allowance. GitHub's current plan table lists $12/month of included compute usage and 500 MB Actions storage for GitHub Free; this is expressed as a monetary compute allowance, not a fixed minutes quota. Standard hosted runners for private repositories draw from this amount. Usage beyond the allowance can be billed unless the owner configures a budget with 'Stop usage when budget limit is reached'. The repository automation cannot inspect or change the owner's billing budget. To preserve a strict zero-cost setup, configure the billing budget to stop usage and expect workflows to stop when the included allowance is exhausted.
- FreeLLMAPI is not exposed to the public internet and is not hosted persistently.
- The daily workflow defaults to FreeLLMAPI so the independent fallback chain is active. The workflow remains manual-only until a full production-readiness run passes.
- Public playlist creation and private staging uploads remain separate, explicit workflow inputs and default to false.
- A successful AI quality verdict is only a handoff to human review. It is not factual certification or publication approval.
- No public YouTube release is automated by this provider integration.

## Required repository secrets

- `GEMINI_API_KEY`: direct Gemini endpoint and final endpoint fallback.
- `HF_INFERENCE_TOKEN`: fine-grained Hugging Face token with **Make calls to Inference Providers** permission. Keep it separate from `HF_TOKEN` used by Chatterbox/Space integrations.
- `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`: optional Cloudflare Workers AI fallback credentials.
- `GOOGLE_AI_STUDIO_API_KEY`: preferred upstream Google provider key for the temporary FreeLLMAPI instance. If absent, the workflow falls back to `GEMINI_API_KEY`.

Never put secret values in repository files, workflow inputs, artifacts, or chat messages.
