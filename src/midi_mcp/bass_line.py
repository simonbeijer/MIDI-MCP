"""`bass_line` helper: render chord changes as a bass line.

Sub-slice 07a of slice 07 (per build order: walking before root_fifth
before sustained). Only the ``walking`` style ships in this slice;
``root_fifth`` and ``sustained`` will be added in follow-up slices
without breaking the contract — ``style`` is required and validated
against ``ALLOWED_STYLES``, so unknown values raise listing the set
that is actually wired today.

Walking pattern in 4/4: quarter notes, ``[root, 3rd, 5th, approach]``
where ``approach`` is a chromatic half-step below the next chord's
root (degenerates to the chord's own root for the final region — see
``_walking_region_pitches``). Approach-tone choice, beat-2 chord-tone
preference and register were chosen for simplicity; the textbook-fit
listen test gates whether they survive.

Seeded local ``random.Random`` is held for slice-08 humanize wiring;
the slice-07 path does not draw from it.
"""

import random
import time
import warnings
from typing import Any

from .config import output_dir
from .theory.harmony import parse_chord

ALLOWED_STYLES = ("walking",)

_PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Per-style register windows enforced by property tests.
BASS_REGISTER: dict[str, tuple[int, int]] = {
    "walking": (28, 55),  # E1 - G3, upright/electric bass range
}

# Per-style defaults. `anchor_pitch` is the target MIDI for the very
# first note; subsequent notes track to the previous pitch.
_STYLE_DEFAULTS: dict[str, dict[str, Any]] = {
    "walking": {"velocity": 90, "anchor_pitch": 40, "swing": 0.67},
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
        pass


def _absolute_beat(bar: int, beat: float, beats_per_bar: float) -> float:
    return (bar - 1) * beats_per_bar + (beat - 1.0)


def _realize_pc_near(pc: int, target_midi: int, lo: int, hi: int) -> int:
    """MIDI in ``[lo, hi]`` with pitch-class ``pc``, closest to ``target_midi``."""
    candidates = [m for m in range(lo, hi + 1) if m % 12 == pc]
    if not candidates:
        # window has no representative for this pc; pick nearest octave anyway
        base = target_midi - ((target_midi - pc) % 12)
        return base
    return min(candidates, key=lambda m: (abs(m - target_midi), m))


def _pick_chord_tone(parsed: dict[str, Any], semis_options: list[int]) -> int | None:
    root_pc = parsed["root"]
    pcs = parsed["pitch_classes"]
    for s in semis_options:
        cand = (root_pc + s) % 12
        if cand in pcs:
            return cand
    return None


def _walking_region_pitches(
    parsed: dict[str, Any],
    next_parsed: dict[str, Any] | None,
    n_beats: int,
    prev_midi: int | None,
    anchor_pitch: int,
    lo: int,
    hi: int,
) -> list[int]:
    """Quarter-note pitches for one chord region's walking line.

    Degree cycle (every 4 beats): ``[root, 3rd, 5th, approach]``.
    Beat 1 = root (chord-tone, satisfies the walking property).
    Beats 2-3 = 3rd / 5th, falling back to root if absent.
    Beat 4 = chromatic approach (half-step below next root); when there
    is no next chord (final region), the approach degenerates to the
    chord's own root rather than guessing the loop target.
    """
    if n_beats <= 0:
        return []
    root_pc = parsed["root"]
    third_pc = _pick_chord_tone(parsed, [3, 4])
    fifth_pc = _pick_chord_tone(parsed, [7, 6, 8])
    if third_pc is None:
        third_pc = root_pc
    if fifth_pc is None:
        fifth_pc = root_pc
    if next_parsed is not None:
        approach_pc = (next_parsed["root"] - 1) % 12
    else:
        approach_pc = root_pc  # final region: no next-chord target to lead to

    degree_pcs = [root_pc, third_pc, fifth_pc, approach_pc]

    pitches: list[int] = []
    for i in range(n_beats):
        pc = degree_pcs[i % 4]
        target = anchor_pitch if (i == 0 and prev_midi is None) else (
            prev_midi if i == 0 else pitches[-1]
        )
        m = _realize_pc_near(pc, target, lo, hi)
        pitches.append(m)
    return pitches


def bass_line(
    changes: list[dict[str, Any]],
    bars: int,
    key: str | None,
    time_sig: list[int],
    tempo: float,
    style: str,
    swing: float | None = None,
    seed: int | None = None,
    humanize: bool = False,
) -> dict[str, Any]:
    """Render ``changes`` into a bass-line notes list.

    Args:
        changes: list of ``{bar, beat, symbol}``; ``bar``/``beat`` are 1-based,
            ``beat`` is float.
        bars: total length in bars (required; not inferred from max bar).
        key: key signature; if missing, defaults to the first-chord root as
            major and emits a warning.
        time_sig: ``[numerator, denominator]``; numerator = beats-per-bar.
        tempo: bpm (passed through; rendering is tempo-independent).
        style: REQUIRED. Currently only ``walking`` is implemented in this
            slice; ``root_fifth`` and ``sustained`` land in follow-up slices.
            Unknown values raise ``ValueError`` listing the allowed set.
        swing: per-style default applied if ``None`` (walking default 0.67).
            Quarter-note walking has no off-beat eighths, so this slice
            records the parameter in the summary but does not warp note
            starts; wired in slice 08.
        seed: RNG seed; auto-generated if missing and appended to
            ``$MIDI_MCP_OUTPUT_DIR/.log``.
        humanize: accepted; True path wired in slice 08.

    Returns ``{notes, summary, seed}``.
    """
    if style not in ALLOWED_STYLES:
        raise ValueError(
            f"unknown style {style!r}; allowed: {list(ALLOWED_STYLES)}"
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

    defaults = _STYLE_DEFAULTS[style]
    if swing is None:
        swing = float(defaults["swing"])

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

    if seed is None:
        seed = random.randint(0, 2**31 - 1)
        _log_seed("bass_line", seed)
    rng = random.Random(seed)  # noqa: F841 — wired in slice 08
    _ = humanize

    beats_per_bar = float(num)
    total_beats = bars * beats_per_bar
    sorted_changes = sorted(
        changes,
        key=lambda c: _absolute_beat(int(c["bar"]), float(c["beat"]), beats_per_bar),
    )

    parsed_regions: list[tuple[float, float, dict[str, Any]]] = []
    for i, ch in enumerate(sorted_changes):
        start = _absolute_beat(int(ch["bar"]), float(ch["beat"]), beats_per_bar)
        if i == len(sorted_changes) - 1:
            end = total_beats
        else:
            nxt = sorted_changes[i + 1]
            end = _absolute_beat(int(nxt["bar"]), float(nxt["beat"]), beats_per_bar)
        if end - start <= 0:
            warnings.warn(
                f"chord at bar {ch['bar']} beat {ch['beat']} has non-positive "
                f"duration ({end - start}); skipping",
                stacklevel=2,
            )
            continue
        parsed = parse_chord(ch.get("symbol", ""))
        if "warning" in parsed:
            warnings.warn(parsed["warning"], stacklevel=2)
            continue
        parsed_regions.append((start, end, parsed))

    notes: list[dict[str, Any]] = []
    lo, hi = BASS_REGISTER[style]
    anchor = int(defaults["anchor_pitch"])
    velocity = int(defaults["velocity"])
    prev_midi: int | None = None

    for i, (start, end, parsed) in enumerate(parsed_regions):
        next_parsed = parsed_regions[i + 1][2] if i + 1 < len(parsed_regions) else None
        n_beats = int(round(end - start))
        if n_beats <= 0:
            continue
        pitches = _walking_region_pitches(
            parsed, next_parsed, n_beats, prev_midi, anchor, lo, hi
        )
        for j, p in enumerate(pitches):
            notes.append(
                {
                    "pitch": int(p),
                    "start": float(start + j),
                    "duration": 1.0,
                    "velocity": velocity,
                    "channel": 0,
                }
            )
        if pitches:
            prev_midi = pitches[-1]

    summary = (
        f"bass_line: {len(parsed_regions)}/{len(sorted_changes)} chord(s) rendered, "
        f"{len(notes)} note(s), style={style}, swing={swing:g}, {bars} bar(s), "
        f"key={key}, tempo={float(tempo):g}, seed={seed}"
    )
    return {"notes": notes, "summary": summary, "seed": seed}
