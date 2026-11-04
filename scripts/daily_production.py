"""Daily ten-unit production pack orchestration and idempotent state management."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "config/unit_content_plan.json"
STATE_PATH = ROOT / "config/daily_production_state.json"
MANIFEST_PATH = ROOT / "output/daily_manifest.json"
TZ = ZoneInfo("Asia/Kolkata")


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Required file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def validate_plan(plan):
    if plan.get("version") != 1 or plan.get("timezone") != "Asia/Kolkata":
        raise ValueError("Plan version/timezone is not supported.")
    units = plan.get("units")
    if not isinstance(units, list) or len(units) != 10:
        raise ValueError("The daily plan must contain exactly ten units.")
    seen_ids, seen_playlist_titles = set(), set()
    for expected, unit in enumerate(units, start=1):
        if unit.get("unit") != expected:
            raise ValueError("Units must be numbered consecutively from 1 to 10.")
        if not unit.get("id") or unit["id"] in seen_ids:
            raise ValueError(f"Missing or duplicate unit id for unit {expected}.")
        seen_ids.add(unit["id"])
        if not unit.get("name") or not unit.get("playlist_title") or not unit.get("playlist_description"):
            raise ValueError(f"Unit {expected} is missing playlist metadata.")
        if unit["playlist_title"] in seen_playlist_titles:
            raise ValueError(f"Duplicate playlist title: {unit['playlist_title']}")
        seen_playlist_titles.add(unit["playlist_title"])
        topics = unit.get("topics")
        if not isinstance(topics, list) or not topics or any(not isinstance(t, str) or not t.strip() for t in topics):
            raise ValueError(f"Unit {expected} must contain non-empty topics.")
        normalized = [re.sub(r"[^a-z0-9]+", "", topic.casefold()) for topic in topics]
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"Unit {expected} contains duplicate topics.")
    return True


def build_manifest(plan, state, run_date, run_id):
    day_index = int(state.get("completed_days", 0))
    publish_date = run_date + timedelta(days=1)
    unit_items = []
    for unit in plan["units"]:
        topic_index = day_index % len(unit["topics"])
        unit_items.append({
            "unit": unit["unit"],
            "unit_id": unit["id"],
            "unit_name": unit["name"],
            "playlist_title": unit["playlist_title"],
            "topic_index": topic_index,
            "topic": unit["topics"][topic_index],
            "language": "Bilingual",
            "content_format": "Concept Explainer",
            "source_notes": unit.get("source_notes", ""),
        })
    focus = unit_items[day_index % len(unit_items)]
    return {
        "version": 1,
        "run_id": str(run_id),
        "run_date": run_date.isoformat(),
        "publication_date": publish_date.isoformat(),
        "day_index": day_index,
        "timezone": "Asia/Kolkata",
        "brand": "DigvijayEconLab",
        "target": {"full_lesson_scripts": 10, "shorts_videos": 1, "community_posts": 1},
        "units": unit_items,
        "short_focus": focus,
        "publishing_enabled": False,
    }


def prepare(args):
    plan = load_json(args.plan)
    validate_plan(plan)
    state = load_json(args.state)
    now = datetime.now(TZ)
    run_date = now.date()
    run_id = str(args.run_id)

    active_status = state.get("last_status")
    last_claimed_date = state.get("last_claimed_date")
    if active_status == "processing" and state.get("active_run_id"):
        if last_claimed_date == run_date.isoformat():
            print("A daily production pack is already running or has already claimed today's slot.")
            return {"claimed": "false", "reason": "already_claimed_today"}
        state["last_status"] = "stale"
        state["active_run_id"] = None
        state["stale_detected_at"] = now.isoformat()
        print("An earlier daily pack was interrupted. Its partial draft is retained as history; the same uncompleted rotation slot will be attempted again.")

    if last_claimed_date == run_date.isoformat():
        if active_status == "completed":
            print("Today's production pack is already complete; skipping duplicate generation.")
            return {"claimed": "false", "reason": "completed_today"}
        if active_status == "failed" and not args.retry_failed:
            print("Today's production pack failed earlier. Set retry_failed=true after checking the failed run.")
            return {"claimed": "false", "reason": "failed_today"}
        if active_status == "failed" and args.retry_failed:
            print("Manual retry of today's failed production pack authorized by workflow input.")

    manifest = build_manifest(plan, state, run_date, run_id)
    state["last_claimed_date"] = run_date.isoformat()
    state["last_status"] = "processing"
    state["active_run_id"] = run_id
    state["active_date"] = run_date.isoformat()
    state["active_day_index"] = manifest["day_index"]
    save_json(args.state, state)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    save_json(MANIFEST_PATH, manifest)

    outputs = {
        "claimed": "true",
        "run_date": manifest["run_date"],
        "publication_date": manifest["publication_date"],
        "day_index": str(manifest["day_index"]),
    }
    if args.github_output:
        with Path(args.github_output).open("a", encoding="utf-8") as stream:
            for key, value in outputs.items():
                stream.write(f"{key}={value}\n")
    print(f"Claimed daily production pack for publication date {manifest['publication_date']}.")
    for item in manifest["units"]:
        print(f"Unit {item['unit']:02d}: {item['topic']}")
    print(f"Short focus: Unit {manifest['short_focus']['unit']:02d} — {manifest['short_focus']['topic']}")
    return outputs


def _run(command, env, label):
    print(f"\n===== {label} =====", flush=True)
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    if label.startswith(("Generate Unit", "Review original Unit", "Correct Unit", "Review corrected Unit", "Generate the daily Short")):
        time.sleep(4.0)  # Keep sequential Gemini calls near 15 requests/minute or slower.


def process_unit(item, base_env):
    """Generate, correct, re-review and gate one lesson independently."""
    unit_prefix = f"unit-{item['unit']:02d}"
    env = base_env.copy()
    env.update({
        "SCRIPT_UNIT": f"Unit {item['unit']}: {item['unit_name']}",
        "SCRIPT_FILENAME_PREFIX": unit_prefix,
        "SCRIPT_TOPIC": item["topic"],
        "SCRIPT_LANGUAGE": item["language"],
        "SCRIPT_FORMAT": item["content_format"],
        "SCRIPT_SOURCE_NOTES": item.get("source_notes", ""),
    })
    slug = re.sub(
        r"[^a-z0-9]+", "-", f"{unit_prefix} {item['topic']}".strip().lower()
    ).strip("-")[:60].strip("-") or "lesson"
    script_path = ROOT / "output/scripts" / f"{slug}.md"
    review_path = ROOT / "output/reviews" / f"{script_path.stem}-quality-review.md"
    corrected_path = ROOT / "output/corrected_scripts" / script_path.name
    deterministic_path = ROOT / "output/quality_checks" / f"{script_path.stem}-corrected-deterministic-check.md"
    gate_path = ROOT / "output/reviews" / f"{script_path.stem}-academic-gate-decision.md"
    correction_log_path = ROOT / "output/corrections" / f"{script_path.stem}-correction-log.md"

    _run(
        [sys.executable, "scripts/generate_script.py", item["topic"], item["language"], item["content_format"], item.get("source_notes", "")],
        env, f"Generate Unit {item['unit']} — {item['topic']}",
    )
    _run(
        [sys.executable, "scripts/review_script.py", str(script_path), item.get("source_notes", "")],
        {**env, "REVIEW_STAGE": "original"},
        f"Review original Unit {item['unit']} script",
    )
    if not review_path.is_file():
        raise RuntimeError(f"Original review missing for Unit {item['unit']}: {review_path}")
    shutil.copy2(review_path, ROOT / "output/reviews" / f"{script_path.stem}-original-quality-review.md")

    _run(
        [sys.executable, "scripts/correct_script.py", str(script_path), str(review_path), item.get("source_notes", "")],
        env, f"Correct Unit {item['unit']} script",
    )
    _run(
        [sys.executable, "scripts/review_script.py", str(corrected_path), item.get("source_notes", "")],
        {**env, "REVIEW_STAGE": "corrected"},
        f"Review corrected Unit {item['unit']} script",
    )
    if not script_path.is_file() or not corrected_path.is_file():
        raise RuntimeError(f"Original or corrected script missing for Unit {item['unit']}.")
    if not deterministic_path.is_file():
        raise RuntimeError(f"Corrected deterministic report missing for Unit {item['unit']}: {deterministic_path}")

    _run(
        [
            sys.executable, "scripts/academic_gate.py",
            str(review_path), str(deterministic_path), str(corrected_path),
            "--correction-log", str(correction_log_path),
            "--output", str(gate_path),
        ],
        env, f"Enforce academic gate Unit {item['unit']}",
    )
    if not gate_path.is_file():
        raise RuntimeError(f"Academic gate decision missing for Unit {item['unit']}: {gate_path}")
    time.sleep(1.0)
    return {
        "unit": item["unit"],
        "topic": item["topic"],
        "status": "passed_to_human_review",
        "gate_report": str(gate_path.relative_to(ROOT)),
    }


def process_units(units, base_env):
    """Run every unit despite individual failures and return pass/fail records."""
    successes, failures = [], []
    for item in units:
        try:
            successes.append(process_unit(item, base_env))
        except Exception as exc:
            failure = {
                "unit": item.get("unit"),
                "topic": item.get("topic", item.get("name", "Unknown topic")),
                "status": "blocked",
                "error": f"{type(exc).__name__}: {exc}",
            }
            failures.append(failure)
            print(
                f"UNIT {item.get('unit', '?')} BLOCKED — {failure['topic']}: {failure['error']}",
                flush=True,
            )
            print("Continuing with the remaining independent lesson topics.", flush=True)
    return successes, failures


def process(args):
    manifest = load_json(args.manifest)
    if len(manifest.get("units", [])) != 10:
        raise ValueError("Daily manifest must contain exactly ten unit lessons.")
    output_dirs = [
        ROOT / "output/scripts",
        ROOT / "output/reviews",
        ROOT / "output/corrected_scripts",
        ROOT / "output/corrections",
        ROOT / "output/quality_checks",
        ROOT / "output/seo",
    ]
    for directory in output_dirs:
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)

    base_env = os.environ.copy()
    if not base_env.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is missing from GitHub Actions secrets.")
    base_env.setdefault("GEMINI_MODEL", "gemini-3.5-flash-lite")

    successes, failures = process_units(manifest["units"], base_env)
    manifest["lesson_quality"] = {
        "passed_to_human_review": successes,
        "blocked_lessons": failures,
        "all_ten_passed_automated_gates": len(successes) == 10 and not failures,
        "publication_approval": False,
    }
    save_json(args.manifest, manifest)

    report_lines = [
        "# Daily Ten-Unit Lesson Quality Gate",
        "",
        "> Automated workflow eligibility for human review only. A pass is not academic certification or publishing approval.",
        "",
        f"- Lessons passed to human review: {len(successes)} / 10",
        f"- Lessons blocked: {len(failures)} / 10",
        "",
        "## Passed lessons",
        "",
    ]
    report_lines.extend(
        f"- Unit {row['unit']}: {row['topic']} — PASS (human review required)"
        for row in successes
    )
    if not successes:
        report_lines.append("- None.")
    report_lines += ["", "## Blocked lessons", ""]
    report_lines.extend(
        f"- Unit {row['unit']}: {row['topic']} — BLOCKED: {row['error']}"
        for row in failures
    )
    if not failures:
        report_lines.append("- None.")
    report_lines += [
        "",
        "## Decision",
        "",
        "**ALL TEN PASSED — READY FOR HUMAN REVIEW**" if len(successes) == 10 and not failures
        else "**BATCH INCOMPLETE — NO FEATURED VIDEO OR SHORT RENDER WILL START**",
        "",
        "All passed lesson scripts and gate reports are retained in the workflow artifact. Failed lessons do not prevent other unit topics from being generated and checked. The batch remains failed until all ten required lessons pass.",
        "",
    ]
    report_path = ROOT / "output/quality_checks" / "daily-batch-status.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    if failures or len(successes) != 10:
        raise RuntimeError(
            f"Daily lesson batch incomplete: {len(successes)}/10 passed automated gates; "
            f"{len(failures)} lesson(s) blocked. Successful outputs and failure details were retained."
        )

    promo_env = base_env.copy()
    promo_env["DAILY_MANIFEST"] = str(Path(args.manifest))
    _run(
        [sys.executable, "scripts/generate_daily_assets.py", str(Path(args.manifest))],
        promo_env,
        "Generate the daily Short storyboard and Community post",
    )
    _run(
        [sys.executable, "scripts/render_short_video.py", str(Path(args.manifest))],
        promo_env,
        "Render the daily vertical Short draft video",
    )
    print("\nDaily production pack complete: 10 individually gated lesson packages, one Short MP4 draft, and one Community post draft.")


def finish(args):
    state = load_json(args.state)
    if str(state.get("active_run_id")) != str(args.run_id) or state.get("last_status") != "processing":
        print("This run does not own the active production claim; state was left unchanged.")
        return 0
    if args.job_status == "success":
        state["completed_days"] = int(state.get("completed_days", 0)) + 1
        state["last_completed_date"] = state.get("active_date")
        state["last_status"] = "completed"
        print(f"Daily production pack completed. Rotation advanced to day index {state['completed_days']}.")
    else:
        state["last_status"] = "failed"
        print("Daily production pack failed. Rotation index was not advanced; inspect the artifact before retrying.")
    state["active_run_id"] = None
    state["active_date"] = None
    state["active_day_index"] = None
    save_json(args.state, state)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Daily ten-unit DigvijayEconLab production workflow.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--plan", default=str(PLAN_PATH))
    validate_parser.add_argument("--state", default=str(STATE_PATH))

    prepare_parser = sub.add_parser("prepare")
    prepare_parser.add_argument("--plan", default=str(PLAN_PATH))
    prepare_parser.add_argument("--state", default=str(STATE_PATH))
    prepare_parser.add_argument("--run-id", required=True)
    prepare_parser.add_argument("--github-output", default="")
    prepare_parser.add_argument("--retry-failed", action="store_true")

    process_parser = sub.add_parser("process")
    process_parser.add_argument("--manifest", default=str(MANIFEST_PATH))

    finish_parser = sub.add_parser("finish")
    finish_parser.add_argument("--state", default=str(STATE_PATH))
    finish_parser.add_argument("--run-id", required=True)
    finish_parser.add_argument("--job-status", choices=("success", "failure", "cancelled"), required=True)

    args = parser.parse_args()
    if args.command == "validate":
        validate_plan(load_json(args.plan))
        print("Daily plan valid: exactly ten units, unique playlist titles, and unique topics per unit.")
        return 0
    if args.command == "prepare":
        prepare(args)
        return 0
    if args.command == "process":
        process(args)
        return 0
    if args.command == "finish":
        return finish(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
