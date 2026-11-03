# DigvijayEconLab — Daily 10-Unit Production Calendar

All times are India Standard Time (Asia/Kolkata).

## Daily production cadence

The GitHub workflow starts at **08:00** and prepares the next day's content pack. This one-day lead time is intentional: it leaves time for subject-matter verification, editing, thumbnail preparation and scheduling.

| Time | Deliverable / target slot |
|---|---|
| 08:00 | Generate next-day pack: 10 unit lesson scripts, academic reviews, corrections, one vertical Short MP4, one Community post and poll |
| 08:30 | Target Community post preview/poll slot (schedule manually in YouTube Studio) |
| 09:00 | Unit 1 — Micro Economics |
| 10:00 | Unit 2 — Macro Economics |
| 11:00 | Unit 3 — Statistics and Econometrics |
| 12:00 | Unit 4 — Mathematical Economics |
| 13:00 | Unit 5 — International Economics |
| 14:00 | Unit 6 — Public Economics |
| 15:00 | Unit 7 — Money and Banking |
| 16:00 | Unit 8 — Growth and Development Economics |
| 17:00 | Unit 9 — Environmental Economics and Demography |
| 18:00 | Unit 10 — Indian Economy |
| 19:00 | Target YouTube Short slot; one Short per day, rotating its focus across the ten units |
| 19:30 | Comment review, corrections log and next-day topic review |

These are recommended publication slots, not active publishing automations. The repository creates the production materials; public release remains manual and requires review.

## Daily output target

- **10 full lesson script packages:** one from every unit, each with original script, first academic review, corrected draft, correction log, second review and deterministic quality reports.
- **1 Shorts MP4 draft:** 9:16 (1080 × 1920), bilingual scene cards and synthetic Hindi/English placeholder narration. No music is added.
- **1 Community post draft:** a bilingual daily preview plus one syllabus-related poll and suggested pinned comment.
- **10 playlist definitions:** one per syllabus unit, with a title and description ready for channel setup.

The current pipeline does not render the ten long-form lesson scripts into finished landscape MP4 videos. Their video editing, narration replacement, thumbnails and final fact-checking remain production tasks. The Short is rendered as a draft MP4, but its synthetic voice pronunciation and pacing must be reviewed.

## Ten playlist titles

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

The matching descriptions are in `config/playlist_catalog.json`. These are playlist definitions only; the repository has not created playlists on YouTube.

## Topic rotation and duplicate protection

The rotation starts with the first topic listed under each unit in `config/unit_content_plan.json`. After a complete daily pack succeeds, the day counter advances by one and every unit moves to its next syllabus topic. Once a unit reaches the end of its topic list, its sequence cycles back to the beginning. A successful pack cannot be claimed twice on the same India-local date. Failed packs do not advance the rotation; a same-day retry requires the explicit `retry_failed` workflow input.

The plan uses the uploaded UGC NET Economics syllabus, Subject Economics, Code No. 01. Topic labels follow that document's unit structure. No PYQs, current statistics or unprovided source citations are invented.

## 14-day pilot

Run the proposed cadence for 14 days before treating it as a permanent public schedule. Review:
- Whether the ten daily lesson scripts can be fact-checked and converted into long-form videos without reducing academic quality.
- Audience retention and click-through rate by unit and by release slot.
- Short-to-long-video traffic and Community poll responses.
- Gemini API quota and workflow completion rate.

Ten full lessons per day is a high-volume plan. If review capacity or API quotas become a bottleneck, reduce public release frequency rather than bypassing academic quality gates.

## Platform and publishing limitations

- **Community posts:** the daily post and poll are drafted by the workflow. Schedule them manually in YouTube Studio. YouTube's Help Center documents scheduling through the Studio post composer; there is no Community-post creation method in the current YouTube Data API v3 reference.
- **Playlists:** the catalog supplies titles and descriptions. Creating playlists or inserting videos requires YouTube Data API write authorization. The existing OAuth grant does not include the playlist-management `youtube` / `youtube.force-ssl` scope, so this automation does not create or modify playlists.
- **Videos:** public upload and publishing remain disabled. The current workflow does not upload any video.
- **Shorts:** YouTube currently classifies square or vertical uploads up to three minutes as Shorts for standard channels, subject to its stated conditions. The generated Short must stay within that duration and pass a copyright and factual review.

## Human approval checklist

Before any public release, a reviewer must:
1. Compare the original and corrected scripts.
2. Resolve all `[VERIFY]` markers and every Critical/High finding against authoritative sources.
3. Verify Hindi-English conceptual equivalence, equations, examples, MCQ answers and explanations.
4. Replace or approve synthetic Short narration, verify subtitles and check the rendered video.
5. Check copyright, thumbnail, title, description, playlist and Community post.
6. Approve the final version for manual scheduling in YouTube Studio.

The workflow is draft production, not an academic certification or automatic publication system.
