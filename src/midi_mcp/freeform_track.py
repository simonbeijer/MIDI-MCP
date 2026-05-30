"""`freeform_track` helper: validate caller-composed notes; no theory applied.

The escape hatch for anything outside ``chord_track``'s rule-bound
voicing palette. Bass lines, melodies, leads, counterpoint — whatever
the caller hands in is what gets written. The helper does no music
theory and adds no randomness: it validates note shape and ranges,
applies ``channel`` as a default when individual notes omit it, and
sorts by ``start`` so the output is stable regardless of input order.

Determinism trade-off: helpers + ``write_midi`` remain bit-deterministic
end-to-end, but ``freeform_track`` output is whatever the caller
provided — not server-reproducible from a seed. The seed ``.log`` no
longer tells the full story for tracks built through this helper.
"""

from typing import Any


def _check_int(value: Any, name: str, lo: int, hi: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            f"{name} must be int, got {type(value).__name__}: {value!r}"
        )
    if value < lo or value > hi:
        raise ValueError(f"{name} must be in [{lo}, {hi}], got {value}")
    return value


def _check_note(n: Any, index: int, default_channel: int) -> dict[str, Any]:
    if not isinstance(n, dict):
        raise ValueError(
            f"note[{index}] must be dict, got {type(n).__name__}"
        )
    required = ("pitch", "start", "duration", "velocity")
    missing = [k for k in required if k not in n]
    if missing:
        raise ValueError(f"note[{index}] missing keys: {missing}")

    pitch = _check_int(n["pitch"], f"note[{index}].pitch", 0, 127)

    try:
        start = float(n["start"])
    except (TypeError, ValueError):
        raise ValueError(
            f"note[{index}].start must be numeric, got {n['start']!r}"
        ) from None
    if start < 0:
        raise ValueError(f"note[{index}].start must be >= 0, got {start}")

    try:
        duration = float(n["duration"])
    except (TypeError, ValueError):
        raise ValueError(
            f"note[{index}].duration must be numeric, got {n['duration']!r}"
        ) from None
    if duration <= 0:
        raise ValueError(f"note[{index}].duration must be > 0, got {duration}")

    velocity = _check_int(n["velocity"], f"note[{index}].velocity", 1, 127)

    if "channel" in n:
        channel = _check_int(n["channel"], f"note[{index}].channel", 0, 15)
    else:
        channel = default_channel

    return {
        "pitch": pitch,
        "start": start,
        "duration": duration,
        "velocity": velocity,
        "channel": channel,
    }


def freeform_track(
    notes: list[dict[str, Any]],
    channel: int,
    instrument: int | None = None,
) -> dict[str, Any]:
    """Validate caller-composed notes; pass through unchanged otherwise.

    Args:
        notes: non-empty list of ``{pitch, start, duration, velocity[, channel]}``.
            ``pitch``/``velocity`` must be ints in [0, 127] / [1, 127];
            ``start`` must be >= 0; ``duration`` must be > 0; per-note
            ``channel`` (if present) must be in [0, 15]. A note that omits
            ``channel`` inherits the track-level ``channel``.
        channel: default MIDI channel (0-15) when a note omits its own.
        instrument: optional GM program number (0-127). Echoed in the
            result so the caller can forward it into ``write_midi`` as
            the track's ``instrument``.

    Returns ``{notes, instrument, summary}``. ``notes`` are returned in
    ``start``-ascending order.
    """
    if not isinstance(notes, list) or not notes:
        raise ValueError("notes must be a non-empty list")
    channel = _check_int(channel, "channel", 0, 15)
    if instrument is not None:
        instrument = _check_int(instrument, "instrument", 0, 127)

    validated = [_check_note(n, i, channel) for i, n in enumerate(notes)]
    validated.sort(key=lambda n: n["start"])

    summary = (
        f"freeform_track: {len(validated)} note(s), channel={channel}, "
        f"instrument={instrument}"
    )
    return {"notes": validated, "instrument": instrument, "summary": summary}
