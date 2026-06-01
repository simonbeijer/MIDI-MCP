"""`write_midi` tool: validate, sanitize path, delegate to midi_io.

This module MUST NOT import `random` — snapshot stability invariant.
"""

from typing import Any

import mido

from .midi_io import write_midi_file
from .paths import resolve_output


def _validate_key(key: str, warnings: list[str]) -> str:
    try:
        mido.MetaMessage("key_signature", key=key)
        return key
    except (ValueError, KeyError) as exc:
        warnings.append(f"invalid key {key!r} ({exc}); defaulting to 'C'")
        return "C"


def _validate_time_sig(time_sig: Any, warnings: list[str]) -> tuple[int, int]:
    try:
        num, den = int(time_sig[0]), int(time_sig[1])
    except (TypeError, ValueError, IndexError):
        warnings.append(f"invalid time_sig {time_sig!r}; defaulting to [4, 4]")
        return (4, 4)
    return (num, den)


def write_midi(
    tracks: list[dict[str, Any]],
    tempo: float,
    time_sig: list[int],
    key: str,
    filename: str,
    overwrite: bool = False,
    project: str | None = None,
) -> dict[str, Any]:
    """Render ``tracks`` to a .mid under ``MIDI_MCP_OUTPUT_DIR``.

    The file lands in ``<output_dir>/<project>/`` if ``project`` is given,
    otherwise in ``<output_dir>/<YYYY-MM-DD>/`` (today's date).

    Returns ``{path, warnings, summary, duration_seconds}``.
    Raises ``PathRejected`` on path-like input or ``ValueError`` on
    missing/invalid ``tracks``/``tempo``.
    """
    if not isinstance(tracks, list):
        raise ValueError("tracks must be a list")
    if tempo is None or float(tempo) <= 0:
        raise ValueError(f"tempo must be > 0, got {tempo!r}")

    warnings: list[str] = []
    sig = _validate_time_sig(time_sig, warnings)
    key_validated = _validate_key(key, warnings)

    path = resolve_output(filename, overwrite=overwrite, project=project)
    if path.name != f"{filename}.mid" and path.name != filename:
        warnings.append(f"filename sanitized: {filename!r} → {path.name!r}")

    duration_seconds = write_midi_file(
        path=path,
        tracks=tracks,
        tempo=float(tempo),
        time_sig=sig,
        key=key_validated,
    )

    note_count = sum(len(t.get("notes", [])) for t in tracks)
    summary = (
        f"wrote {path.name}: {len(tracks)} track(s), {note_count} note(s), "
        f"{float(tempo):g} bpm, {sig[0]}/{sig[1]}, key {key_validated}, "
        f"{duration_seconds:.2f}s"
    )
    return {
        "path": str(path),
        "warnings": warnings,
        "summary": summary,
        "duration_seconds": duration_seconds,
    }
