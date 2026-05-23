"""Filename sanitization, path-like rejection, collision auto-suffix.

`resolve_output` is the only public entry. Sanitization is exposed for tests.
"""

import re
import unicodedata
from pathlib import Path

from .config import ensure_output_dir

_VALID_CHAR = re.compile(r"[a-z0-9_-]")
_WHITESPACE = re.compile(r"\s+")
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_MAX_LEN = 60


class PathRejected(ValueError):
    """Filename rejected as path-like. Carries a sanitized suggestion."""

    def __init__(self, message: str, suggestion: str):
        super().__init__(message)
        self.suggestion = suggestion


def _is_path_like(name: str) -> bool:
    return (
        "/" in name
        or "\\" in name
        or name.startswith("~")
        or bool(_DRIVE_PREFIX.match(name))
    )


def _strip_mid_extension(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".mid"):
        return name[:-4]
    if lower.endswith(".midi"):
        return name[:-5]
    return name


def sanitize_basename(name: str) -> str:
    """Sanitize to `[a-z0-9_-]`. Empty result → ``"untitled"``."""
    stem = _strip_mid_extension(name)
    decomposed = unicodedata.normalize("NFKD", stem)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = ascii_only.lower()
    spaced = _WHITESPACE.sub("_", lowered)
    kept = "".join(c for c in spaced if _VALID_CHAR.match(c))
    truncated = kept[:_MAX_LEN]
    return truncated or "untitled"


def _suggestion_for(filename: str) -> str:
    last = filename.replace("\\", "/").split("/")[-1] or filename
    last = _DRIVE_PREFIX.sub("", last).lstrip("~")
    return sanitize_basename(last)


def resolve_output(filename: str, overwrite: bool = False) -> Path:
    """Resolve a sanitized output path under ``MIDI_MCP_OUTPUT_DIR``.

    Raises ``PathRejected`` if ``filename`` looks like a path. Otherwise
    sanitizes and returns the resolved path. Auto-suffixes ``name-2.mid``,
    ``name-3.mid``, ... on collision unless ``overwrite=True``.
    """
    if not isinstance(filename, str) or not filename:
        raise ValueError("filename must be a non-empty string")
    if _is_path_like(filename):
        suggestion = _suggestion_for(filename)
        raise PathRejected(
            f"path-like input rejected: {filename!r}. Provide a bare filename "
            f"(no '/', '\\', '~', or drive prefix). Suggestion: {suggestion!r}",
            suggestion,
        )
    stem = sanitize_basename(filename)
    base_dir = ensure_output_dir()
    candidate = base_dir / f"{stem}.mid"
    if overwrite or not candidate.exists():
        return candidate
    n = 2
    while True:
        candidate = base_dir / f"{stem}-{n}.mid"
        if not candidate.exists():
            return candidate
        n += 1
