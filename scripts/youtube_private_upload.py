"""Upload the audited daily Short to YouTube as PRIVATE for human review.

This script deliberately has no public-publishing path. A human must inspect the
private upload in YouTube Studio and choose whether/when to publish it.
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
    path = Path(video_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise YouTubeUploadError("Short MP4 is missing or empty.")
    title = metadata.get("short_title")
    description = metadata.get("short_description", "")
    if not isinstance(title, str) or not title.strip():
        raise YouTubeUploadError("Short title is missing.")
    tags = metadata.get("tags", ["DigvijayEconLab", "Economics"])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise YouTubeUploadError("Short tags must be a list of strings.")

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
        },
    }
    boundary = "djel-upload-boundary-2026"
    metadata_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    body = (
        b"--" + boundary.encode() + b"\r\n"
        b"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        + metadata_bytes + b"\r\n"
        b"--" + boundary.encode() + b"\r\n"
        b"Content-Type: video/mp4\r\n\r\n"
        + path.read_bytes() + b"\r\n"
        b"--" + boundary.encode() + b"--"
    )
    url = UPLOAD_URL + "?" + urllib.parse.urlencode({
        "uploadType": "multipart", "part": "snippet,status"
    })
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )
    try:
        with opener(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1500]
        raise YouTubeUploadError(f"YouTube upload failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise YouTubeUploadError(f"YouTube upload failed: {exc}") from exc

    video_id = result.get("id")
    privacy = result.get("status", {}).get("privacyStatus")
    if not isinstance(video_id, str) or not video_id:
        raise YouTubeUploadError("YouTube response did not include a video ID.")
    if privacy != "private":
        raise YouTubeUploadError("YouTube did not confirm private visibility; check YouTube Studio.")
    return {"video_id": video_id, "privacy_status": "private",
            "url": f"https://www.youtube.com/watch?v={video_id}"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("publication_date")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root)
    report_dir = root / "output/youtube"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{args.publication_date}-private-upload.json"

    if os.environ.get("YOUTUBE_PRIVATE_UPLOAD_ENABLED", "").strip().lower() != "true":
        report = {"status": "disabled", "uploaded": False,
                  "message": "Private upload is disabled. Set repository variable YOUTUBE_PRIVATE_UPLOAD_ENABLED=true to enable private review uploads."}
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(report["message"])
        return 0

    audit_path = root / "output/shorts" / f"{args.publication_date}-prepublish-audit.json"
    storyboard_path = root / "output/shorts" / f"{args.publication_date}-short.json"
    video_path = root / "output/shorts" / f"{args.publication_date}-digvijayeconlab-short.mp4"
    if not audit_path.is_file():
        raise SystemExit("Private upload blocked: pre-publication audit report is missing.")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "pass" or audit.get("human_review_required") is not True:
        raise SystemExit("Private upload blocked: technical audit did not pass or review flag is missing.")
    if not storyboard_path.is_file() or not video_path.is_file():
        raise SystemExit("Private upload blocked: storyboard or rendered Short is missing.")

    credentials = [os.environ.get(key) for key in (
        "YOUTUBE_OAUTH_CLIENT_ID", "YOUTUBE_OAUTH_CLIENT_SECRET", "YOUTUBE_OAUTH_REFRESH_TOKEN"
    )]
    if not all(credentials):
        raise SystemExit("Private upload blocked: YouTube OAuth GitHub secrets are incomplete.")

    try:
        token = _refresh_access_token(*credentials)
        metadata = json.loads(storyboard_path.read_text(encoding="utf-8"))
        result = upload_private_video(video_path, metadata, token)
    except (OSError, json.JSONDecodeError, YouTubeUploadError) as exc:
        raise SystemExit(str(exc)) from exc

    report = {
        "status": "uploaded_private",
        "uploaded": True,
        **result,
        "human_review_required": True,
        "public_publishing": "not_supported_by_this_script",
        "next_step": "Review the private video in YouTube Studio. Publish manually only after checking accuracy, rights, captions and the altered-content disclosure.",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
