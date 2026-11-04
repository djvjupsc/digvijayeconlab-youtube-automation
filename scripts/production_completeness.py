"""Validate that the daily artifact contains every expected draft deliverable.

A complete draft pack is not publication approval. Voice, academic and copyright
checks remain explicit, and private/public YouTube uploads are controlled elsewhere.
"""
import argparse
import json
from pathlib import Path

from PIL import Image


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inspect(root, publication_date):
    root = Path(root)
    required = [
        root / "output" / "quality_checks" / "daily-batch-status.md",
        root / "output" / "community" / f"{publication_date}-community-post.md",
        root / "output" / "seo" / f"{publication_date}-seo-metadata.json",
        root / "output" / "seo" / f"{publication_date}-seo-metadata.md",
        root / "output" / "shorts" / f"{publication_date}-short.json",
        root / "output" / "shorts" / f"{publication_date}-short-storyboard.md",
        root / "output" / "shorts" / f"{publication_date}-short-render.json",
        root / "output" / "shorts" / f"{publication_date}-digvijayeconlab-short.mp4",
        root / "output" / "shorts" / f"{publication_date}-prepublish-audit.json",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.is_file() or path.stat().st_size == 0]

    lesson_status_path = root / "output" / "quality_checks" / "daily-batch-status.md"
    lesson_status = lesson_status_path.read_text(encoding="utf-8") if lesson_status_path.is_file() else ""
    if "- Lessons passed to human review: 10 / 10" not in lesson_status or "- Lessons blocked: 0 / 10" not in lesson_status:
        missing.append("daily-batch-status.md (must confirm 10/10 lesson gates passed and zero blocked)")

    thumbnail_dir = root / "output" / "thumbnails"
    thumbnail_files = [thumbnail_dir / f"unit-{unit:02d}-thumbnail.jpg" for unit in range(1, 11)]
    thumbnail_dimensions = {}
    for path in thumbnail_files:
        if not path.is_file() or path.stat().st_size == 0:
            missing.append(str(path.relative_to(root)))
            continue
        try:
            with Image.open(path) as image:
                thumbnail_dimensions[path.name] = list(image.size)
                if image.size != (1280, 720):
                    missing.append(f"{path.relative_to(root)} (expected 1280x720, got {image.size})")
        except Exception as exc:
            missing.append(f"{path.relative_to(root)} (unreadable image: {exc})")

    longform_report_path = root / "output" / "longform" / f"{publication_date}-longform-render.json"
    longform_report = None
    longform_video = None
    if not longform_report_path.is_file():
        missing.append(str(longform_report_path.relative_to(root)))
    else:
        longform_report = load_json(longform_report_path)
        candidate = Path(longform_report.get("video", ""))
        if not candidate.is_absolute():
            candidate = root / candidate
        if not candidate.is_file() or candidate.stat().st_size == 0:
            missing.append(f"long-form video missing: {candidate}")
        else:
            longform_video = str(candidate.relative_to(root))

    audit_path = root / "output" / "shorts" / f"{publication_date}-prepublish-audit.json"
    audit = load_json(audit_path) if audit_path.is_file() else {}
    short_render_path = root / "output" / "shorts" / f"{publication_date}-short-render.json"
    short_render = load_json(short_render_path) if short_render_path.is_file() else {}
    seo = load_json(root / "output" / "seo" / f"{publication_date}-seo-metadata.json") if (root / "output" / "seo" / f"{publication_date}-seo-metadata.json").is_file() else []

    if len(seo) != 10:
        missing.append(f"SEO metadata must contain 10 records (found {len(seo)})")

    voice_is_owner_authorized = bool(short_render.get("voice_clone_used")) and bool(longform_report and longform_report.get("voice_clone_used"))
    short_audit_passed = audit.get("status") == "pass"
    longform_audit_status = (longform_report or {}).get("audit_status", "missing")

    report = {
        "status": "incomplete" if missing else "complete_draft",
        "publication_date": publication_date,
        "deliverables": {
            "lesson_packages": "10/10 PASS — READY FOR HUMAN REVIEW" if "- Lessons passed to human review: 10 / 10" in lesson_status and "- Lessons blocked: 0 / 10" in lesson_status else "incomplete or blocked",
            "thumbnails": {"count": len(thumbnail_dimensions), "dimensions": thumbnail_dimensions},
            "seo_records": len(seo),
            "community_post": "present" if required[0].is_file() else "missing",
            "short_video": str(required[6].relative_to(root)) if required[6].is_file() else None,
            "longform_video": longform_video,
        },
        "quality_and_release": {
            "short_prepublication_audit": audit.get("status", "missing"),
            "longform_audit_status": longform_audit_status,
            "owner_authorized_voice_used_for_both_videos": voice_is_owner_authorized,
            "publication_approved": False,
            "youtube_uploads_authorized": False,
            "human_review_required": True,
            "copyright_and_ai_disclosure_review_required": True,
        },
        "missing_or_invalid_deliverables": missing,
        "warnings": [
            "A complete draft package is not academic certification or publication approval.",
            "A placeholder/eSpeak narration preview is not upload-eligible.",
            "A blocked pre-publication audit keeps the Short in draft-only status.",
            "Unresolved [VERIFY] markers remain in lessons and are never removed automatically.",
        ],
    }
    output = root / "output" / "production-completeness.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return not missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", default="output/daily_manifest.json")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    manifest = load_json(Path(args.root) / args.manifest)
    raise SystemExit(0 if inspect(args.root, manifest["publication_date"]) else 1)


if __name__ == "__main__":
    main()
