"""Schedule eligible DigvijayEconLab video files through Metricool.

This module does not create YouTube Community posts or playlists. It reads existing
playlist IDs from Metricool, uploads video files to Metricool storage, and schedules
YouTube video posts with public visibility. The daily workflow calls it only after
the deterministic + AI review publication gate passes.
"""

import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "https://app.metricool.com/api"
TZ = ZoneInfo("Asia/Kolkata")
PART_SIZE = 5 * 1024 * 1024


class MetricoolError(RuntimeError):
    pass


def _url(path, params):
    return BASE + path + "?" + urllib.parse.urlencode(params)


def _request(url, method="GET", token=None, body=None, content_type="application/json", timeout=180):
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Mc-Auth"] = token
    data = None
    if body is not None:
        if isinstance(body, bytes):
            data = body
            if content_type:
                headers["Content-Type"] = content_type
        else:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = content_type
    elif content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            if not raw:
                return {}, response.headers
            try:
                return json.loads(raw.decode("utf-8")), response.headers
            except json.JSONDecodeError:
                return {"raw": raw.decode("utf-8", errors="replace")[:1000]}, response.headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1500]
        raise MetricoolError(f"Metricool API failed ({exc.code}) for {method} {url.split('?')[0]}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MetricoolError(f"Metricool connection failed for {method} {url.split('?')[0]}: {exc}") from exc


def _data(payload):
    return payload.get("data", payload) if isinstance(payload, dict) else payload


def _api_params(user_id, blog_id):
    return {"userId": str(user_id), "blogId": str(blog_id)}


def list_youtube_playlists(token, user_id, blog_id):
    params = _api_params(user_id, blog_id)
    params["refresh"] = "true"
    result, _ = _request(_url("/v2/scheduler/catalogs/youtube/playlists", params), token=token)
    items = _data(result)
    if isinstance(items, dict):
        items = items.get("items", items.get("playlists", []))
    if not isinstance(items, list):
        raise MetricoolError("Metricool playlist response was not a list.")
    output = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name")
        playlist_id = item.get("id") or item.get("playlistId")
        if isinstance(title, str) and isinstance(playlist_id, (str, int)):
            output[title] = str(playlist_id)
    return output


def upload_media(path, token, user_id, blog_id):
    path = Path(path)
    if not path.is_file():
        raise MetricoolError(f"Video file does not exist: {path}")
    if path.suffix.lower() != ".mp4":
        raise MetricoolError(f"Only MP4 media is accepted by this publishing pipeline: {path.name}")
    content = path.read_bytes()
    if not content:
        raise MetricoolError(f"Video file is empty: {path}")
    parts = []
    for offset in range(0, len(content), PART_SIZE):
        chunk = content[offset:offset + PART_SIZE]
        parts.append({
            "size": len(chunk),
            "startByte": offset,
            "endByte": offset + len(chunk),
            "hash": base64.b64encode(hashlib.sha256(chunk).digest()).decode("ascii"),
        })

    params = _api_params(user_id, blog_id)
    transaction, _ = _request(
        _url("/v2/media/s3/upload-transactions", params),
        method="PUT",
        token=token,
        body={
            "resourceType": "planner",
            "contentType": "video/mp4",
            "fileExtension": "mp4",
            "parts": parts,
        },
    )
    result = _data(transaction)
    if not isinstance(result, dict):
        raise MetricoolError("Metricool did not return an upload transaction.")
    key = result.get("key")
    bucket = result.get("bucket")
    upload_type = str(result.get("uploadType", "")).upper()
    if not key or not bucket:
        raise MetricoolError("Metricool upload transaction is missing key or bucket.")

    completed_parts = []
    if upload_type == "SIMPLE" or result.get("presignedUrl"):
        signed_url = result.get("presignedUrl")
        if not signed_url:
            raise MetricoolError("Metricool simple upload has no presigned URL.")
        _, headers = _request(
            signed_url,
            method="PUT",
            body=content,
            token=None,
            content_type="video/mp4",
            timeout=300,
        )
        # Metricool's simple completion contract requires the file URL supplied
        # by its transaction response. Do not guess an S3 URL from bucket/key.
        file_url = result.get("fileUrl")
        if not isinstance(file_url, str) or not file_url.startswith("https://"):
            raise MetricoolError("Metricool simple upload transaction omitted its fileUrl.")
        complete_body = {"simple": {"fileUrl": file_url}}
    else:
        urls = result.get("parts")
        upload_id = result.get("uploadId")
        if not isinstance(urls, list) or not upload_id or len(urls) != len(parts):
            raise MetricoolError("Metricool multipart response does not match the requested parts.")
        for index, (part, signed) in enumerate(zip(parts, urls)):
            start = part["startByte"]
            end = part["endByte"]
            chunk = content[start:end]
            presigned_url = signed.get("presignedUrl")
            part_number = signed.get("partNumber", index + 1)
            if not presigned_url:
                raise MetricoolError(f"Metricool multipart URL missing for part {part_number}.")
            _, headers = _request(
                presigned_url,
                method="PUT",
                body=chunk,
                token=None,
                content_type="video/mp4",
                timeout=300,
            )
            etag = headers.get("ETag")
            if not etag:
                raise MetricoolError(f"Upload response omitted ETag for part {part_number}.")
            completed_parts.append({"partNumber": part_number, "etag": etag})
        complete_body = {
            "multipart": {
                "uploadId": upload_id,
                "key": key,
                "parts": completed_parts,
            }
        }

    completed, _ = _request(
        _url("/v2/media/s3/upload-transactions", params),
        method="PATCH",
        token=token,
        body=complete_body,
    )
    final = _data(completed)
    file_url = final.get("convertedFileUrl") or final.get("fileUrl") if isinstance(final, dict) else None
    if not isinstance(file_url, str) or not file_url.startswith("https://"):
        raise MetricoolError("Metricool upload completion did not return a usable HTTPS file URL.")
    return file_url


def publication_gate(manifest, root=Path(".")):
    issues = []
    units = manifest.get("units", [])
    if len(units) != 10:
        issues.append("The daily manifest does not contain exactly ten unit lessons.")
        return False, issues

    corrected_dir = Path(root) / "output/corrected_scripts"
    review_dir = Path(root) / "output/reviews"
    quality_dir = Path(root) / "output/quality_checks"

    for item in units:
        unit = int(item["unit"])
        prefix = f"unit-{unit:02d}-"
        scripts = sorted(corrected_dir.glob(prefix + "*.md"))
        if len(scripts) != 1:
            issues.append(f"Unit {unit}: expected exactly one corrected script, found {len(scripts)}.")
            continue
        script_path = scripts[0]
        script = script_path.read_text(encoding="utf-8")
        if re.search(r"\[\s*VERIFY\b", script, flags=re.IGNORECASE):
            issues.append(f"Unit {unit}: unresolved [VERIFY] marker remains in corrected script.")

        review_path = review_dir / f"{script_path.stem}-quality-review.md"
        original_review_path = review_dir / f"{script_path.stem}-original-quality-review.md"
        deterministic_path = quality_dir / f"{script_path.stem}-corrected-deterministic-check.md"
        for file_path, label in [
            (review_path, "corrected academic review"),
            (original_review_path, "original academic review"),
            (deterministic_path, "corrected deterministic report"),
        ]:
            if not file_path.is_file():
                issues.append(f"Unit {unit}: missing {label}.")
        if review_path.is_file():
            report_text = review_path.read_text(encoding="utf-8")
            report = report_text.upper()
            if "HOLD FOR CORRECTION" in report or "NOT READY" in report:
                issues.append(f"Unit {unit}: academic reviewer returned a HOLD/not-ready verdict.")
            lines = report_text.splitlines()
            verdict = ""
            for index, line in enumerate(lines):
                if "overall verdict" in line.lower():
                    verdict = next((candidate.strip() for candidate in lines[index + 1:] if candidate.strip()), "")
                    break
            if not any(word in verdict.lower() for word in ("ready", "approved", "pass")):
                issues.append(f"Unit {unit}: corrected academic review has no explicit READY/APPROVED verdict.")
            if "[VERIFY" in report:
                issues.append(f"Unit {unit}: academic review still reports verification gaps.")
        if deterministic_path.is_file():
            report = deterministic_path.read_text(encoding="utf-8")
            if "- Blocking findings: 0" not in report:
                issues.append(f"Unit {unit}: corrected deterministic report has blocking findings or is malformed.")
            if "STRUCTURAL CHECKS PASSED" not in report:
                issues.append(f"Unit {unit}: deterministic gate did not explicitly pass.")
    return not issues, issues


def list_existing_posts(token, user_id, blog_id, start_dt, end_dt):
    params = _api_params(user_id, blog_id)
    params.update({
        "start": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "end": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "timezone": "Asia/Kolkata",
    })
    result, _ = _request(_url("/v2/scheduler/posts", params), token=token)
    items = _data(result)
    if isinstance(items, dict):
        items = items.get("items", items.get("posts", []))
    return items if isinstance(items, list) else []


def _already_scheduled(posts, title, date_time):
    target = date_time.strftime("%Y-%m-%d")
    for post in posts:
        if not isinstance(post, dict):
            continue
        if post.get("youtubeData", {}).get("title") == title:
            pub = post.get("publicationDate", {})
            if isinstance(pub, dict) and str(pub.get("dateTime", "")).startswith(target):
                return post
    return None


def schedule_video(path, title, description, tags, playlist_id, kind, publish_at,
                   token, user_id, blog_id, job_id):
    if not playlist_id:
        raise MetricoolError(f"No existing YouTube playlist ID was found for: {title}")
    media_url = upload_media(path, token, user_id, blog_id)
    params = _api_params(user_id, blog_id)
    params["jobId"] = job_id
    payload = {
        "publicationDate": {
            "dateTime": publish_at.strftime("%Y-%m-%dT%H:%M:%S"),
            "timezone": "Asia/Kolkata",
        },
        "text": description,
        "providers": [{"network": "youtube"}],
        "media": [media_url],
        "autoPublish": True,
        "draft": False,
        "saveExternalMediaFiles": True,
        "youtubeData": {
            "title": title[:100],
            "type": "SHORT" if kind == "short" else "VIDEO",
            "privacy": "public",
            "tags": list(dict.fromkeys(tags))[:30],
            "category": "27",
            "playlistId": str(playlist_id),
            "madeForKids": False,
            "isAiGeneratedContent": True,
            "notifySubscribers": True,
        },
    }
    result, _ = _request(
        _url("/v2/scheduler/posts", params),
        method="POST",
        token=token,
        body=payload,
    )
    return _data(result)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: metricool_publish.py DAILY_MANIFEST.json")
    root = Path(".")
    manifest_path = Path(sys.argv[1])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    date = manifest["publication_date"]
    report_dir = root / "output/metricool"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{date}-publishing-report.json"

    token = os.environ.get("METRICOOL_API_TOKEN")
    user_id = os.environ.get("METRICOOL_USER_ID")
    blog_id = os.environ.get("METRICOOL_BLOG_ID")
    if not all([token, user_id, blog_id]):
        report = {
            "status": "not_configured",
            "message": "Add METRICOOL_API_TOKEN, METRICOOL_USER_ID and METRICOOL_BLOG_ID GitHub Actions secrets. No video was scheduled.",
            "publication_date": date,
            "scheduled": [],
            "skipped": ["All public publishing was skipped because Metricool API credentials are missing."],
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(report["message"])
        return 0

    passed, issues = publication_gate(manifest, root)
    if not passed:
        report = {
            "status": "blocked_by_academic_gate",
            "publication_date": date,
            "scheduled": [],
            "blocking_issues": issues,
            "message": "No public publishing was performed because one or more unit quality gates failed.",
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(report["message"])
        for issue in issues:
            print("BLOCK: " + issue)
        return 0

    try:
        playlists = list_youtube_playlists(token, user_id, blog_id)
        publish_dt = datetime.fromisoformat(date).replace(tzinfo=TZ)
        window_start = publish_dt.replace(hour=0, minute=0, second=0)
        window_end = publish_dt.replace(hour=23, minute=59, second=59)
        existing_posts = list_existing_posts(token, user_id, blog_id, window_start, window_end)
        timeline = json.loads((root / "config/daily_timeline.json").read_text(encoding="utf-8"))
        scheduled, skipped = [], []

        # Long-form video files are optional until the separate long-form renderer exists.
        seo_path = root / "output/seo" / f"{date}-seo-metadata.json"
        seo_items = {}
        if seo_path.is_file():
            seo_items = {int(row["unit"]): row for row in json.loads(seo_path.read_text(encoding="utf-8"))}
        for item in manifest["units"]:
            unit = int(item["unit"])
            video_path = root / "output/videos" / f"unit-{unit:02d}.mp4"
            if not video_path.is_file():
                skipped.append(f"Unit {unit}: no finished long-form MP4 exists yet; script package is not uploaded.")
                continue
            meta = seo_items.get(unit, {})
            title = meta.get("video_title", f"UGC NET Economics Unit {unit}: {item['topic']} | DigvijayEconLab")
            description = meta.get("description", f"{item['topic']} — Unit {unit}, {item['unit_name']}. Bilingual Economics lesson by DigvijayEconLab.")
            tags = meta.get("tags", ["UGC NET Economics", "MPPSC Assistant Professor", "Economics", "DigvijayEconLab"])
            playlist_title = item["playlist_title"]
            playlist_id = playlists.get(playlist_title)
            slot = next((row["time"] for row in timeline["full_lesson_release_slots"] if int(row["unit"]) == unit), "09:00")
            hour, minute = map(int, slot.split(":"))
            when = publish_dt.replace(hour=hour, minute=minute, second=0)
            if _already_scheduled(existing_posts, title, when):
                scheduled.append({"unit": unit, "title": title, "status": "already_scheduled"})
                continue
            result = schedule_video(video_path, title, description, tags, playlist_id, "video",
                                    when, token, user_id, blog_id, f"digvijayeconlab-{date}-unit-{unit:02d}")
            scheduled.append({"unit": unit, "title": title, "status": "scheduled", "result": result})

        short_path = root / "output/shorts" / f"{date}-digvijayeconlab-short.mp4"
        short_json_path = root / "output/shorts" / f"{date}-short.json"
        short_render_path = root / "output/shorts" / f"{date}-short-render.json"
        if short_path.is_file() and short_json_path.is_file():
            if not short_render_path.is_file():
                skipped.append("Short not scheduled: no render-provider report exists.")
            else:
                render_report = json.loads(short_render_path.read_text(encoding="utf-8"))
                if not render_report.get("voice_clone_used"):
                    skipped.append("Short not scheduled: it was not narrated with the configured owner's HeyGen voice clone.")
                else:
                    short_data = json.loads(short_json_path.read_text(encoding="utf-8"))
                    focus = short_data["focus_unit"]
                    unit_no = int(focus["unit"])
                    unit_item = next(item for item in manifest["units"] if int(item["unit"]) == unit_no)
                    playlist_id = playlists.get(unit_item["playlist_title"])
                    title = short_data["short_title"]
                    description = short_data.get("short_description", f"Daily Economics Short by DigvijayEconLab — {focus['topic']}")
                    tags = ["DigvijayEconLab", "UGC NET Economics", "MPPSC Assistant Professor Economics",
                            unit_item["unit_name"], focus["topic"], "Economics Shorts"]
                    when = publish_dt.replace(hour=19, minute=0, second=0)
                    if _already_scheduled(existing_posts, title, when):
                        scheduled.append({"kind": "short", "title": title, "status": "already_scheduled"})
                    else:
                        result = schedule_video(short_path, title, description, tags, playlist_id, "short",
                                                when, token, user_id, blog_id, f"digvijayeconlab-{date}-short")
                        scheduled.append({"kind": "short", "title": title, "status": "scheduled", "result": result})
        else:
            skipped.append("No rendered Short MP4 exists; Short not scheduled.")

        report = {
            "status": "completed",
            "publication_date": date,
            "scheduled": scheduled,
            "skipped": skipped,
            "community_post": "Not published: Metricool API and YouTube Data API do not expose Community-post creation.",
            "playlist_creation": "Not performed: this API only reads YouTube playlists; create the ten playlists once in YouTube Studio or authorize the YouTube Data API youtube scope separately.",
        }
    except (MetricoolError, KeyError, ValueError, OSError) as exc:
        report = {
            "status": "error",
            "publication_date": date,
            "scheduled": scheduled if "scheduled" in locals() else [],
            "error": str(exc),
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
