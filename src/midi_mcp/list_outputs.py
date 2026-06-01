"""`list_outputs` tool: enumerate folders + .mid files one level deep."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ensure_output_dir


def _file_entry(file_path: Path, rel_path: str) -> dict[str, Any]:
    stat = file_path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return {"path": rel_path, "modified": modified, "size_bytes": stat.st_size}


def list_outputs() -> dict[str, Any]:
    """List folders and ``.mid`` files in ``MIDI_MCP_OUTPUT_DIR``.

    Returns ``{folders, files}``. ``folders`` is the list of top-level
    subdirectory names. ``files`` recurses one level deep: each entry is
    ``{path, modified, size_bytes}`` with ``path`` relative to the output
    dir. Root-level files (legacy, pre-folder writes) appear with a bare
    filename. Excludes dotfiles (seed ``.log``) and non-``.mid`` files.
    """
    base = ensure_output_dir()
    folders: list[str] = []
    files: list[dict[str, Any]] = []

    for child in base.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_dir():
            folders.append(child.name)
            for grandchild in child.iterdir():
                if not grandchild.is_file():
                    continue
                if grandchild.name.startswith("."):
                    continue
                if grandchild.suffix.lower() != ".mid":
                    continue
                files.append(
                    _file_entry(grandchild, f"{child.name}/{grandchild.name}")
                )
        elif child.is_file() and child.suffix.lower() == ".mid":
            files.append(_file_entry(child, child.name))

    folders.sort()
    files.sort(key=lambda e: e["path"])
    return {"folders": folders, "files": files}
