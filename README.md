# DigvijayEconLab YouTube Automation

Cloud-based educational content production for DigvijayEconLab.

## Current operating mode

The **daily ten-unit production workflow** is scheduled for **08:00 Asia/Kolkata**. Each successful daily pack prepares material for the following publication date:

- 10 bilingual full-lesson script packages: one lesson from every UGC NET Economics unit.
- One bilingual 9:16 YouTube Short, rendered as an MP4 draft with synthetic placeholder narration.
- One bilingual YouTube Community post draft, including a poll and suggested pinned comment.
- Ten unit-specific playlist definitions with titles and descriptions.

The next day's pack is generated one day ahead to allow academic verification, editing and scheduling. The suggested public release schedule is in `docs/daily-production-calendar.md` and `config/daily_timeline.json`.

**Important:** full-length lesson scripts are generated and reviewed, but this workflow does not yet render those ten lessons into finished landscape MP4 videos. It renders the one daily Short draft. Community posts and the ten playlists are prepared as drafts/catalogue entries; they are not published or created on YouTube automatically.

Public video upload, public playlist creation, Community post publishing and YouTube scheduling remain disabled. All content requires human approval.

## Project layout

- `config/content_plan.json` — brand, audience, content pillars and publishing safeguards.
- `config/unit_content_plan.json` — the ten syllabus units and their rotating topic sequences, based on the user-supplied UGC NET Economics syllabus, Subject Economics, Code No. 01.
- `config/playlist_catalog.json` — ten playlist titles and descriptions; catalogue only, not created on YouTube.
- `config/daily_timeline.json` — proposed Community, ten-lesson and Short release slots in India time.
- `config/daily_production_state.json` — idempotency state and successful-day rotation counter.
- `config/topic_queue.json` — separate legacy one-topic queue for manual/backlog drafts.
- `scripts/daily_production.py` — claims one daily pack, rotates all ten unit topics, runs each lesson through the full generation/review/correction/re-review pipeline, generates promotional assets, and records completion.
- `scripts/generate_script.py` — generates an individual educational Markdown lesson through Gemini.
- `scripts/review_script.py` — creates an academic quality-control report; it does not rewrite the original script.
- `scripts/correct_script.py` — requests schema-constrained JSON from Gemini, validates required fields, preserves original `[VERIFY ...]` markers, applies limited deterministic notation repairs, and records unresolved items.
- `scripts/quality_checks.py` — deterministic structural and formatting checks.
- `scripts/generate_daily_assets.py` — generates the daily bilingual Short storyboard, Community post/poll draft, and validated SEO metadata (title variants, descriptions, tags, hashtags and thumbnail copy) for all ten unit lessons.
- `scripts/chatterbox_tts.py` — generates Hindi and English narration through the free Chatterbox Multilingual V3 Hugging Face Space, using a reference recording downloaded from a private Hugging Face dataset at runtime.
- `scripts/heygen_tts.py` — optional paid HeyGen TTS fallback; reads `HEYGEN_API_KEY` and `HEYGEN_VOICE_ID` only from GitHub Actions secrets.
- `scripts/render_short_video.py` — renders a 1080 × 1920 narrated Short draft using Chatterbox (preferred when enabled), HeyGen or generic eSpeak fallback, Pillow and FFmpeg; no music is added.
- `scripts/topic_queue.py` — manages the legacy one-topic queue.
- `tests/` — offline unit and regression tests.
- `.github/workflows/daily-channel-pack.yml` — scheduled daily ten-unit production pack at 08:00 IST.
- `.github/workflows/script-draft.yml` — legacy single-topic workflow, manually triggered or triggered by changes to its separate topic queue.
- `.github/workflows/quality-tests.yml` — runs code compilation, unit tests and plan validation on pull requests and main pushes.

## Daily production schedule

The detailed schedule is in `docs/daily-production-calendar.md`.

| India time | Planned activity |
|---|---|
| 08:00 | Generate next day's pack |
| 08:30 | Community post preview/poll |
| 09:00–18:00 | One lesson from Units 1–10, one per hour |
| 19:00 | Daily Short |
| 19:30 | Review comments and next-day plan |

These are recommended release slots, not active publishing automations. The daily workflow generates tomorrow's package at 08:00 today.

## Topic rotation and duplicate protection

1. The workflow validates the ten-unit plan and runs the complete offline regression suite.
2. It claims today's pack and commits the claim state before calling Gemini.
3. It selects one topic per unit using the successful-day rotation counter.
4. Each of the ten lessons is generated, academically reviewed, corrected using validated structured output, and reviewed again.
5. It generates one daily Short storyboard, one Community post and poll, then renders a vertical MP4 Short draft.
6. It uploads all available outputs as a GitHub Actions artifact with 14-day retention.
7. Only a successful pack advances the rotation counter. A failed pack does not advance to the next day's topics.
8. A completed pack cannot be claimed twice on the same India-local date. A failed pack can be retried on the same date only by manually running the workflow with `retry_failed=true`.

The current rotation starts at the first topic listed for each unit in `config/unit_content_plan.json`. Each successful day advances every unit by one topic. When one unit reaches the end of its list, that unit's topic sequence cycles to its beginning.

## First daily pack

The workflow's first scheduled run is **4 November 2026 at 08:00 IST**. It will prepare the publication pack for **5 November 2026**. This is one day ahead to allow review and editing.

## Playlist setup

The ten playlist definitions are in `config/playlist_catalog.json`. Titles are:

1. UGC NET Economics Unit 1 | Micro Economics | DigvijayEconLab
2. UGC NET Economics Unit 2 | Macro Economics | DigvijayEconLab
3. UGC NET Economics Unit 3 | Statistics and Econometrics | DigvijayEconLab
4. UGC NET Economics Unit 4 | Mathematical Economics | DigvijayEconLab
5. UGC NET Economics Unit 5 | International Economics | DigvijayEconLab
6. UGC NET Economics Unit 6 | Public Economics | DigvijayEconLab
7. UGC NET Economics Unit 7 | Money and Banking | DigvijayEconLab
8. UGC NET Economics Unit 8 | Growth and Development Economics | DigvijayEconLab
9. UGC NET Economics Unit 9 | Environmental Economics and Demography | DigvijayEconLab
10. UGC NET Economics Unit 10 | Indian Economy | DigvijayEconLab

These are catalogue entries, not live playlists. YouTube's playlist creation and playlist-item insertion endpoints need a write OAuth scope. The existing Cloudflare OAuth grant was configured for upload/read/analytics and does not currently include `youtube` or `youtube.force-ssl`. This project has not requested a new scope or re-authorized the channel.

## Shorts and Community posts

- The daily Short is rendered as a 1080 × 1920 MP4 with bilingual on-screen text and narration. When `CHATTERBOX_ENABLED=true` and the private Hugging Face reference-audio settings are configured, Chatterbox Multilingual V3 is preferred. Otherwise, configured HeyGen credentials are used; if neither owner-voice provider is configured, eSpeak is used as a generic placeholder clearly marked as not the owner’s voice. No background music or third-party assets are added.
- The Community post is generated as text plus a poll draft and a suggested pinned comment. YouTube's documented Community post scheduling process is through YouTube Studio. The public YouTube Data API v3 reference does not offer a Community-post creation endpoint, so the automation does not attempt to publish it.
- YouTube currently categorizes eligible square or vertical videos up to three minutes as Shorts for standard channels, subject to the platform's conditions. Keep every rendered Short within that limit and check copyright before publishing.

## Academic quality and human approval

The original and corrected lesson drafts are each checked by deterministic structural rules and an AI-assisted academic audit. Critical or High deterministic findings force a HOLD verdict. Original `[VERIFY]` markers are preserved in the corrected draft even if the correction model removes or alters them.

A successful workflow run only means the pipeline executed. It does **not** certify economics accuracy, source reliability, Hindi-English equivalence, MCQ correctness, exam suitability or publication readiness. Review:
- All ten original and corrected lesson scripts.
- All ten original and corrected academic review reports.
- Every correction log and deterministic report.
- The Short's factual claims, pronunciation, subtitles, rendering and duration.
- Community copy, playlist metadata, copyrights and final titles.

Resolve all verification markers and Critical/High issues against authoritative textbooks or sources before production use. Human approval is mandatory.

## HeyGen voice matching

The renderer calls HeyGen Voice TTS directly. Add these repository Actions secrets (never paste the values into chat):
- `HEYGEN_API_KEY` — your HeyGen API key with voice-generation permissions.
- `HEYGEN_VOICE_ID` — the voice ID of your own active HeyGen clone.

Create an Instant Voice from a clean recording of your own voice or a Professional Voice Clone (PVC) for closer similarity. HeyGen currently documents Instant Voice creation from up to 60 seconds of speech; Professional Voice Clone uses at least 20 minutes, with 30 minutes to two hours recommended for a richer match. Use only your own voice or a voice you have explicit permission to clone. The renderer records whether the HeyGen clone was actually used. The Metricool publisher refuses to schedule the daily Short when that report does not confirm the owner's clone.

HeyGen API pricing is usage-based and is separate from the HeyGen app subscription. Check the current plan/API allowance before running high-volume TTS. The code does not create or purchase a HeyGen voice clone; create the voice in your HeyGen account first, then add the voice ID as a GitHub secret.

## Gemini API and quota safeguards

The workflow uses Gemini Developer API model `gemini-3.5-flash-lite` through the GitHub Actions secret `GEMINI_API_KEY`. Gemini Developer API access is separate from a Google AI Pro consumer subscription. Rate limits depend on the Google AI Studio project and model; check the active limits in AI Studio. This daily batch can require up to 41 sequential Gemini requests (10 scripts × generation/review/correction/re-review, plus one Short/Community generation request). The workflow spaces AI requests to reduce rate-limit pressure, but the free-tier project may still reject or exhaust the daily batch. No paid billing is configured. If quota is insufficient, reduce output volume or request a separate billing decision; do not bypass quality gates.

Free-tier requests may be used by Google to improve its products. Do not submit personal, confidential or sensitive information.

## Security and publishing safeguards

- Never commit Google OAuth client secrets, refresh tokens, access tokens, API keys, passwords or `.env` files.
- Store credentials only through GitHub Actions Secrets or Cloudflare Worker Secrets.
- Do not make this repository public.
- Do not use or modify the separate PixelToolkit project for this automation.
- No automatic YouTube uploads, public playlist creation or public Community publishing are enabled.
- Do not add OAuth scopes, enable billing or change account/security settings without explicit authorization.

## 14-day pilot

The initial operating plan is a 14-day pilot. Review workflow completion, Gemini quota, academic review workload, CTR, retention by unit, and Short-to-long-video traffic before treating ten daily lessons as a permanent public release cadence. Ten long-form releases per day is a high volume; reduce public release frequency rather than sacrificing quality.


## Metricool publishing integration

The workflow includes an optional Metricool scheduler. It is **inactive until all three repository Actions secrets are present**:
- `METRICOOL_API_TOKEN` — token from Metricool Account Settings → API.
- `METRICOOL_USER_ID` — Metricool user ID.
- `METRICOOL_BLOG_ID` — Metricool brand ID for the connected DigvijayEconLab YouTube channel.

Metricool API access is limited to Advanced and Custom plans. Every API request uses the `X-Mc-Auth` header plus the user and brand IDs. The scheduler:
- reads the channel's existing YouTube playlists from Metricool,
- uploads finished MP4 files to Metricool media storage,
- schedules eligible YouTube videos and Shorts with SEO title, description, tags, privacy and playlist ID,
- checks existing scheduled posts for the same title/date before creating a duplicate,
- writes a per-day publishing report into the artifact.

### Public publishing gate

The scheduler will not publish a daily batch unless all ten corrected lesson packages have original and corrected academic review reports, no unresolved `[VERIFY]` markers, explicit positive corrected-review verdicts, and deterministic reports with zero blocking findings. The daily Short is withheld unless its render report confirms that the configured owner reference voice clone (Chatterbox or HeyGen) was used. A generic eSpeak placeholder is never scheduled publicly.

Long-form publishing is not active yet because the system currently creates ten reviewed lesson scripts, not ten finished landscape MP4s. The scheduler only looks for actual video files at `output/videos/unit-01.mp4` through `unit-10.mp4`; it will skip a unit if its MP4 is missing. Do not treat a script or PDF as a finished video file.

### Playlist creation and Community posts

The Metricool API can list existing YouTube playlists and assign an existing playlist ID to a scheduled video, but the current integration does not create a new playlist. To create all ten playlist containers automatically, the Google OAuth worker must be reauthorized with the YouTube Data API `youtube` scope, then the workflow can use `playlists.insert` for creation and `playlistItems.insert` for adding videos. The current Worker grant was authorized only with `youtube.upload`, `youtube.readonly` and `yt-analytics.readonly`; no new scope or consent was applied in this repository.

Community posts and polls remain drafts for manual scheduling in YouTube Studio. The public YouTube Data API does not offer a Community-post creation endpoint, and Metricool's public API does not expose YouTube Community post publishing. Do not attempt to automate these with undocumented endpoints.

### Connect Metricool

1. Confirm that the Metricool account is on Advanced or Custom and that the DigvijayEconLab YouTube channel is connected to the correct brand.
2. In Metricool, open Account Settings → API and create/copy the API token. Obtain the user ID and brand/blog ID from the Metricool brand URL or API profile list.
3. In GitHub, open Settings → Secrets and variables → Actions → New repository secret. Add the three secrets above. Never paste the token into chat or commit it to the repository.
4. Run the daily production workflow only after reviewing the first artifact and confirming the channel/brand IDs are correct. A test schedule should be private/draft first if the Metricool account supports it; public scheduling is otherwise an irreversible external action once the scheduled time arrives.

No publishing request is made if the three Metricool secrets are absent. Once present, eligible videos are scheduled publicly according to `config/daily_timeline.json`; the scheduler does not have a per-video approval dialog. Remove/blank the secrets to disable all Metricool publishing quickly.

### Voice clone setup

Add the HeyGen API key and your own HeyGen voice ID as `HEYGEN_API_KEY` and `HEYGEN_VOICE_ID` GitHub Actions secrets. For a Professional Voice Clone, HeyGen currently specifies at least 20 minutes of your own clean recordings and recommends 30 minutes to two hours; the add-on has a separate paid cost. The current HeyGen TTS API can synthesize text in the chosen cloned voice. The workflow uses the exact configured voice ID for Hindi and English, but accent and pronunciation should be reviewed before public release.



## Free Chatterbox voice clone setup

The preferred free narration provider is the official ResembleAI Chatterbox Multilingual V3 Hugging Face Space:
https://huggingface.co/spaces/ResembleAI/Chatterbox-Multilingual-TTS-V3

The Space supports Hindi and English reference-audio voice generation. Its current UI/API limit is 300 characters per request; the adapter splits longer narration at sentence/word boundaries and joins the returned WAV segments. It uses the documented Generate endpoint and the neutral settings (exaggeration 0.5, temperature 0.8, CFG/pace 0.5).

**Free-service limitation:** the Space runs on shared Hugging Face ZeroGPU infrastructure. It may queue, sleep, rate-limit or be temporarily unavailable. This is a best-effort free integration, not a production SLA. If the Space is unavailable, the Chatterbox step fails visibly rather than silently substituting a different voice. The workflow will not schedule the Short unless its render report confirms that an owner reference voice clone was used.

### Keep the voice recording private

Do not commit the voice recording to this GitHub repository. Create a **private Hugging Face dataset repository** in your own Hugging Face account, for example `djvjupsc/digvijayeconlab-voice-reference`, and upload the approved WAV reference as `voice-reference.wav`. Keep the dataset private. The GitHub Action downloads it at runtime using a read-scoped Hugging Face token; it does not add the audio file to Git history or artifacts.

### Configure GitHub Actions

In the repository, open **Settings → Secrets and variables → Actions**.

Add this repository **secret**:
- `HF_TOKEN` — a Hugging Face user access token with read access to the private voice-reference dataset only. Do not paste it into chat or commit it.

Add these repository **variables**:
- `CHATTERBOX_ENABLED` = `true`
- `CHATTERBOX_REFERENCE_REPO` = your private dataset repo ID, e.g. `djvjupsc/digvijayeconlab-voice-reference`
- `CHATTERBOX_REFERENCE_FILENAME` = `voice-reference.wav`
- `CHATTERBOX_SPACE` = `ResembleAI/Chatterbox-Multilingual-TTS-V3`

When enabled, Chatterbox takes priority over HeyGen. If Chatterbox is disabled, the existing HeyGen integration remains available; if neither clone provider is configured, the renderer uses eSpeak placeholder narration. The report records the provider and whether a reference voice clone was used, but never records the token or reference-audio contents.

The adapter sends narration text and the reference audio to the public ResembleAI Hugging Face Space for synthesis. Only use a recording of your own voice or a recording you have explicit permission to use. Chatterbox output contains an imperceptible Perth watermark and is MIT-licensed; the model's free Space remains subject to service availability and its usage limits.


## Pre-publication safety controls

The daily workflow runs `scripts/prepublish_audit.py` on the generated Short. It verifies that the MP4 is present, H.264, 1080×1920, no longer than three minutes, includes narration, uses the configured owner-authorized voice clone, and has no music track (the current renderer adds no music or third-party visual assets). A failed audit stops the publishing job.

The audit is not a copyright certificate. It cannot query Content ID, establish third-party licensing, or guarantee that YouTube will not issue a claim. Check YouTube Studio's copyright checks and retain licences/permissions for any external asset. The current Short renderer creates its own typography slides and uses narration only; no external stock clips, music or movie footage are included.

**Public scheduling is disabled by default.** The Metricool publisher requires the repository Actions secret `PUBLIC_PUBLISHING_ENABLED=true` in addition to the existing Metricool credentials. Leave it unset/false for draft-only operation. Only enable it after confirming the Metricool account is connected to the correct DigvijayEconLab YouTube channel and reviewing the workflow output. When enabled, eligible videos may be scheduled publicly without another confirmation prompt.

The audit report records `publish_authorized: false` and `human_review_required: true`; the workflow's publication switch is a separate account-owner authorization. Review educational accuracy, pronunciation, subtitles, originality, thumbnail/title accuracy, advertiser suitability, asset rights, and whether altered/synthetic-content disclosure applies before enabling public scheduling.

YouTube's monetization review evaluates channel-level originality and authenticity. Avoid repetitive mass-produced videos, generic template-only slideshows, scraped content, and minimally transformed third-party material. AI assistance is not automatically disqualifying, but the creator's original teaching, analysis and educational value must be clear.
