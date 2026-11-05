# FreeLLMAPI production workflow

## Scope

The daily ten-unit workflow defaults to FreeLLMAPI and uses a live-verified Cloudflare Workers AI Free-plan fallback before the direct Gemini endpoint. It remains manual-only until live reliability and full-pack validation are complete. The workflow does not publish videos or create public playlists unless separate opt-ins are selected.

## Run configuration

1. Open **Actions → DigvijayEconLab daily ten-unit production pack → Run workflow**.
2. The default is `freellmapi`, which activates the Cloudflare Free-plan preflight and fallback. Selecting `gemini` bypasses the independent provider and uses only direct Gemini.
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

Before a FreeLLMAPI production pack is claimed, `scripts/provider_preflight.py` sends a short bilingual probe to Cloudflare Workers AI. The daily workflow stops before claiming work if Cloudflare credentials are absent, invalid, or its free daily allocation is exhausted. The smoke workflow runs the same check before building FreeLLMAPI. The probe deliberately forces the FreeLLMAPI endpoint unavailable so it verifies the independent route, not the Google-backed primary route.

At runtime, the strict zero-cost fallback order is Cloudflare Workers AI, then direct Gemini. Gemini shares the Google AI Studio credential/quota with FreeLLMAPI and is not an independent quota pool.

- **Cloudflare Workers AI** uses the repository secrets `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`. The default model is `@cf/meta/llama-3.2-3b-instruct`, which Cloudflare lists for multilingual dialogue. Create the token from the Workers AI dashboard's REST API setup, or give a custom token both `Workers AI - Read` and `Workers AI - Edit` permissions.
- **Hugging Face routed Inference Providers are disabled in strict zero-cost mode.** Current Hugging Face pricing says Free users receive no included monthly Inference Provider credits; routed calls require purchased credits or a paid PRO subscription. The new `HF_INFERENCE_TOKEN` secret is therefore not passed to production or smoke workflows and is not used. Keep `HF_TOKEN` separate for Chatterbox/Space access. Do not purchase credits or add a provider-specific paid key for this setup.
- **Cloudflare Free allocation:** Workers AI Free provides 10,000 neurons per day at no charge. Requests above the allocation fail on the Free plan; do not upgrade to Workers Paid to bypass the limit. The account must remain on the Workers Free plan. Cloudflare documents the daily allowance and that usage beyond it requires Workers Paid.
- **Gemini** remains a final endpoint fallback. Since it shares the same Google provider/quota with FreeLLMAPI, it may not recover from Google rate limits or outages.
- The workflow does not purchase credits, add a payment method, or enable a paid plan. If Cloudflare free capacity is exhausted and Gemini is unavailable, the batch fails visibly and remains incomplete.
- Retries are bounded and respect provider retry hints. The production workflow stops if the independent Cloudflare live preflight fails.

Cloudflare credentials are required for the default FreeLLMAPI production mode. Without them, the preflight fails before a production pack is claimed. No Hugging Face API call is attempted in this zero-cost configuration.

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
- `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`: required for the zero-cost independent Cloudflare Workers AI fallback in default FreeLLMAPI mode.
- `GOOGLE_AI_STUDIO_API_KEY`: preferred upstream Google provider key for the temporary FreeLLMAPI instance. If absent, the workflow falls back to `GEMINI_API_KEY`.

Never put secret values in repository files, workflow inputs, artifacts, or chat messages.
