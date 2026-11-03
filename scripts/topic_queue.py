"""Claim and finalize one unique topic from the controlled content queue."""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ALLOWED_LANGUAGES = {"Hindi", "English", "Bilingual"}
ALLOWED_FORMATS = {
    "Concept Explainer",
    "MCQ Set",
    "Previous-Year-Question Analysis",
}
ALLOWED_STATUSES = {"pending", "processing", "completed", "failed", "stale"}
STALE_CLAIM_HOURS = 6


def utc_now():
    return datetime.now(timezone.utc)


def iso_now():
    return utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_topic(topic):
    return re.sub(r"[^a-z0-9]+", "", topic.casefold())


def load_queue(path):
    queue_path = Path(path)
    try:
        data = json.loads(queue_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Topic queue file not found: {queue_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Topic queue is not valid JSON: {exc}") from exc

    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Topic queue must be a version 1 JSON object.")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("Topic queue 'items' must be an array.")

    seen_ids = set()
    seen_topics = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"Queue item {index + 1} must be an object.")
        topic_id = item.get("id")
        topic = item.get("topic")
        if not isinstance(topic_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,79}", topic_id):
            raise ValueError(f"Queue item {index + 1} has an invalid id.")
        if topic_id in seen_ids:
            raise ValueError(f"Duplicate queue id: {topic_id}")
        seen_ids.add(topic_id)
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError(f"Queue item {topic_id} must have a non-empty topic.")
        normalized = normalize_topic(topic)
        if normalized in seen_topics:
            raise ValueError(f"Duplicate topic detected (case/punctuation insensitive): {topic}")
        seen_topics.add(normalized)

        if item.get("language") not in ALLOWED_LANGUAGES:
            raise ValueError(f"Queue item {topic_id} has an unsupported language.")
        if item.get("content_format") not in ALLOWED_FORMATS:
            raise ValueError(f"Queue item {topic_id} has an unsupported content format.")
        if not isinstance(item.get("source_notes", ""), str):
            raise ValueError(f"Queue item {topic_id}: source_notes must be a string.")
        if item.get("status", "pending") not in ALLOWED_STATUSES:
            raise ValueError(f"Queue item {topic_id} has an unsupported status.")
    return data


def save_queue(path, data):
    queue_path = Path(path)
    temporary = queue_path.with_suffix(queue_path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(queue_path)


def recover_stale_claims(data, now=None):
    now = now or utc_now()
    recovered = []
    for item in data["items"]:
        if item.get("status") != "processing":
            continue
        claimed_at = item.get("claimed_at")
        try:
            parsed = datetime.fromisoformat(claimed_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            parsed = now - timedelta(hours=STALE_CLAIM_HOURS + 1)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if now - parsed > timedelta(hours=STALE_CLAIM_HOURS):
            item["status"] = "stale"
            item.pop("claimed_by", None)
            item.pop("claimed_at", None)
            item["recovered_at"] = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
            recovered.append(item["id"])
    return recovered


def write_github_outputs(path, values):
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            delimiter = "GHAA_" + uuid.uuid4().hex
            while delimiter in str(value):
                delimiter = "GHAA_" + uuid.uuid4().hex
            stream.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


def claim(args):
    data = load_queue(args.queue)
    recovered = recover_stale_claims(data)
    item = next(
        (entry for entry in data["items"] if entry.get("status", "pending") == "pending"),
        None,
    )
    if item is None:
        if recovered:
            save_queue(args.queue, data)
        values = {
            "claimed": "false",
            "queue_id": "",
            "topic": "",
            "language": "",
            "content_format": "",
            "source_notes": "",
        }
        write_github_outputs(args.github_output, values)
        print("No pending topic is available. No Gemini API call will be made.")
        return 0

    item["status"] = "processing"
    item["claimed_by"] = str(args.run_id)
    item["claimed_at"] = iso_now()
    save_queue(args.queue, data)
    values = {
        "claimed": "true",
        "queue_id": item["id"],
        "topic": item["topic"],
        "language": item["language"],
        "content_format": item["content_format"],
        "source_notes": item.get("source_notes", ""),
    }
    write_github_outputs(args.github_output, values)
    print(f"Claimed queue item {item['id']}: {item['topic']}")
    if recovered:
        print("Marked stale processing claim(s) for manual review (not automatically retried): " + ", ".join(recovered))
    return 0


def finish(args):
    data = load_queue(args.queue)
    matching = next(
        (
            item for item in data["items"]
            if item.get("status") == "processing"
            and item.get("claimed_by") == str(args.run_id)
        ),
        None,
    )
    if matching is None:
        print(f"No processing queue item is owned by run {args.run_id}; leaving queue unchanged.")
        return 0

    final_status = "completed" if args.job_status == "success" else "failed"
    matching["status"] = final_status
    matching["finished_at"] = iso_now()
    matching["last_run_id"] = str(args.run_id)
    matching.pop("claimed_by", None)
    matching.pop("claimed_at", None)
    save_queue(args.queue, data)
    print(f"Queue item {matching['id']} marked {final_status}.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Manage the controlled DigvijayEconLab topic queue."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--queue", default="config/topic_queue.json")

    claim_parser = subparsers.add_parser("claim")
    claim_parser.add_argument("--queue", default="config/topic_queue.json")
    claim_parser.add_argument("--run-id", required=True)
    claim_parser.add_argument("--github-output", default="")

    finish_parser = subparsers.add_parser("finish")
    finish_parser.add_argument("--queue", default="config/topic_queue.json")
    finish_parser.add_argument("--run-id", required=True)
    finish_parser.add_argument(
        "--job-status", choices=("success", "failure", "cancelled"), required=True
    )

    args = parser.parse_args()
    try:
        data = load_queue(args.queue)
        if args.command == "validate":
            print(f"Topic queue valid: {len(data['items'])} unique item(s).")
            return 0
        if args.command == "claim":
            return claim(args)
        if args.command == "finish":
            return finish(args)
    except ValueError as exc:
        print(f"QUEUE ERROR: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
