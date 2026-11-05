# FreeLLMAPI production workflow

## Scope

The daily ten-unit workflow supports an explicit, opt-in FreeLLMAPI mode. Gemini remains the default. The workflow does not publish videos or create public playlists unless the existing separate opt-ins are selected.

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

If FreeLLMAPI cannot serve a request after its bounded retry policy, the adapter tries the configured fallback chain in order: Cloudflare Workers AI, Hugging Face Inference Providers, then direct Gemini.

- **Cloudflare Workers AI** uses the optional `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` repository secrets and the OpenAI-compatible account endpoint. The default model is `@cf/meta/llama-3.1-8b-instruct`. Create a token with the minimum `Workers AI - Read` and `Workers AI - Edit` permissions.
- **Hugging Face** uses the existing `HF_TOKEN` secret and `https://router.huggingface.co/v1/chat/completions`. The default fallback model is `Qwen/Qwen3-4B-Instruct-2507:cheapest`.
- **Gemini** remains the final endpoint fallback and shares the Google AI Studio credential/quota with FreeLLMAPI. It is not an independent quota pool.
- Cloudflare's Free plan currently includes 10,000 Workers AI neurons per day; requests beyond that free allocation fail on the Free plan. Hugging Face currently lists $0.10/month of Inference Provider credits for Free users, subject to change. Gemini free-tier rate limits are model- and project-specific. None of these providers guarantees enough free capacity for a 10-unit daily batch.
- The workflow does not purchase credits or enable a paid plan. If free capacity is exhausted, the request should fail visibly and the batch remains incomplete. Do not add a paid billing method to bypass quotas.
- Retries are bounded and respect provider retry hints. The pipeline stops with an explicit error if all configured providers fail.

Cloudflare credentials are optional. Without them, Cloudflare is skipped and the adapter proceeds to Hugging Face. The production and smoke workflows pass the existing `HF_TOKEN` secret and optional Cloudflare secrets to the runner.

## Cost and publication safeguards

- No billing setup or paid service is enabled by this workflow.
- GitHub Actions usage remains subject to the repository's included Actions quota. If that quota is exhausted, the run may be blocked; no paid overage is authorized by this configuration.
- FreeLLMAPI is not exposed to the public internet and is not hosted persistently.
- The daily workflow defaults to FreeLLMAPI so the independent fallback chain is active. The workflow remains manual-only until a full production-readiness run passes.
- Public playlist creation and private staging uploads remain separate, explicit workflow inputs and default to false.
- A successful AI quality verdict is only a handoff to human review. It is not factual certification or publication approval.
- No public YouTube release is automated by this provider integration.

## Required repository secrets

- `GEMINI_API_KEY`: direct Gemini endpoint and final endpoint fallback.
- `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`: optional Cloudflare Workers AI fallback credentials.
- `GOOGLE_AI_STUDIO_API_KEY`: preferred upstream Google provider key for the temporary FreeLLMAPI instance. If absent, the workflow falls back to `GEMINI_API_KEY`.

Never put secret values in repository files, workflow inputs, artifacts, or chat messages.
