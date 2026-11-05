# FreeLLMAPI production workflow

## Scope

The daily ten-unit workflow supports an explicit, opt-in FreeLLMAPI mode. Gemini remains the default. The workflow does not publish videos or create public playlists unless the existing separate opt-ins are selected.

## Run configuration

1. Open **Actions → DigvijayEconLab daily ten-unit production pack → Run workflow**.
2. Leave **AI provider** set to `gemini` for the existing default path, or select `freellmapi` to run the local FreeLLMAPI adapter.
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

If FreeLLMAPI cannot serve a request after its bounded retry policy, the adapter attempts the direct Gemini API when `LLM_FALLBACK_PROVIDER=gemini` and `GEMINI_API_KEY` is present.

This is an endpoint/runtime fallback, **not an independent provider or quota pool**: both routes use Google AI Studio credentials and may share the same Google rate limits.

## Cost and publication safeguards

- No billing setup or paid service is enabled by this workflow.
- GitHub Actions usage remains subject to the repository's included Actions quota. If that quota is exhausted, the run may be blocked; no paid overage is authorized by this configuration.
- FreeLLMAPI is not exposed to the public internet and is not hosted persistently.
- The daily workflow defaults to Gemini.
- Public playlist creation and private staging uploads remain separate, explicit workflow inputs and default to false.
- A successful AI quality verdict is only a handoff to human review. It is not factual certification or publication approval.
- No public YouTube release is automated by this provider integration.

## Required repository secrets

- `GEMINI_API_KEY`: direct Gemini endpoint and emergency endpoint fallback.
- `GOOGLE_AI_STUDIO_API_KEY`: preferred upstream Google provider key for the temporary FreeLLMAPI instance. If absent, the workflow falls back to `GEMINI_API_KEY`.

Never put secret values in repository files, workflow inputs, artifacts, or chat messages.
