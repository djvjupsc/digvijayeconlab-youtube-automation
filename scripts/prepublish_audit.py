"""Pre-publication safety audit for the generated DigvijayEconLab Short.

This checks technical delivery and the assets produced by this repository. It cannot
predict Content ID matches, grant copyright clearance, or replace a human review.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path


def inspect_video(path, ffprobe="ffprobe"):
    if not Path(path).is_file() or Path(path).stat().st_size == 0:
        raise ValueError("Rendered MP4 is missing or empty.")
    if not shutil.which(ffprobe):
        raise ValueError("ffprobe is required for the pre-publication audit.")
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    if not video:
        raise ValueError("MP4 contains no video stream.")
    if (video.get("width"), video.get("height")) != (1080, 1920):
        raise ValueError("Short must be rendered at 1080x1920.")
    if video.get("codec_name") != "h264":
        raise ValueError("Short video codec must be H.264.")
    if not audio:
        raise ValueError("Short must contain narration audio.")
    duration = float(data.get("format", {}).get("duration", 0))
    if duration <= 0 or duration > 180:
        raise ValueError("Short duration must be greater than zero and no more than 180 seconds.")
    return {"duration_seconds": round(duration, 2), "width": 1080, "height": 1920,
            "video_codec": "h264", "audio_streams": len(audio)}


def audit(short_json, render_json, video_path, output_path):
    storyboard = json.loads(Path(short_json).read_text(encoding="utf-8"))
    render = json.loads(Path(render_json).read_text(encoding="utf-8"))
    problems = []
    if not isinstance(storyboard.get("short_title"), str) or not storyboard["short_title"].strip():
        problems.append("Short title is missing.")
    if len(storyboard.get("scenes", [])) < 4:
        problems.append("Short storyboard has fewer than four scenes.")
    if render.get("music") != "none":
        problems.append("Only repository-generated narration is approved by this pipeline; soundtrack must be removed or separately licensed and reviewed.")
    if not render.get("voice_clone_used"):
        problems.append("Owner-authorized voice clone was not used; generic placeholder narration cannot be published.")
    if render.get("voice_reference_stored_in_repository") is not False:
        problems.append("Voice reference must not be stored in the repository.")
    if render.get("review_required") is not True:
        problems.append("Render report must retain the human-review requirement.")
    technical = {}
    if not problems:
        try:
            technical = inspect_video(video_path)
        except (ValueError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            problems.append(str(exc))
    report = {
        "status": "pass" if not problems else "blocked",
        "publish_authorized": False,
        "human_review_required": True,
        "copyright_clearance": "not_certified; verify YouTube Studio Checks and asset rights before publication",
        "ai_disclosure_review_required": True,
        "technical": technical,
        "blocking_issues": problems,
        "limitations": [
            "This audit cannot query Content ID or guarantee absence of copyright claims.",
            "This audit cannot determine whether a third-party asset is licensed; this pipeline currently uses generated slides, narration and no music.",
            "A human must review educational accuracy, pronunciation, subtitles, visual quality, originality and the YouTube altered-content disclosure question.",
        ],
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return not problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("short_json")
    parser.add_argument("render_json")
    parser.add_argument("video")
    parser.add_argument("output")
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.short_json, args.render_json, args.video, args.output) else 1)


if __name__ == "__main__":
    main()
