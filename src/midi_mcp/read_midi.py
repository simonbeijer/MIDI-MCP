"""`read_midi` tool: parse .mid via mido into the data contract.

Returns at most 50 notes to bound context blow-up.
"""

from pathlib import Path
from typing import Any

import mido

_MAX_NOTES = 50


def _extract_meta(mid: mido.MidiFile) -> tuple[float | None, list[int] | None, str | None]:
    tempo_bpm: float | None = None
    time_sig: list[int] | None = None
    key: str | None = None
    for track in mid.tracks:
        for msg in track:
            if msg.type == "set_tempo" and tempo_bpm is None:
                tempo_bpm = mido.tempo2bpm(msg.tempo)
            elif msg.type == "time_signature" and time_sig is None:
                time_sig = [msg.numerator, msg.denominator]
            elif msg.type == "key_signature" and key is None:
                key = msg.key
            if tempo_bpm is not None and time_sig is not None and key is not None:
                return tempo_bpm, time_sig, key
    return tempo_bpm, time_sig, key


def _extract_notes(mid: mido.MidiFile) -> list[dict[str, Any]]:
    tpb = mid.ticks_per_beat
    notes: list[dict[str, Any]] = []
    for track in mid.tracks:
        abs_tick = 0
        pending: dict[tuple[int, int], tuple[int, int]] = {}
        for msg in track:
            abs_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                pending[(msg.channel, msg.note)] = (abs_tick, msg.velocity)
            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                k = (msg.channel, msg.note)
                if k in pending:
                    on_tick, vel = pending.pop(k)
                    notes.append(
                        {
                            "pitch": msg.note,
                            "start": on_tick / tpb,
                            "duration": (abs_tick - on_tick) / tpb,
                            "velocity": vel,
                            "channel": msg.channel,
                        }
                    )
    notes.sort(key=lambda n: (n["start"], n["pitch"]))
    return notes


def read_midi(path: str) -> dict[str, Any]:
    """Read a .mid file and return structured fields + first 50 notes.

    Returns ``{summary, first_50_notes, tempo, time_sig, key, track_count}``.
    """
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"no such file: {path!r}")

    mid = mido.MidiFile(str(p))
    tempo, time_sig, key = _extract_meta(mid)
    all_notes = _extract_notes(mid)
    truncated = all_notes[:_MAX_NOTES]
    track_count = len(mid.tracks)

    tempo_str = f"{tempo:g} bpm" if tempo is not None else "unknown tempo"
    ts_str = f"{time_sig[0]}/{time_sig[1]}" if time_sig else "unknown time_sig"
    key_str = f"key {key}" if key else "unknown key"
    summary = (
        f"read {p.name}: {track_count} track(s), {len(all_notes)} note(s) "
        f"({len(truncated)} returned), {tempo_str}, {ts_str}, {key_str}"
    )

    return {
        "summary": summary,
        "first_50_notes": truncated,
        "tempo": tempo,
        "time_sig": time_sig,
        "key": key,
        "track_count": track_count,
    }
