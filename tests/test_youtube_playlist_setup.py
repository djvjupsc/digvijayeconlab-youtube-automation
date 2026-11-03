import unittest
from scripts.youtube_playlist_setup import YouTubePlaylistError, ensure_playlists


def make_catalog():
    return {
        "items": [
            {"title": f"Unit {i} | Economics", "description": f"Unit {i} course lessons"}
            for i in range(1, 11)
        ]
    }


class YouTubePlaylistSetupTests(unittest.TestCase):
    def test_creates_missing_playlists_only_once(self):
        existing = {}
        calls = []

        def fake_request(url, method="GET", token=None, body=None, form=False):
            calls.append((url, method, body))
            if method == "GET":
                return {
                    "items": [
                        {"id": "existing-1", "snippet": {"title": "Unit 1 | Economics"}}
                    ]
                }
            title = body["snippet"]["title"]
            playlist_id = f"id-{len(existing) + 1}"
            existing[title] = playlist_id
            return {"id": playlist_id}

        result = ensure_playlists(make_catalog(), "access-token", request_json=fake_request)
        self.assertEqual(len(result["created"]), 9)
        self.assertEqual(len(result["reused"]), 1)
        self.assertEqual(result["playlists"]["Unit 1 | Economics"], "existing-1")
        self.assertEqual(len([call for call in calls if call[1] == "POST"]), 9)
        self.assertEqual(result["privacy_status"], "public")

    def test_rejects_catalogue_that_is_not_exactly_ten_playlists(self):
        with self.assertRaisesRegex(YouTubePlaylistError, "exactly ten"):
            ensure_playlists({"items": make_catalog()["items"][:9]}, "access-token")

    def test_rejects_empty_playlist_title(self):
        catalog = make_catalog()
        catalog["items"][3]["title"] = " "
        with self.assertRaisesRegex(YouTubePlaylistError, "empty title"):
            ensure_playlists(catalog, "access-token", request_json=lambda *a, **k: {"items": []})


if __name__ == "__main__":
    unittest.main()
