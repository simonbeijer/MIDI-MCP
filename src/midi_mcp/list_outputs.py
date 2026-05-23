"""`list_outputs` tool: enumerate .mid files in the output dir."""

from datetime import datetime, timezone
from typing import Any

from .config import ensure_output_dir


def list_outputs() -> list[dict[str, Any]]:
    """List ``.mid`` files in ``MIDI_MCP_OUTPUT_DIR``.

    Excludes dotfiles and any non-``.mid`` files (including the seed ``.log``).
    Each entry: ``{filename, modified, size_bytes}``. ``modified`` is an
    ISO-8601 UTC timestamp.
    """
    base = ensure_output_dir()
    entries: list[dict[str, Any]] = []
    for child in base.iterdir():
        if not child.is_file():
            continue
        if child.name.startswith("."):
            continue
        if child.suffix.lower() != ".mid":
            continue
        stat = child.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        entries.append(
            {
                "filename": child.name,
                "modified": modified,
                "size_bytes": stat.st_size,
            }
        )
    entries.sort(key=lambda e: e["filename"])
    return entries
