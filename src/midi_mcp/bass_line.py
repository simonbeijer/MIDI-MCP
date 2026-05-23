"""`bass_line` helper: render chord changes as a bass line.

Slices 07a (walking), 07b (root_fifth), and 07c (sustained) shipped.
``style`` is required and validated against ``ALLOWED_STYLES``, so
unknown values raise listing the set that is actually wired today.

Walking pattern in 4/4: quarter notes, ``[root, 3rd, 5th, approach]``
where ``approach`` is a chromatic half-step below the next chord's
root (degenerates to the chord's own root for the final region — see
``_walking_region_pitches``). Approach-tone choice, beat-2 chord-tone
preference and register were chosen for simplicity; the textbook-fit
listen test gates whether they survive.

Root-fifth pattern: half-note root at region start, half-note fifth at
region start + 2. Falls back to root-only if the region is < 3 beats,
and to root pc if the chord has no fifth (e.g. some sus voicings). No
sub-rule deviation in this slice — every bar gets root-then-fifth;
issue's "or root, per documented sub-rule" left for a later pass.
Simplest-choice note: long single-chord regions (> 4 beats / 1 bar)
would let the fifth's duration cross a barline; the test fixture only
exercises chord-per-bar so we don't split per-bar yet.

Sustained pattern: one note per chord region, root pitch class held
for the region's full duration. ``swing`` default ``0.50`` (no
rhythmic activity to swing). Fifth/approach logic does not apply.

Seeded local ``random.Random`` drives the ``humanize=True`` path
(slice 08). ``humanize=False`` draws nothing from it; ``humanize=True``
applies symmetric velocity and micro-timing jitter per note, clamping
start to the note's bar downbeat so jitter never pushes a note
earlier than its bar.
"""

import random
import time
import warnings
from typing import Any

from .config import output_dir
from .theory.harmony import parse_chord

ALLOWED_STYLES = ("walking", "root_fifth", "sustained")

_PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Per-style register windows enforced by property tests.
BASS_REGISTER: dict[str, tuple[int, int]] = {
    "walking": (28, 55),  # E1 - G3, upright/electric bass range
    "root_fifth": (28, 55),
    "sustained": (28, 55),
}

# Per-style defaults. `anchor_pitch` is the target MIDI for the very
# first note; subsequent notes track to the previous pitch.
_STYLE_DEFAULTS: dict[str, dict[str, Any]] = {
    "walking": {"velocity": 90, "anchor_pitch": 40, "swing": 0.67},
    "root_fifth": {"velocity": 90, "anchor_pitch": 40, "swing": 0.50},
    "sustained": {"velocity": 90, "anchor_pitch": 40, "swing": 0.50},
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


# Symmetric jitter magnitudes for humanize=True. v2 will split this into
# explicit `velocity_jitter: float` and `timing_jitter: float` params.
_HUMANIZE_VELOCITY_RANGE = 6  # +/- units around the per-style default
_HUMANIZE_TIMING_RANGE = 0.02  # +/- beats


def _apply_humanize(
    notes: list[dict[str, Any]], rng: random.Random, beats_per_bar: float
) -> None:
    """Apply seeded velocity + timing jitter in place.

    Clamps start to the note's bar downbeat so jitter never pushes a
    note earlier than its bar.
    """
    for n in notes:
        v_jitter = rng.randint(-_HUMANIZE_VELOCITY_RANGE, _HUMANIZE_VELOCITY_RANGE)
        n["velocity"] = max(1, min(127, int(n["velocity"]) + v_jitter))
        t_jitter = rng.uniform(-_HUMANIZE_TIMING_RANGE, _HUMANIZE_TIMING_RANGE)
        bar_index = int(n["start"] // beats_per_bar)
        bar_start = bar_index * beats_per_bar
        n["start"] = max(bar_start, n["start"] + t_jitter)


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


def _root_fifth_region_notes(
    parsed: dict[str, Any],
    start: float,
    n_beats: int,
    prev_midi: int | None,
    anchor: int,
    lo: int,
    hi: int,
    velocity: int,
) -> tuple[list[dict[str, Any]], int]:
    """Half-note root at region beat 1, half-note fifth at region beat 3.

    Falls back to root-only if ``n_beats < 3``. Fifth degenerates to root
    pc when chord has no fifth (e.g. some sus voicings).
    """
    root_pc = parsed["root"]
    fifth_pc = _pick_chord_tone(parsed, [7, 6, 8])
    if fifth_pc is None:
        fifth_pc = root_pc
    target = anchor if prev_midi is None else prev_midi
    root_m = _realize_pc_near(root_pc, target, lo, hi)
    notes: list[dict[str, Any]] = [
        {
            "pitch": root_m,
            "start": float(start),
            "duration": float(min(2, n_beats)),
            "velocity": velocity,
            "channel": 0,
        }
    ]
    if n_beats < 3:
        return notes, root_m
    fifth_m = _realize_pc_near(fifth_pc, root_m, lo, hi)
    notes.append(
        {
            "pitch": fifth_m,
            "start": float(start + 2.0),
            "duration": float(n_beats - 2),
            "velocity": velocity,
            "channel": 0,
        }
    )
    return notes, fifth_m


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
        style: REQUIRED. One of ``walking``, ``root_fifth``, ``sustained``.
            Unknown values raise ``ValueError`` listing the allowed set.
        swing: per-style default applied if ``None`` (walking 0.67,
            root_fifth 0.50, sustained 0.50). Recorded in the summary
            but does not warp note starts in this slice; wired in slice 08.
        seed: RNG seed; auto-generated if missing and appended to
            ``$MIDI_MCP_OUTPUT_DIR/.log``.
        humanize: when True, applies seeded symmetric velocity (+/- 6) and
            micro-timing (+/- 0.02 beats) jitter to every note. Start is
            clamped to the note's bar downbeat so jitter never pushes a
            note earlier than its bar. v2 intent: split into
            ``velocity_jitter: float`` and ``timing_jitter: float``.

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
    rng = random.Random(seed)

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
        n_beats = int(round(end - start))
        if n_beats <= 0:
            continue
        if style == "walking":
            next_parsed = (
                parsed_regions[i + 1][2] if i + 1 < len(parsed_regions) else None
            )
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
        elif style == "root_fifth":
            region_notes, prev_midi = _root_fifth_region_notes(
                parsed, start, n_beats, prev_midi, anchor, lo, hi, velocity
            )
            notes.extend(region_notes)
        elif style == "sustained":
            root_pc = parsed["root"]
            target = anchor if prev_midi is None else prev_midi
            root_m = _realize_pc_near(root_pc, target, lo, hi)
            notes.append(
                {
                    "pitch": int(root_m),
                    "start": float(start),
                    "duration": float(n_beats),
                    "velocity": velocity,
                    "channel": 0,
                }
            )
            prev_midi = root_m

    if humanize:
        _apply_humanize(notes, rng, beats_per_bar)

    summary = (
        f"bass_line: {len(parsed_regions)}/{len(sorted_changes)} chord(s) rendered, "
        f"{len(notes)} note(s), style={style}, swing={swing:g}, {bars} bar(s), "
        f"key={key}, tempo={float(tempo):g}, seed={seed}"
    )
    return {"notes": notes, "summary": summary, "seed": seed}
