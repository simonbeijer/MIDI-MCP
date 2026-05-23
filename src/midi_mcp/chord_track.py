"""`chord_track` helper: render chord changes as voiced MIDI notes.

Seven voicings ship in v1: ``drop2`` (jazz), ``triad`` (indie/rock),
``sustained_pad`` (lo-fi), ``shell`` (jazz root+3+7), ``rootless``
(jazz, root omitted), ``power`` (rock root+5+octave), ``quartal``
(modal/gospel, fourth-stacked). ``voicing`` is a required parameter —
there is no smart default; an unknown value raises with the allowed list.

A seeded ``random.Random`` is constructed for every call so the
``humanize=True`` path (slice 08) is deterministic. ``humanize=False``
draws nothing from the RNG; ``humanize=True`` applies symmetric
velocity and micro-timing jitter per note. Start is clamped to the
note's bar downbeat so jitter never pushes a note earlier than its
bar.
"""

import random
import time
import warnings
from typing import Any

from .config import output_dir
from .theory.harmony import parse_chord

ALLOWED_VOICINGS = (
    "drop2",
    "triad",
    "sustained_pad",
    "shell",
    "rootless",
    "power",
    "quartal",
)

_PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Per-voicing defaults. Registers chosen so a Logic listen test can
# distinguish them by ear without further tweaking.
_VOICING_DEFAULTS: dict[str, dict[str, int]] = {
    # drop2: top voice around C5 — sits above a walking bass
    "drop2": {"velocity": 75, "anchor_pitch": 72, "anchor": "top"},
    # triad: root in the guitar/keys register
    "triad": {"velocity": 85, "anchor_pitch": 48, "anchor": "root"},
    # sustained_pad: same root register, full hold, softer velocity
    "sustained_pad": {"velocity": 60, "anchor_pitch": 48, "anchor": "root"},
    # shell: root + 3rd + 7th, low-mid (guitar/keys backings)
    "shell": {"velocity": 75, "anchor_pitch": 55, "anchor": "root"},
    # rootless: 3rd + 5th + 7th + 9th if present, RH piano register
    "rootless": {"velocity": 70, "anchor_pitch": 60, "anchor": "root"},
    # power: root + 5th + octave root, bass guitar register
    "power": {"velocity": 95, "anchor_pitch": 40, "anchor": "root"},
    # quartal: stacked roughly in 4ths, mid register
    "quartal": {"velocity": 70, "anchor_pitch": 60, "anchor": "root"},
}

# Voicing-specific register windows enforced by property tests.
VOICING_REGISTER: dict[str, tuple[int, int]] = {
    "drop2": (36, 84),
    "triad": (36, 72),
    "sustained_pad": (36, 84),
    "shell": (40, 76),
    "rootless": (48, 84),
    "power": (28, 64),
    "quartal": (48, 84),
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


def _realize_pcs_ascending(pcs_seq: list[int], start_midi: int) -> list[int]:
    """Realize ``pcs_seq`` as ascending MIDI; first voice ≥ ``start_midi``."""
    if not pcs_seq:
        return []
    first_pc = pcs_seq[0] % 12
    first_midi = start_midi + ((first_pc - start_midi) % 12)
    out = [first_midi]
    last = first_midi
    for pc in pcs_seq[1:]:
        offset = (pc - last) % 12
        if offset == 0:
            offset = 12  # avoid duplicate at same MIDI as prev voice
        last = last + offset
        out.append(last)
    return out


def _pick_pc(pcs: set[int], root_pc: int, semis_options: list[int]) -> int | None:
    """First ``(root_pc + s) % 12`` from ``semis_options`` that is in ``pcs``."""
    for s in semis_options:
        cand = (root_pc + s) % 12
        if cand in pcs:
            return cand
    return None


def _voice_shell(parsed: dict[str, Any]) -> list[int]:
    """root + 3rd + 7th, drawn from the chord's pitch classes."""
    root_pc = parsed["root"]
    pcs = parsed["pitch_classes"]
    selected = [root_pc]
    third = _pick_pc(pcs, root_pc, [3, 4])
    seventh = _pick_pc(pcs, root_pc, [10, 11])
    for pc in (third, seventh):
        if pc is not None:
            selected.append(pc)
    return _realize_pcs_ascending(selected, start_midi=48)


def _voice_rootless(parsed: dict[str, Any]) -> list[int]:
    """3rd + 5th + 7th + (9th if present) — root pitch class always omitted."""
    root_pc = parsed["root"]
    pcs = parsed["pitch_classes"]
    third = _pick_pc(pcs, root_pc, [3, 4])
    # 5th: skip if it would collide with the third (e.g. dim chord b5 == #4)
    fifth = _pick_pc(pcs, root_pc, [6, 7, 8])
    seventh = _pick_pc(pcs, root_pc, [10, 11])
    ninth = _pick_pc(pcs, root_pc, [1, 2])
    selected: list[int] = []
    seen: set[int] = set()
    for pc in (third, fifth, seventh, ninth):
        if pc is not None and pc not in seen and pc != root_pc:
            selected.append(pc)
            seen.add(pc)
    if not selected:
        # last-resort: any non-root pc in the chord
        non_roots = sorted(
            (pc for pc in pcs if pc != root_pc),
            key=lambda pc: (pc - root_pc) % 12,
        )
        if non_roots:
            selected = non_roots
        else:
            selected = [root_pc]  # degenerate: chord IS just the root
    return _realize_pcs_ascending(selected, start_midi=60)


def _voice_power(parsed: dict[str, Any]) -> list[int]:
    """root + 5th + octave root (5th falls back to b5/#5 if no P5)."""
    root_pc = parsed["root"]
    pcs = parsed["pitch_classes"]
    fifth = _pick_pc(pcs, root_pc, [7, 6, 8])
    selected = [root_pc]
    if fifth is not None:
        selected.append(fifth)
    selected.append(root_pc)  # octave root
    return _realize_pcs_ascending(selected, start_midi=36)


def _voice_quartal(parsed: dict[str, Any]) -> list[int]:
    """Three voices, each chosen so the interval above the prev approximates P4.

    Selection runs over the chord's own pitch classes (subset constraint),
    so on tonal 7th chords without intervallic 4ths this degenerates toward
    a close voicing — the quartal character only fully emerges on
    sus/modal/quartal-friendly chord inputs.
    """
    root_pc = parsed["root"]
    pcs = parsed["pitch_classes"]
    seq: list[int] = [root_pc]
    used = {root_pc}
    last = root_pc
    for _ in range(2):
        candidates = [pc for pc in pcs if pc not in used]
        if not candidates:
            break
        best = min(
            candidates,
            key=lambda pc: (abs(((pc - last) % 12) - 5), (pc - last) % 12),
        )
        seq.append(best)
        used.add(best)
        last = best
    return _realize_pcs_ascending(seq, start_midi=60)


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
    elif voicing == "shell":
        voiced = _voice_shell(parsed)
    elif voicing == "rootless":
        voiced = _voice_rootless(parsed)
    elif voicing == "power":
        voiced = _voice_power(parsed)
    elif voicing == "quartal":
        voiced = _voice_quartal(parsed)
    else:  # defensive; caller validates
        raise ValueError(f"unknown voicing {voicing!r}")
    voiced = _shift_to_anchor(voiced, defaults["anchor_pitch"], defaults["anchor"])
    return voiced, defaults["velocity"]


def _absolute_beat(bar: int, beat: float, beats_per_bar: float) -> float:
    return (bar - 1) * beats_per_bar + (beat - 1.0)


# Symmetric jitter magnitudes for humanize=True. v2 will split this into
# explicit `velocity_jitter: float` and `timing_jitter: float` params.
_HUMANIZE_VELOCITY_RANGE = 6  # +/- units around the per-voicing default
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
        voicing: REQUIRED. One of ``drop2``, ``triad``, ``sustained_pad``,
            ``shell``, ``rootless``, ``power``, ``quartal``. Unknown values
            raise ``ValueError`` listing the allowed set.
        seed: RNG seed; auto-generated if missing and appended to
            ``$MIDI_MCP_OUTPUT_DIR/.log``.
        humanize: when True, applies seeded symmetric velocity (+/- 6) and
            micro-timing (+/- 0.02 beats) jitter to every note. Start is
            clamped to the note's bar downbeat so jitter never pushes a
            note earlier than its bar. v2 intent: split into
            ``velocity_jitter: float`` and ``timing_jitter: float``.

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
    rng = random.Random(seed)

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

    if humanize:
        _apply_humanize(notes, rng, beats_per_bar)

    summary = (
        f"chord_track: {rendered_chords}/{len(sorted_changes)} chord(s) rendered, "
        f"{len(notes)} note(s), voicing={voicing}, {bars} bar(s), "
        f"key={key}, tempo={float(tempo):g}, seed={seed}"
    )
    return {"notes": notes, "summary": summary, "seed": seed}
