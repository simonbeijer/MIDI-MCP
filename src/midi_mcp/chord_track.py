"""`chord_track` helper: render chord changes as voiced MIDI notes.

Three voicings ship in v1: ``drop2`` (jazz), ``triad`` (indie/rock),
``sustained_pad`` (lo-fi). ``voicing`` is a required parameter — there
is no smart default; an unknown value raises with the allowed list.

A seeded ``random.Random`` is constructed for every call so future
``humanize=True`` wiring (slice 08) is deterministic. The current
``humanize=False`` path uses no randomness, but the seed is still
returned and logged so calls are reproducible after slice 08 lands.
"""

import random
import time
import warnings
from typing import Any

from .config import output_dir
from .theory.harmony import parse_chord

ALLOWED_VOICINGS = ("drop2", "triad", "sustained_pad")

_PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Per-voicing defaults. Registers chosen so a Logic listen test can
# distinguish the three by ear without further tweaking.
_VOICING_DEFAULTS: dict[str, dict[str, int]] = {
    # drop2: top voice around C5 — sits above a walking bass
    "drop2": {"velocity": 75, "anchor_pitch": 72, "anchor": "top"},
    # triad: root in the guitar/keys register
    "triad": {"velocity": 85, "anchor_pitch": 48, "anchor": "root"},
    # sustained_pad: same root register, full hold, softer velocity
    "sustained_pad": {"velocity": 60, "anchor_pitch": 48, "anchor": "root"},
}

# Voicing-specific register windows enforced by property tests.
VOICING_REGISTER: dict[str, tuple[int, int]] = {
    "drop2": (36, 84),
    "triad": (36, 72),
    "sustained_pad": (36, 84),
}


def _log_seed(helper: str, seed: int) -> None:
    """Append a single line to ``$MIDI_MCP_OUTPUT_DIR/.log``."""
    try:
        log_path = output_dir() / ".log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        with log_path.open("a") as f:
            f.write(f"{ts} {helper} seed={seed}\n")
    except OSError:
        # logging is best-effort; never fail the helper because of it
        pass


def _close_voicing(pitches: list[int]) -> list[int]:
    """Stack ``pitches`` above the lowest, each within an octave of the previous."""
    if not pitches:
        return list(pitches)
    sorted_p = sorted(pitches)
    bass = sorted_p[0]
    out = [bass]
    last = bass
    for p in sorted_p[1:]:
        while p < last:
            p += 12
        out.append(p)
        last = p
    return out


def _shift_to_anchor(pitches: list[int], target: int, anchor: str) -> list[int]:
    """Octave-shift the whole voicing so ``anchor`` (top|root) sits near ``target``."""
    if not pitches:
        return list(pitches)
    anchor_pitch = pitches[-1] if anchor == "top" else pitches[0]
    delta_octaves = round((target - anchor_pitch) / 12)
    shift = delta_octaves * 12
    return [p + shift for p in pitches]


def _voice_drop2(close: list[int]) -> list[int]:
    """Four-way close → drop the 2nd-from-top voice an octave."""
    voices = list(close)
    # ensure four voices; if fewer, double the root up an octave
    while len(voices) < 4:
        voices.append(voices[0] + 12)
    voices.sort()
    voices = voices[:4]
    drop_idx = len(voices) - 2
    voices[drop_idx] -= 12
    voices.sort()
    return voices


def _build_voicing(voicing: str, parsed: dict[str, Any]) -> tuple[list[int], int]:
    """Return ``(pitches, velocity)`` for a single chord realization."""
    defaults = _VOICING_DEFAULTS[voicing]
    if voicing == "drop2":
        close = _close_voicing(parsed["pitches"])
        voiced = _voice_drop2(close)
    elif voicing == "triad":
        triad_src = parsed["pitches"][:3] if len(parsed["pitches"]) >= 3 else parsed["pitches"]
        voiced = _close_voicing(triad_src)
    elif voicing == "sustained_pad":
        voiced = _close_voicing(parsed["pitches"])
    else:  # defensive; caller validates
        raise ValueError(f"unknown voicing {voicing!r}")
    voiced = _shift_to_anchor(voiced, defaults["anchor_pitch"], defaults["anchor"])
    return voiced, defaults["velocity"]


def _absolute_beat(bar: int, beat: float, beats_per_bar: float) -> float:
    return (bar - 1) * beats_per_bar + (beat - 1.0)


def chord_track(
    changes: list[dict[str, Any]],
    bars: int,
    key: str | None,
    time_sig: list[int],
    tempo: float,
    voicing: str,
    seed: int | None = None,
    humanize: bool = False,
) -> dict[str, Any]:
    """Render ``changes`` into a voiced notes list.

    Args:
        changes: list of ``{bar, beat, symbol}``; ``bar``/``beat`` are 1-based,
            ``beat`` is float.
        bars: total length in bars (required; not inferred from max bar).
        key: key signature; if missing, defaults to the first-chord root as
            major and emits a warning.
        time_sig: ``[numerator, denominator]``; numerator is treated as the
            beats-per-bar count.
        tempo: bpm (accepted, but rendering is tempo-independent; passed
            through for the caller's downstream ``write_midi`` call).
        voicing: REQUIRED. One of ``drop2``, ``triad``, ``sustained_pad``.
            Unknown values raise ``ValueError`` listing the allowed set.
        seed: RNG seed; auto-generated if missing and appended to
            ``$MIDI_MCP_OUTPUT_DIR/.log``.
        humanize: accepted but unused in v1 slice 05; wired in slice 08.

    Returns ``{notes, summary, seed}``.
    """
    if voicing not in ALLOWED_VOICINGS:
        raise ValueError(
            f"unknown voicing {voicing!r}; allowed: {list(ALLOWED_VOICINGS)}"
        )
    if not isinstance(changes, list) or not changes:
        raise ValueError("changes must be a non-empty list")
    if not isinstance(bars, int) or bars <= 0:
        raise ValueError(f"bars must be a positive int, got {bars!r}")
    try:
        num = int(time_sig[0])
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError(f"invalid time_sig {time_sig!r}: {exc}") from None
    if num <= 0:
        raise ValueError(f"time_sig numerator must be > 0, got {num}")

    # key handling
    if not key:
        first = parse_chord(changes[0].get("symbol", ""))
        if "warning" not in first:
            key = _PITCH_NAMES[first["root"]]
            warnings.warn(
                f"key missing; defaulting to first-chord root as major: {key}",
                stacklevel=2,
            )
        else:
            key = "C"
            warnings.warn(
                "key missing and first chord unparseable; defaulting to C",
                stacklevel=2,
            )

    # seeded RNG: held for slice-08 humanize wiring even though slice 05
    # doesn't draw from it. Constructing it here keeps determinism shape
    # locked in now.
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
        _log_seed("chord_track", seed)
    rng = random.Random(seed)  # noqa: F841 — wired in slice 08
    _ = humanize  # accepted, unused in slice 05

    beats_per_bar = float(num)
    total_beats = bars * beats_per_bar
    sorted_changes = sorted(
        changes, key=lambda c: _absolute_beat(int(c["bar"]), float(c["beat"]), beats_per_bar)
    )

    notes: list[dict[str, Any]] = []
    rendered_chords = 0
    for i, ch in enumerate(sorted_changes):
        start = _absolute_beat(int(ch["bar"]), float(ch["beat"]), beats_per_bar)
        if i == len(sorted_changes) - 1:
            end = total_beats
        else:
            nxt = sorted_changes[i + 1]
            end = _absolute_beat(int(nxt["bar"]), float(nxt["beat"]), beats_per_bar)
        duration = end - start
        if duration <= 0:
            warnings.warn(
                f"chord at bar {ch['bar']} beat {ch['beat']} has non-positive "
                f"duration ({duration}); skipping",
                stacklevel=2,
            )
            continue
        parsed = parse_chord(ch.get("symbol", ""))
        if "warning" in parsed:
            warnings.warn(parsed["warning"], stacklevel=2)
            continue
        pitches, velocity = _build_voicing(voicing, parsed)
        for p in pitches:
            notes.append(
                {
                    "pitch": int(p),
                    "start": float(start),
                    "duration": float(duration),
                    "velocity": int(velocity),
                    "channel": 0,
                }
            )
        rendered_chords += 1

    summary = (
        f"chord_track: {rendered_chords}/{len(sorted_changes)} chord(s) rendered, "
        f"{len(notes)} note(s), voicing={voicing}, {bars} bar(s), "
        f"key={key}, tempo={float(tempo):g}, seed={seed}"
    )
    return {"notes": notes, "summary": summary, "seed": seed}
