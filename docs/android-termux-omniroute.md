# Android Termux + OmniRoute (local-only)

This is an optional local AI gateway for the Android device. The GitHub Actions production workflow continues to use its temporary, localhost-only FreeLLMAPI instance and independent provider fallback chain. A gateway at `127.0.0.1` on the phone is **not reachable from GitHub-hosted runners**; do not expose the phone's dashboard/API to the public internet or create an unauthenticated tunnel.

## 1. Install on Android

Install Termux from its official F-Droid or GitHub release source. Open Termux and run:

```sh
pkg update
pkg upgrade
pkg install nodejs python git
node --version
npm --version
npm install -g omniroute
```

Use the current `nodejs` package, not `nodejs-lts` if it installs an older Node release. OmniRoute's current Termux guide requires a supported Node 22.22.2+ or 24+ release within its documented range. If the version check fails, stop and resolve the Node version before installing.

## 2. Start the local gateway

```sh
omniroute
```

Keep the Termux process running. On the same phone, open `http://127.0.0.1:20128` in the browser. Complete the dashboard's initial setup, enable dashboard/API authentication, and add only providers you are authorized to use. Prefer official free-tier API credentials or provider integrations whose terms permit this use. Do not paste GitHub, Google, YouTube, or other account passwords/cookies into third-party providers.

Keep the service bound to loopback/local device access. Do not use `0.0.0.0`, public port forwarding, or a public tunnel for this personal gateway.

## 3. Connect this repository's Python provider adapter

The repository now supports `LLM_PROVIDER=omniroute`. In the Termux shell where you run the project, set:

```sh
export LLM_PROVIDER=omniroute
export OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1
export OMNIROUTE_API_KEY='YOUR_LOCAL_OMNIROUTE_API_KEY'
export OMNIROUTE_MODEL=auto
```

Create/copy the API key from OmniRoute's authenticated dashboard. Do not commit it, put it in a script, or send it in chat. Then run the existing Python content-generation commands from your local checkout. For example:

```sh
python scripts/generate_script.py "Opportunity Cost" Bilingual "MCQ Set" docs/source-notes/opportunity-cost.md
```

If your chosen provider does not support the `auto` alias, select an exact model ID shown by the OmniRoute dashboard and set `OMNIROUTE_MODEL` to that ID.

## 4. Background operation (optional)

Android may stop background processes to save battery. Keep Termux battery optimization disabled only if you need the gateway to remain available. Start with a foreground session; do not configure boot persistence until the local API has been tested. The dashboard and API are unavailable whenever Android stops Termux.

## 5. GitHub Actions architecture

- **GitHub-hosted automation:** keep the existing temporary FreeLLMAPI + Cloudflare Workers AI + Hugging Face + Gemini fallback workflow. It does not depend on the phone being online.
- **Android local work:** use OmniRoute through `127.0.0.1:20128/v1` for interactive/manual generation from the phone.
- **No public bridge:** GitHub Actions cannot call the phone's loopback endpoint. Publicly exposing it would add avoidable credential and abuse risks.
- **Free-tier reality:** providers impose separate quotas, model availability and terms. No token count or free tier is guaranteed; quota exhaustion should fail visibly rather than enable paid billing.

## Official setup references

- OmniRoute project: https://www.omniroute.online/
- OmniRoute quick start: https://omniroute.hagicode.com/en-US/getting-started/quick-start/
- OmniRoute Android Termux guide: https://github.com/TribAI-LLC/omniroute/blob/main/docs/guides/TERMUX_GUIDE.md
- FreeLLMAPI upstream: https://github.com/tashfeenahmed/freellmapi
