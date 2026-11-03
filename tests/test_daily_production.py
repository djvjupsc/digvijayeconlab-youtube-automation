import unittest
from scripts.daily_production import build_manifest, validate_plan


class DailyProductionPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = {
            "version": 1,
            "timezone": "Asia/Kolkata",
            "units": [
                {
                    "unit": i,
                    "id": f"unit-{i}",
                    "name": f"Unit {i}",
                    "playlist_title": f"Playlist {i}",
                    "playlist_description": f"Description {i}",
                    "topics": [f"Topic {i} A", f"Topic {i} B"],
                }
                for i in range(1, 11)
            ],
        }

    def test_requires_exactly_ten_consecutive_units(self):
        self.assertTrue(validate_plan(self.plan))
        with self.assertRaisesRegex(ValueError, "exactly ten"):
            validate_plan({**self.plan, "units": self.plan["units"][:9]})

    def test_rejects_duplicate_topics_within_unit(self):
        broken = {**self.plan, "units": [dict(unit) for unit in self.plan["units"]]}
        broken["units"][2]["topics"] = ["Repeated Topic", " repeated-topic "]
        with self.assertRaisesRegex(ValueError, "duplicate topics"):
            validate_plan(broken)

    def test_rotates_one_topic_per_unit_per_successful_day(self):
        state = {"completed_days": 0}
        day_zero = build_manifest(self.plan, state, __import__("datetime").date(2026, 11, 4), "1")
        day_one = build_manifest(self.plan, {"completed_days": 1}, __import__("datetime").date(2026, 11, 5), "2")
        self.assertEqual(len(day_zero["units"]), 10)
        self.assertEqual(len(day_one["units"]), 10)
        self.assertEqual(day_zero["units"][0]["topic"], "Topic 1 A")
        self.assertEqual(day_one["units"][0]["topic"], "Topic 1 B")
        self.assertEqual(day_zero["units"][9]["topic"], "Topic 10 A")
        self.assertEqual(day_one["units"][9]["topic"], "Topic 10 B")

    def test_publication_date_is_one_day_after_generation(self):
        from datetime import date
        manifest = build_manifest(self.plan, {"completed_days": 0}, date(2026, 11, 4), "run")
        self.assertEqual(manifest["publication_date"], "2026-11-05")
        self.assertFalse(manifest["publishing_enabled"])

    def test_short_focus_rotates_across_units(self):
        from datetime import date
        manifest = build_manifest(self.plan, {"completed_days": 3}, date(2026, 11, 7), "run")
        self.assertEqual(manifest["short_focus"]["unit"], 4)


if __name__ == "__main__":
    unittest.main()
