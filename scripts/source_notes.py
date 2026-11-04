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



def resolve_source_notes_argument(value):
    """Resolve a source-notes argument as a file path or preserve legacy inline text."""
    if value is None:
        return ""
    raw = str(value)
    if not raw.strip():
        return ""
    path = Path(raw.strip())
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        # Long inline source notes may not be valid filesystem paths.
        pass
    return raw
