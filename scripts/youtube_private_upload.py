"""Stage audited Shorts or one featured lesson as PRIVATE YouTube videos.

Uses the YouTube resumable-upload protocol. This script deliberately has no public
publishing path. The channel owner makes every public-release decision in Studio.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubeUploadError(RuntimeError):
    pass


def _refresh_access_token(client_id, client_secret, refresh_token):
    body = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_URL, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise YouTubeUploadError(f"Google OAuth refresh failed: {exc}") from exc
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise YouTubeUploadError("Google OAuth response did not contain an access token.")
    return token


def upload_private_video(video_path, metadata, access_token, opener=urllib.request.urlopen):
    """Initiate a resumable upload, send the MP4, and verify PRIVATE visibility."""
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise YouTubeUploadError("Video MP4 is missing or empty.")
    title = metadata.get("video_title") or metadata.get("short_title")
    description = metadata.get("description") or metadata.get("short_description", "")
    if not isinstance(title, str) or not title.strip():
        raise YouTubeUploadError("Video title is missing.")
    if not isinstance(description, str):
        raise YouTubeUploadError("Video description must be text.")
    tags = metadata.get("tags", ["DigvijayEconLab", "Economics"])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise YouTubeUploadError("Video tags must be a list of strings.")

    payload = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": "27",
            "defaultLanguage": "hi",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    file_size = path.stat().st_size
    init_url = UPLOAD_URL + "?" + urllib.parse.urlencode({
        "uploadType": "resumable", "part": "snippet,status"
    })
    init_request = urllib.request.Request(
        init_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(file_size),
        },
    )
    try:
        with opener(init_request, timeout=60) as response:
            session_url = response.headers.get("Location")
            if not isinstance(session_url, str) or not session_url.startswith("https://"):
                raise YouTubeUploadError("YouTube did not return a valid HTTPS resumable upload URL.")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1500]
        raise YouTubeUploadError(f"YouTube upload initialization failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise YouTubeUploadError(f"YouTube upload initialization failed: {exc}") from exc

    media_request = urllib.request.Request(
        session_url,
        data=path.read_bytes(),
        method="PUT",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "video/mp4",
            "Content-Length": str(file_size),
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
        },
    )
    try:
        with opener(media_request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1500]
        raise YouTubeUploadError(f"YouTube media upload failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise YouTubeUploadError(f"YouTube media upload failed: {exc}") from exc

    video_id = result.get("id")
    privacy = result.get("status", {}).get("privacyStatus")
    synthetic_disclosure = result.get("status", {}).get("containsSyntheticMedia")
    if not isinstance(video_id, str) or not video_id:
        raise YouTubeUploadError("YouTube response did not include a video ID.")
    if privacy != "private":
        raise YouTubeUploadError("YouTube did not confirm private visibility; check YouTube Studio.")
    if synthetic_disclosure is not True:
        raise YouTubeUploadError("YouTube did not confirm the synthetic-content disclosure; check YouTube Studio.")
    return {
        "video_id": video_id,
        "privacy_status": "private",
        "contains_synthetic_media": True,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


def _load_upload_job(root, publication_date, kind):
    if kind == "short":
        audit_path = root / "output/shorts" / f"{publication_date}-prepublish-audit.json"
        metadata_path = root / "output/shorts" / f"{publication_date}-short.json"
        video_path = root / "output/shorts" / f"{publication_date}-digvijayeconlab-short.mp4"
        if not audit_path.is_file() or not metadata_path.is_file() or not video_path.is_file():
            return None, "Short audit, storyboard or rendered MP4 is missing."
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if audit.get("status") != "pass" or audit.get("human_review_required") is not True:
            return None, "Short is not eligible: technical audit did not pass or human review flag is missing."
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        return (video_path, metadata, audit), None

    render_path = root / "output/longform" / f"{publication_date}-longform-render.json"
    if not render_path.is_file():
        return None, "Long-form render report is missing."
    render = json.loads(render_path.read_text(encoding="utf-8"))
    technical = render.get("technical", {})
    eligible = (
        render.get("audit_status") == "pass"
        and render.get("upload_eligible") is True
        and render.get("voice_clone_used") is True
        and render.get("voice_reference_stored_in_repository") is False
        and render.get("music") == "none"
        and render.get("review_required") is True
        and technical.get("width") == 1920
        and technical.get("height") == 1080
        and technical.get("video_codec") == "h264"
        and int(technical.get("audio_streams", 0)) > 0
        and float(technical.get("duration_seconds", 0)) > 0
    )
    if not eligible:
        return None, "Long-form video is not eligible: owner voice, audit, no-music, human-review or technical checks did not pass."
    video_path = Path(render.get("video", ""))
    if not video_path.is_absolute():
        video_path = root / video_path
    if not video_path.is_file():
        return None, "Long-form MP4 is missing."
    seo_path = root / "output/seo" / f"{publication_date}-seo-metadata.json"
    if not seo_path.is_file():
        return None, "Long-form SEO metadata is missing."
    seo_rows = json.loads(seo_path.read_text(encoding="utf-8"))
    unit = int(render.get("unit", 0))
    metadata = next((row for row in seo_rows if int(row.get("unit", 0)) == unit), None)
    if not metadata:
        return None, "Long-form SEO metadata for the featured unit is missing."
    metadata = {
        "video_title": metadata.get("video_title"),
        "description": metadata.get("description"),
        "tags": metadata.get("tags", []),
    }
    return (video_path, metadata, render), None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("publication_date")
    parser.add_argument("--kind", choices=("short", "longform"), default="short")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root)
    report_dir = root / "output/youtube"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{args.publication_date}-{args.kind}-private-upload.json"

    if os.environ.get("YOUTUBE_PRIVATE_UPLOAD_ENABLED", "").strip().lower() != "true":
        report = {
            "status": "disabled",
            "kind": args.kind,
            "uploaded": False,
            "message": "Private upload is disabled. Set YOUTUBE_PRIVATE_UPLOAD_ENABLED=true to enable PRIVATE review uploads.",
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(report["message"])
        return 0

    try:
        job, issue = _load_upload_job(root, args.publication_date, args.kind)
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise SystemExit(f"Could not validate the {args.kind} upload package: {exc}") from exc
    if issue:
        report = {
            "status": "skipped_not_eligible",
            "kind": args.kind,
            "uploaded": False,
            "message": issue,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(issue)
        return 0

    credentials = [os.environ.get(key) for key in (
        "YOUTUBE_OAUTH_CLIENT_ID", "YOUTUBE_OAUTH_CLIENT_SECRET", "YOUTUBE_OAUTH_REFRESH_TOKEN"
    )]
    if not all(credentials):
        raise SystemExit("Private upload blocked: YouTube OAuth GitHub secrets are incomplete.")

    video_path, metadata, audit = job
    try:
        token = _refresh_access_token(*credentials)
        result = upload_private_video(video_path, metadata, token)
    except (OSError, json.JSONDecodeError, YouTubeUploadError) as exc:
        raise SystemExit(str(exc)) from exc

    report = {
        "status": "uploaded_private",
        "kind": args.kind,
        "uploaded": True,
        **result,
        "human_review_required": True,
        "public_publishing": "not_supported_by_this_script",
        "next_step": "Review the private video in YouTube Studio. Publish manually only after checking academic accuracy, rights, captions and the altered-content disclosure.",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
