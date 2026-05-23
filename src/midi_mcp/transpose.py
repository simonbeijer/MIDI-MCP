"""`transpose` tool: shift pitches on a notes list. Clamps out-of-range."""

import warnings
from typing import Any


def transpose(notes: list[dict[str, Any]], semitones: int) -> list[dict[str, Any]]:
    """Return a new notes list with each pitch shifted by ``semitones``.

    Pitches outside ``[0, 127]`` after shift are clamped and a warning is
    issued. Other note fields are preserved.
    """
    if not isinstance(notes, list):
        raise ValueError("notes must be a list")
    shift = int(semitones)
    out: list[dict[str, Any]] = []
    clamped = 0
    for n in notes:
        new_pitch = int(n["pitch"]) + shift
        if new_pitch < 0:
            new_pitch = 0
            clamped += 1
        elif new_pitch > 127:
            new_pitch = 127
            clamped += 1
        out.append({**n, "pitch": new_pitch})
    if clamped:
        warnings.warn(
            f"transpose: {clamped} note(s) clamped to [0, 127] after shift of {shift}",
            stacklevel=2,
        )
    return out
