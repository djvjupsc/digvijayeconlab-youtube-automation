# DigvijayEconLab YouTube Automation

Cloud-based educational content production for DigvijayEconLab.

## Current operating mode

The **daily ten-unit production workflow** is scheduled for **08:00 Asia/Kolkata**. Each successful daily pack prepares material for the following publication date:

- 10 bilingual full-lesson script packages: one lesson from every UGC NET Economics unit.
- One bilingual 9:16 YouTube Short MP4 draft.
- Ten original 16:9 (1280 × 720) branded YouTube thumbnail images, one per unit.
- One featured 16:9 (1920 × 1080) narrated long-form lesson MP4, selected from the rotating featured unit.
- One bilingual YouTube Community post draft, including a poll and suggested pinned comment.
- Ten unit-specific playlist definitions with titles and descriptions.

The next day's pack is generated one day ahead to allow academic verification, editing and scheduling. The suggested public release schedule is in `docs/daily-production-calendar.md` and `config/daily_timeline.json`.

**Important:** the workflow generates and reviews ten lesson scripts, renders one featured long-form lesson and one Short, and creates ten thumbnails each day. The long-form renderer uses original typography slides with narration from Chatterbox when enabled; eSpeak may create a preview draft but cannot pass the private-upload voice gate. Community posts and the ten playlists are prepared as drafts/catalogue entries; Community posts are not published automatically.

Public video publishing and automatic scheduling remain disabled. An optional uploader can place an audited Short in PRIVATE visibility for manual review. Public playlist creation is a separate one-time manual opt-in. Community posts remain drafts. All content requires human approval.

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
- `scripts/render_short_video.py` — renders a 1080 × 1920 narrated Short draft using free Chatterbox when enabled, or generic eSpeak placeholder narration; no paid TTS integration or music is used.
- `scripts/render_thumbnails.py` — renders ten original 1280 × 720 thumbnails using SEO headline options, bilingual labels, original chart motifs and installed fonts; no image API or stock asset is used.
- `scripts/render_longform_video.py` — converts the featured corrected lesson into a 1920 × 1080 narrated slide-based MP4, validates the render, and marks it upload-eligible only when the owner-authorized Chatterbox voice was used.
- `scripts/topic_queue.py` — manages the legacy one-topic queue.
- `tests/` — offline unit, upload-safeguard, thumbnail and long-form parsing/render tests.
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

## Per-lesson quality gates and failure isolation

Every daily unit lesson now has its own generation → original review → correction → corrected review → academic gate sequence. The gate checks the review's explicit verdict, Critical/High issue sections, the deterministic structural report, unresolved `[VERIFY]` markers, and any unresolved items listed in the correction log. A passing result means **ready for human review only**; it does not certify factual accuracy or authorize publishing.

A failed topic is recorded as BLOCKED, but the orchestration continues through the remaining independent unit topics so one malformed script or review does not discard the other nine attempts. The batch is marked failed unless all ten lessons pass their automated gates. A failed batch does not advance the rotation and does not start the Short/Community asset stage. The workflow artifact retains successful lesson drafts, gate reports and a batch-status report for diagnosis. Review the artifact before using the same-day manual retry.

The Law of Demand Giffen-history verifier accepts common Markdown heading and bold-list labels, and accepts a corrected lesson with no remaining inherited markers even when no provenance appendix is present. It still fails closed when a marker remains in lesson content or when the required English/Hindi historical caveats are absent. This is a wording/structure check only; the cited academic sources are not fetched or independently validated by that script.

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

The ten playlist definitions are in `config/playlist_catalog.json`. The scheduled daily workflow does not create them. A manual `workflow_dispatch` run has a separate `create_public_playlists` checkbox, off by default, for a one-time creation operation after confirming the OAuth scope and channel. Titles are:

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

- The daily Short is rendered as a 1080 × 1920 MP4 with bilingual on-screen text and narration. When `CHATTERBOX_ENABLED=true` and the private Hugging Face reference-audio settings are configured, Chatterbox Multilingual V3 is used. Otherwise, eSpeak is used as a generic placeholder clearly marked as not the owner’s voice. No paid TTS provider, background music or third-party visuals are used.
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

## Law of Demand pilot narration modes

The isolated Law of Demand workflow offers two explicit narration modes:

- **Production (default):** requires `CHATTERBOX_ENABLED=true`, the private owner voice reference and successful Chatterbox synthesis. If the free Hugging Face ZeroGPU quota is exhausted or the Space is unavailable, production stops safely. It never substitutes another voice.
- **Preview:** uses eSpeak NG to render the complete 1920 × 1080 visual lesson while Chatterbox is unavailable. The render report records `narration_mode: preview`, `preview_only: true`, `voice_clone_used: false` and `upload_eligible: false`. The workflow's YouTube upload step is skipped in preview mode even if the private-upload input is set to yes.

Preview output is for layout, slide pacing and caption inspection only. It is not an owner-voice production master and must not be uploaded. Return to Production mode after Chatterbox quota is available. Human academic review remains mandatory in both modes.

## Free narration setup

The automated narration path uses Chatterbox Multilingual V3 through the public Hugging Face Space and the user's own private reference recording. The project does not use a paid voice-generation API. Use only your own voice or a recording you have explicit permission to use. Review voice likeness, Hindi/English pronunciation and pacing before publication.

When Chatterbox is unavailable or disabled, eSpeak may be used to create a visual/audio draft, but the pre-publication audit blocks that generic voice from upload. This prevents a placeholder from being mistaken for the owner's cloned voice.

## Gemini API and quota safeguards

The workflow uses Gemini Developer API model `gemini-3.5-flash-lite` through the GitHub Actions secret `GEMINI_API_KEY`. Gemini Developer API access is separate from a Google AI Pro consumer subscription. Rate limits depend on the Google AI Studio project and model; check the active limits in AI Studio. This daily batch can require up to 41 sequential Gemini requests (10 scripts × generation/review/correction/re-review, plus one Short/Community generation request). The workflow spaces AI requests to reduce rate-limit pressure, but the free-tier project may still reject or exhaust the daily batch. No paid billing is configured. If quota is insufficient, reduce output volume or request a separate billing decision; do not bypass quality gates.

Free-tier requests may be used by Google to improve its products. Do not submit personal, confidential or sensitive information.

## Security and publishing safeguards

- Never commit Google OAuth client secrets, refresh tokens, access tokens, API keys, passwords or `.env` files.
- Store credentials only through GitHub Actions Secrets or Cloudflare Worker Secrets.
- Do not make this repository public.
- Do not use or modify the separate PixelToolkit project for this automation.
- Automated Short upload is optional and PRIVATE-only; public playlist creation requires a separate manual workflow input; Community publishing remains manual.
- Do not add OAuth scopes, enable billing or change account/security settings without explicit authorization.

## 14-day pilot

The initial operating plan is a 14-day pilot. Review workflow completion, Gemini quota, academic review workload, CTR, retention by unit, and Short-to-long-video traffic before treating ten daily lessons as a permanent public release cadence. Ten long-form releases per day is a high volume; reduce public release frequency rather than sacrificing quality.


## Free YouTube publishing workflow

The production workflow uses GitHub Actions, Python, FFmpeg, the YouTube Data API and the existing GitHub Actions OAuth secrets. It has no third-party social scheduler or paid publishing API dependency.

- The daily workflow uses YouTube's resumable upload protocol to upload an audited Short and the featured long-form lesson as **PRIVATE** when the repository variable `YOUTUBE_PRIVATE_UPLOAD_ENABLED=true`. Both uploads include the synthetic-media disclosure flag.
- The private uploader has no public-publishing code path. Review the upload in YouTube Studio and make any public-release decision manually.
- The ten public playlists are created only when a user manually dispatches the workflow and explicitly selects `create_public_playlists=true`. This is off by default and requires the appropriate YouTube write scope.
- The daily workflow renders one featured long-form lesson per day, not ten long-form videos. The uploader requires a passing render report, ready academic review, owner-reference Chatterbox voice, no music and a valid 1920 × 1080 H.264 MP4. Placeholder eSpeak narration is draft-only.
- Community text and poll content are generated as drafts. YouTube's public Data API does not provide a Community-post creation endpoint, so do not use undocumented endpoints.

### OAuth and YouTube API limitations

The current external Google OAuth application is in Testing mode. Refresh tokens for YouTube scopes may expire after seven days, requiring the channel owner to authorize again and update the GitHub secret. This is not suitable for fully unattended long-running uploads until the OAuth configuration is resolved.

YouTube's current `videos.insert` reference states that uploads from unverified API projects are not automatically restricted to PRIVATE. This project nevertheless sets `privacyStatus=private` deliberately so every automated upload remains staged for human review. Public publishing is not implemented in this uploader. Follow current YouTube API Services Terms and any project-specific compliance instructions.

Remove unused paid-scheduler credentials from GitHub Actions repository secrets once you confirm they are no longer needed. No source code in this repository should read them.

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

When enabled, Chatterbox is used. If it is disabled or unavailable, the renderer may use eSpeak placeholder narration for draft preview only; the pre-publication audit blocks uploads unless the configured owner reference voice clone was used. The report records the provider and whether a reference voice clone was used, but never records the token or reference-audio contents.

The adapter sends narration text and the reference audio to the public ResembleAI Hugging Face Space for synthesis. Only use a recording of your own voice or a recording you have explicit permission to use. Chatterbox output contains an imperceptible Perth watermark and is MIT-licensed; the model's free Space remains subject to service availability and its usage limits.


## Pre-publication safety controls

The daily workflow runs `scripts/prepublish_audit.py` on the generated Short. It verifies that the MP4 is present, H.264, 1080×1920, no longer than three minutes, includes narration, uses the configured owner-authorized voice clone, and has no music track (the current renderer adds no music or third-party visual assets). A failed audit stops the publishing job.

The audits are not copyright certificates. They cannot query Content ID, establish third-party licensing, or guarantee that YouTube will not issue a claim. Check YouTube Studio's copyright checks and retain licences/permissions for any external asset. The current Short and long-form renderers create original typography slides and use narration only; no external stock clips, music or movie footage are included.

**Public publishing is not implemented in this project.** The optional YouTube uploader can only create a PRIVATE video for review. It cannot switch a video to Unlisted or Public. The owner must inspect the private video and publish it manually in YouTube Studio after checking academic accuracy, copyright status, subtitles and AI disclosure.

The audit report records `publish_authorized: false` and `human_review_required: true`; the workflow's publication switch is a separate account-owner authorization. Review educational accuracy, pronunciation, subtitles, originality, thumbnail/title accuracy, advertiser suitability, asset rights, and whether altered/synthetic-content disclosure applies before enabling public scheduling.

YouTube's monetization review evaluates channel-level originality and authenticity. Avoid repetitive mass-produced videos, generic template-only slideshows, scraped content, and minimally transformed third-party material. AI assistance is not automatically disqualifying, but the creator's original teaching, analysis and educational value must be clear.
