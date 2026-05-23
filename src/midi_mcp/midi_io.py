"""MIDI file I/O. Absolute beat→tick math; fixed meta event order.

mido is the only MIDI library used here; do not introduce `pretty_midi`.
This module MUST NOT import `random` — snapshot tests depend on byte-stability.
"""

from pathlib import Path
from typing import Any

import mido

from .config import TICKS_PER_BEAT


def _build_conductor_track(
    tempo: float, time_sig: tuple[int, int], key: str
) -> mido.MidiTrack:
    """Track 0: meta events only, in fixed order."""
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo), time=0))
    num, den = time_sig
    track.append(
        mido.MetaMessage(
            "time_signature", numerator=num, denominator=den, time=0
        )
    )
    track.append(mido.MetaMessage("key_signature", key=key, time=0))
    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def _build_note_track(track_spec: dict[str, Any]) -> mido.MidiTrack:
    track = mido.MidiTrack()
    name = track_spec.get("name")
    if name:
        track.append(mido.MetaMessage("track_name", name=str(name), time=0))
    notes = track_spec.get("notes", [])
    instrument = track_spec.get("instrument")
    if isinstance(instrument, int):
        first_channel = int(notes[0].get("channel", 0)) if notes else 0
        track.append(
            mido.Message(
                "program_change",
                program=instrument,
                channel=first_channel,
                time=0,
            )
        )

    # absolute-tick events; sort with note_off before note_on at the same tick
    events: list[tuple[int, int, mido.Message]] = []
    for n in notes:
        pitch = int(n["pitch"])
        start = float(n["start"])
        duration = float(n["duration"])
        velocity = int(n["velocity"])
        channel = int(n.get("channel", 0))
        on_tick = round(start * TICKS_PER_BEAT)
        off_tick = round((start + duration) * TICKS_PER_BEAT)
        if off_tick <= on_tick:
            off_tick = on_tick + 1
        events.append(
            (on_tick, 1, mido.Message("note_on", note=pitch, velocity=velocity, channel=channel))
        )
        events.append(
            (off_tick, 0, mido.Message("note_off", note=pitch, velocity=0, channel=channel))
        )

    events.sort(key=lambda e: (e[0], e[1]))
    prev_tick = 0
    for abs_tick, _, msg in events:
        delta = abs_tick - prev_tick
        track.append(msg.copy(time=delta))
        prev_tick = abs_tick
    track.append(mido.MetaMessage("end_of_track", time=0))
    return track


def write_midi_file(
    path: Path,
    tracks: list[dict[str, Any]],
    tempo: float,
    time_sig: tuple[int, int],
    key: str,
) -> float:
    """Write a multi-track .mid file. Returns duration in seconds.

    Track 0 is conductor-only; supplied ``tracks`` are written from track 1.
    """
    mid = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
    mid.tracks.append(_build_conductor_track(tempo, tuple(time_sig), key))
    for spec in tracks:
        mid.tracks.append(_build_note_track(spec))

    path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(path)

    last_beat = 0.0
    for spec in tracks:
        for n in spec.get("notes", []):
            end = float(n["start"]) + float(n["duration"])
            if end > last_beat:
                last_beat = end
    return last_beat * 60.0 / float(tempo)
