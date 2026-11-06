import unittest
from unittest.mock import patch
from scripts.daily_production import build_manifest, process_units, validate_plan, validate_provider_credentials


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

    def test_freellmapi_route_requires_its_unified_key_not_gemini_alias(self):
        self.assertTrue(validate_provider_credentials({
            "LLM_PROVIDER": "freellmapi",
            "FREELLMAPI_API_KEY": "temporary-unified-key",
        }))
        with self.assertRaisesRegex(RuntimeError, "FREELLMAPI_API_KEY"):
            validate_provider_credentials({"LLM_PROVIDER": "freellmapi"})

    def test_direct_gemini_route_requires_gemini_api_key(self):
        self.assertTrue(validate_provider_credentials({
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "temporary-google-key",
        }))
        with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
            validate_provider_credentials({"LLM_PROVIDER": "gemini"})

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

    def test_process_units_continues_after_one_lesson_fails(self):
        units = [
            {"unit": i, "name": f"Unit {i}", "topic": f"Topic {i}"}
            for i in range(1, 11)
        ]

        def fake_process_unit(item, base_env):
            if item["unit"] == 3:
                raise RuntimeError("simulated topic-specific QA failure")
            return {
                "unit": item["unit"],
                "topic": item["topic"],
                "status": "passed_to_human_review",
            }

        with patch("scripts.daily_production.process_unit", side_effect=fake_process_unit):
            successes, failures = process_units(units, {})

        self.assertEqual(len(successes), 9)
        self.assertEqual([row["unit"] for row in failures], [3])
        self.assertIn("simulated topic-specific QA failure", failures[0]["error"])
        self.assertEqual(successes[-1]["unit"], 10)

    def test_publication_date_is_one_day_after_generation(self):
        from datetime import date
        manifest = build_manifest(self.plan, {"completed_days": 0}, date(2026, 11, 4), "run")
        self.assertEqual(manifest["publication_date"], "2026-11-05")
        self.assertFalse(manifest["publishing_enabled"])

    def test_manifest_carries_unit_specific_source_notes_path(self):
        from datetime import date
        plan = {**self.plan, "units": [dict(item) for item in self.plan["units"]]}
        plan["units"][6]["source_notes_by_topic"] = {
            "Topic 7 A": "config/source_notes/unit-07-components-of-money-supply.md"
        }
        manifest = build_manifest(plan, {"completed_days": 0}, date(2026, 11, 4), "run")
        self.assertEqual(
            manifest["units"][6]["source_notes"],
            "config/source_notes/unit-07-components-of-money-supply.md",
        )
        self.assertEqual(manifest["units"][0]["source_notes"], "")

    def test_topic_specific_source_notes_do_not_leak_to_other_rotating_topics(self):
        from datetime import date
        plan = {**self.plan, "units": [dict(item) for item in self.plan["units"]]}
        plan["units"][0]["source_notes_by_topic"] = {
            "Topic 1 A": "config/source_notes/unit-01-topic-a.md"
        }
        first = build_manifest(plan, {"completed_days": 0}, date(2026, 11, 4), "run-a")
        second = build_manifest(plan, {"completed_days": 1}, date(2026, 11, 5), "run-b")
        self.assertEqual(first["units"][0]["source_notes"], "config/source_notes/unit-01-topic-a.md")
        self.assertEqual(second["units"][0]["source_notes"], "")

    def test_rejects_source_notes_for_unknown_topic(self):
        plan = {**self.plan, "units": [dict(item) for item in self.plan["units"]]}
        plan["units"][0]["source_notes_by_topic"] = {"Not in plan": "notes.md"}
        with self.assertRaisesRegex(ValueError, "unknown topic"):
            validate_plan(plan)

    def test_rejects_non_object_topic_source_notes(self):
        plan = {**self.plan, "units": [dict(item) for item in self.plan["units"]]}
        plan["units"][0]["source_notes_by_topic"] = ["notes.md"]
        with self.assertRaisesRegex(ValueError, "must be an object"):
            validate_plan(plan)

    def test_short_focus_rotates_across_units(self):
        from datetime import date
        manifest = build_manifest(self.plan, {"completed_days": 3}, date(2026, 11, 7), "run")
        self.assertEqual(manifest["short_focus"]["unit"], 4)

    def test_resume_reuses_only_matching_complete_pass_package(self):
        import tempfile
        from pathlib import Path
        from scripts.daily_production import can_reuse_unit, _unit_artifact_paths
        item = {
            "unit": 1, "unit_id": "unit-1", "unit_name": "Unit 1",
            "topic": "Topic 1 A", "language": "Bilingual",
            "content_format": "Concept Explainer", "source_notes": "",
        }
        previous_manifest = {"units": [dict(item)]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = _unit_artifact_paths(item, root)
            for path in paths.values():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("artifact", encoding="utf-8")
            paths["gate"].write_text("**PASS — READY FOR HUMAN REVIEW**\n", encoding="utf-8")
            self.assertTrue(can_reuse_unit(item, root, previous_manifest))
            changed_topic = {**item, "topic": "Different topic"}
            self.assertFalse(can_reuse_unit(changed_topic, root, previous_manifest))
            paths["gate"].write_text("**HOLD — BLOCKED**\n", encoding="utf-8")
            self.assertFalse(can_reuse_unit(item, root, previous_manifest))

    def test_resume_rejects_incomplete_pass_package(self):
        import tempfile
        from pathlib import Path
        from scripts.daily_production import can_reuse_unit, _unit_artifact_paths
        item = {
            "unit": 6, "unit_id": "unit-6", "unit_name": "Unit 6",
            "topic": "Topic 6 A", "language": "Bilingual",
            "content_format": "Concept Explainer", "source_notes": "",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = _unit_artifact_paths(item, root)
            for key, path in paths.items():
                if key != "correction_log":
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("artifact", encoding="utf-8")
            paths["gate"].write_text("**PASS — READY FOR HUMAN REVIEW**\n", encoding="utf-8")
            self.assertFalse(can_reuse_unit(item, root, {"units": [dict(item)]}))


if __name__ == "__main__":
    unittest.main()
