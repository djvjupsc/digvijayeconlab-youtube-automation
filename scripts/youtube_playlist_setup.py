"""Create the ten configured public YouTube playlists using a refresh-token grant.

Requires a refresh token freshly consented with the YouTube Data API youtube scope.
Existing playlists are re-used by exact title; this script is safe to re-run.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubePlaylistError(RuntimeError):
    pass


def _request_json(url, method="GET", token=None, body=None, form=False):
    headers = {"Accept": "application/json"}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        if exc.code == 403:
            raise YouTubePlaylistError(
                "YouTube denied playlist write access. Re-authorize the OAuth worker with "
                "https://www.googleapis.com/auth/youtube and store the newly issued refresh token "
                "in YOUTUBE_OAUTH_REFRESH_TOKEN. The current read/upload-only token cannot create playlists. "
                + detail
            ) from exc
        raise YouTubePlaylistError(f"YouTube API failed (HTTP {exc.code}): {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise YouTubePlaylistError(f"YouTube API connection failed: {exc}") from exc


def refresh_access_token(client_id, client_secret, refresh_token, request_json=_request_json):
    data = request_json(
        TOKEN_URL,
        method="POST",
        body={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        form=True,
    )
    access_token = data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise YouTubePlaylistError("Google OAuth token refresh response did not contain access_token.")
    return access_token


def fetch_existing_playlists(access_token, request_json=_request_json):
    existing = {}
    page_token = None
    while True:
        params = {"part": "snippet", "mine": "true", "maxResults": "50"}
        if page_token:
            params["pageToken"] = page_token
        url = API_BASE + "/playlists?" + urllib.parse.urlencode(params)
        payload = request_json(url, token=access_token)
        for item in payload.get("items", []):
            title = item.get("snippet", {}).get("title")
            playlist_id = item.get("id")
            if isinstance(title, str) and isinstance(playlist_id, str) and title not in existing:
                existing[title] = playlist_id
        page_token = payload.get("nextPageToken")
        if not page_token:
            return existing


def ensure_playlists(catalog, access_token, request_json=_request_json):
    items = catalog.get("items", [])
    if len(items) != 10:
        raise YouTubePlaylistError("Playlist catalogue must contain exactly ten configured playlists.")
    existing = fetch_existing_playlists(access_token, request_json=request_json)
    created, reused = [], []
    for row in items:
        title = row.get("title")
        description = row.get("description", "")
        if not isinstance(title, str) or not title.strip():
            raise YouTubePlaylistError("Playlist catalogue contains an empty title.")
        if title in existing:
            reused.append({"title": title, "playlist_id": existing[title]})
            continue
        payload = {
            "snippet": {
                "title": title,
                "description": description,
                "defaultLanguage": "en",
            },
            "status": {"privacyStatus": "public"},
        }
        result = request_json(
            API_BASE + "/playlists?part=snippet,status",
            method="POST",
            token=access_token,
            body=payload,
        )
        playlist_id = result.get("id")
        if not isinstance(playlist_id, str) or not playlist_id:
            raise YouTubePlaylistError(f"YouTube did not return a playlist ID for: {title}")
        existing[title] = playlist_id
        created.append({"title": title, "playlist_id": playlist_id})
    return {
        "status": "created_or_verified",
        "privacy_status": "public",
        "created": created,
        "reused": reused,
        "playlists": existing,
    }


def main():
    catalog_path = Path("config/playlist_catalog.json")
    output_path = Path("output/youtube-playlists.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client_id = os.environ.get("YOUTUBE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("YOUTUBE_OAUTH_CLIENT_SECRET")
    refresh_token = os.environ.get("YOUTUBE_OAUTH_REFRESH_TOKEN")
    if not all([client_id, client_secret, refresh_token]):
        result = {
            "status": "not_configured",
            "message": (
                "Playlist creation skipped. Add YOUTUBE_OAUTH_CLIENT_ID, "
                "YOUTUBE_OAUTH_CLIENT_SECRET and a newly consented "
                "YOUTUBE_OAUTH_REFRESH_TOKEN as GitHub Actions secrets. "
                "The refresh token must include the YouTube Data API youtube scope."
            ),
            "created": [],
            "reused": [],
            "playlists": {},
        }
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(result["message"])
        return 0

    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        access_token = refresh_access_token(client_id, client_secret, refresh_token)
        result = ensure_playlists(catalog, access_token)
    except (OSError, json.JSONDecodeError, YouTubePlaylistError) as exc:
        error = {
            "status": "error",
            "created": [],
            "reused": [],
            "playlists": {},
            "error": str(exc),
        }
        output_path.write_text(json.dumps(error, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(str(exc)) from exc

    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "playlists"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
