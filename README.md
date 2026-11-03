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
- `scripts/render_short_video.py` — renders a 1080 × 1920 narrated Short draft using Pillow, eSpeak NG and FFmpeg; no music is added.
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

- The daily Short is rendered as a 1080 × 1920 MP4 with bilingual on-screen text and synthesized Hindi/English narration. The voice is a placeholder and may sound robotic; review pronunciation and pacing. No background music or third-party assets are added.
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
