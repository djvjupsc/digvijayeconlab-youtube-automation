import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.topic_queue import claim, finish, load_queue, recover_stale_claims, save_queue


class TopicQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.queue_path = Path(self.temp_dir.name) / "topic_queue.json"
        self.data = {
            "version": 1,
            "items": [
                {
                    "id": "topic-one",
                    "topic": "Elasticity of Demand",
                    "language": "Bilingual",
                    "content_format": "Concept Explainer",
                    "source_notes": "",
                    "status": "pending",
                },
                {
                    "id": "topic-two",
                    "topic": "Consumer Equilibrium",
                    "language": "Hindi",
                    "content_format": "MCQ Set",
                    "source_notes": "Approved source notes.",
                    "status": "pending",
                },
            ],
        }
        save_queue(self.queue_path, self.data)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_load_queue_accepts_unique_topics(self):
        self.assertEqual(len(load_queue(self.queue_path)["items"]), 2)

    def test_rejects_duplicate_ids(self):
        data = json.loads(self.queue_path.read_text(encoding="utf-8"))
        data["items"][1]["id"] = data["items"][0]["id"]
        save_queue(self.queue_path, data)
        with self.assertRaisesRegex(ValueError, "Duplicate queue id"):
            load_queue(self.queue_path)

    def test_rejects_duplicate_topics_ignoring_case_and_punctuation(self):
        data = json.loads(self.queue_path.read_text(encoding="utf-8"))
        data["items"][1]["topic"] = "ELASTICITY-of-demand!"
        save_queue(self.queue_path, data)
        with self.assertRaisesRegex(ValueError, "Duplicate topic"):
            load_queue(self.queue_path)

    def test_claims_first_pending_item_and_writes_github_outputs(self):
        output_path = Path(self.temp_dir.name) / "github_output.txt"
        args = type("Args", (), {
            "queue": str(self.queue_path),
            "run_id": "12345",
            "github_output": str(output_path),
        })()
        self.assertEqual(claim(args), 0)
        claimed = load_queue(self.queue_path)["items"][0]
        self.assertEqual(claimed["status"], "processing")
        self.assertEqual(claimed["claimed_by"], "12345")
        outputs = output_path.read_text(encoding="utf-8")
        self.assertIn("claimed", outputs)
        self.assertIn("Elasticity of Demand", outputs)

    def test_sequential_runs_claim_different_topics(self):
        args = type("Args", (), {
            "queue": str(self.queue_path),
            "run_id": "111",
            "github_output": "",
        })()
        claim(args)
        args.run_id = "222"
        claim(args)
        items = load_queue(self.queue_path)["items"]
        self.assertEqual(items[0]["claimed_by"], "111")
        self.assertEqual(items[1]["claimed_by"], "222")
        self.assertNotEqual(items[0]["id"], items[1]["id"])

    def test_finish_marks_only_items_owned_by_run(self):
        claim_args = type("Args", (), {
            "queue": str(self.queue_path),
            "run_id": "555",
            "github_output": "",
        })()
        claim(claim_args)
        finish_args = type("Args", (), {
            "queue": str(self.queue_path),
            "run_id": "555",
            "job_status": "success",
        })()
        self.assertEqual(finish(finish_args), 0)
        item = load_queue(self.queue_path)["items"][0]
        self.assertEqual(item["status"], "completed")
        self.assertEqual(item["last_run_id"], "555")
        self.assertNotIn("claimed_by", item)

    def test_failed_item_is_not_silently_requeued(self):
        claim_args = type("Args", (), {
            "queue": str(self.queue_path),
            "run_id": "777",
            "github_output": "",
        })()
        claim(claim_args)
        finish_args = type("Args", (), {
            "queue": str(self.queue_path),
            "run_id": "777",
            "job_status": "failure",
        })()
        finish(finish_args)
        self.assertEqual(load_queue(self.queue_path)["items"][0]["status"], "failed")

    def test_marks_stale_processing_claims_without_requeueing(self):
        data = load_queue(self.queue_path)
        data["items"][0]["status"] = "processing"
        data["items"][0]["claimed_by"] = "old-run"
        data["items"][0]["claimed_at"] = (
            datetime.now(timezone.utc) - timedelta(hours=7)
        ).isoformat()
        data["items"][1]["status"] = "processing"
        data["items"][1]["claimed_by"] = "recent-run"
        data["items"][1]["claimed_at"] = datetime.now(timezone.utc).isoformat()
        recovered = recover_stale_claims(data)
        self.assertEqual(recovered, ["topic-one"])
        self.assertEqual(data["items"][0]["status"], "stale")
        self.assertEqual(data["items"][1]["status"], "processing")

    def test_rejects_invalid_format(self):
        data = json.loads(self.queue_path.read_text(encoding="utf-8"))
        data["items"][0]["content_format"] = "Instant Video"
        save_queue(self.queue_path, data)
        with self.assertRaisesRegex(ValueError, "unsupported content format"):
            load_queue(self.queue_path)


    def test_stale_item_is_not_selected_for_generation(self):
        data = load_queue(self.queue_path)
        data["items"][0]["status"] = "stale"
        data["items"][1]["status"] = "completed"
        save_queue(self.queue_path, data)
        output_path = Path(self.temp_dir.name) / "github_output.txt"
        args = type("Args", (), {
            "queue": str(self.queue_path),
            "run_id": "999",
            "github_output": str(output_path),
        })()
        self.assertEqual(claim(args), 0)
        outputs = output_path.read_text(encoding="utf-8")
        self.assertIn("claimed", outputs)
        self.assertIn("false", outputs)
        self.assertEqual(load_queue(self.queue_path)["items"][0]["status"], "stale")


if __name__ == "__main__":
    unittest.main()
