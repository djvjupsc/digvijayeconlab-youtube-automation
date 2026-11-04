"""Shared handling for optional lesson source-note files."""

from pathlib import Path


def load_optional_source_notes(path_value):
    """Read source notes when a non-empty path is supplied; otherwise return ''.

    An omitted or blank path means no source notes were supplied. A non-blank
    path must exist, so a typo cannot silently downgrade source evidence.
    """
    if path_value is None:
        return ""

    path_text = str(path_value).strip()
    if not path_text:
        return ""

    path = Path(path_text)
    if not path.is_file():
        raise SystemExit(f"Source notes file not found: {path}")
    return path.read_text(encoding="utf-8")
