"""Tests for freeform_track: validation, default-channel fill, sort, echo."""

import pytest


def _note(**kw):
    base = {"pitch": 60, "start": 0.0, "duration": 1.0, "velocity": 80}
    base.update(kw)
    return base


# ----- Return shape ----------------------------------------------------------


def test_return_shape_notes_instrument_summary():
    from midi_mcp.freeform_track import freeform_track

    result = freeform_track(notes=[_note()], channel=0)
    assert set(result.keys()) == {"notes", "instrument", "summary"}
    assert result["instrument"] is None
    assert isinstance(result["summary"], str)
    assert all(
        set(n) == {"pitch", "start", "duration", "velocity", "channel"}
        for n in result["notes"]
    )


def test_instrument_echoed_in_result_and_summary():
    from midi_mcp.freeform_track import freeform_track

    result = freeform_track(notes=[_note()], channel=2, instrument=33)
    assert result["instrument"] == 33
    assert "instrument=33" in result["summary"]
    assert "channel=2" in result["summary"]


# ----- Channel fill / override ----------------------------------------------


def test_missing_channel_inherits_track_default():
    from midi_mcp.freeform_track import freeform_track

    result = freeform_track(notes=[_note()], channel=7)
    assert result["notes"][0]["channel"] == 7


def test_explicit_per_note_channel_overrides_default():
    from midi_mcp.freeform_track import freeform_track

    result = freeform_track(
        notes=[_note(channel=3), _note(start=1.0)], channel=7
    )
    assert result["notes"][0]["channel"] == 3
    assert result["notes"][1]["channel"] == 7


# ----- Sort by start ---------------------------------------------------------


def test_notes_returned_in_start_ascending_order():
    from midi_mcp.freeform_track import freeform_track

    out_of_order = [
        _note(start=2.0, pitch=62),
        _note(start=0.5, pitch=60),
        _note(start=1.0, pitch=61),
    ]
    result = freeform_track(notes=out_of_order, channel=0)
    starts = [n["start"] for n in result["notes"]]
    assert starts == sorted(starts)
    assert [n["pitch"] for n in result["notes"]] == [60, 61, 62]


# ----- No-theory pass-through -----------------------------------------------


def test_input_passes_through_unmodified():
    """No transposition, octave shift, rounding, or velocity tweak."""
    from midi_mcp.freeform_track import freeform_track

    notes_in = [
        _note(pitch=37, start=0.0, duration=0.75, velocity=110, channel=2),
        _note(pitch=84, start=1.25, duration=2.5, velocity=33, channel=5),
    ]
    result = freeform_track(notes=notes_in, channel=0)
    # input order is already start-ascending, so positions match
    for original, out in zip(notes_in, result["notes"]):
        assert out["pitch"] == original["pitch"]
        assert out["start"] == original["start"]
        assert out["duration"] == original["duration"]
        assert out["velocity"] == original["velocity"]
        assert out["channel"] == original["channel"]


# ----- Validation: top-level args -------------------------------------------


def test_empty_notes_raises():
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="non-empty list"):
        freeform_track(notes=[], channel=0)


def test_non_list_notes_raises():
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="non-empty list"):
        freeform_track(notes="not a list", channel=0)  # type: ignore[arg-type]


@pytest.mark.parametrize("channel", [-1, 16, 99])
def test_channel_out_of_range_raises(channel):
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="channel"):
        freeform_track(notes=[_note()], channel=channel)


def test_channel_non_int_raises():
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="channel"):
        freeform_track(notes=[_note()], channel=1.5)  # type: ignore[arg-type]


@pytest.mark.parametrize("instrument", [-1, 128, 200])
def test_instrument_out_of_range_raises(instrument):
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="instrument"):
        freeform_track(notes=[_note()], channel=0, instrument=instrument)


def test_instrument_non_int_raises():
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="instrument"):
        freeform_track(notes=[_note()], channel=0, instrument=33.0)  # type: ignore[arg-type]


# ----- Validation: per-note shape -------------------------------------------


@pytest.mark.parametrize(
    "missing", ["pitch", "start", "duration", "velocity"]
)
def test_missing_required_note_key_raises(missing):
    from midi_mcp.freeform_track import freeform_track

    n = _note()
    del n[missing]
    with pytest.raises(ValueError, match=missing):
        freeform_track(notes=[n], channel=0)


def test_non_dict_note_raises():
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match=r"note\[0\]"):
        freeform_track(notes=[(60, 0, 1, 80)], channel=0)  # type: ignore[list-item]


# ----- Validation: per-note ranges ------------------------------------------


@pytest.mark.parametrize("pitch", [-1, 128, 9999])
def test_pitch_out_of_range_raises(pitch):
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="pitch"):
        freeform_track(notes=[_note(pitch=pitch)], channel=0)


@pytest.mark.parametrize("velocity", [0, -1, 128])
def test_velocity_out_of_range_raises(velocity):
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="velocity"):
        freeform_track(notes=[_note(velocity=velocity)], channel=0)


def test_negative_start_raises():
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="start"):
        freeform_track(notes=[_note(start=-0.5)], channel=0)


@pytest.mark.parametrize("duration", [0, -1.0])
def test_non_positive_duration_raises(duration):
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="duration"):
        freeform_track(notes=[_note(duration=duration)], channel=0)


@pytest.mark.parametrize("ch", [-1, 16])
def test_per_note_channel_out_of_range_raises(ch):
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match=r"note\[0\].channel"):
        freeform_track(notes=[_note(channel=ch)], channel=0)


# ----- bool is not int -------------------------------------------------------


def test_bool_channel_rejected():
    """bool is technically int in Python; reject explicitly."""
    from midi_mcp.freeform_track import freeform_track

    with pytest.raises(ValueError, match="channel"):
        freeform_track(notes=[_note()], channel=True)  # type: ignore[arg-type]


# ----- End-to-end through write_midi ----------------------------------------


def test_pipes_through_write_midi(tmp_path, monkeypatch):
    """freeform_track → write_midi round-trip writes a non-empty .mid."""
    from pathlib import Path

    from midi_mcp.freeform_track import freeform_track
    from midi_mcp.write_midi import write_midi

    monkeypatch.setenv("MIDI_MCP_OUTPUT_DIR", str(tmp_path))
    result = freeform_track(
        notes=[
            _note(pitch=40, start=0.0, duration=1.0),
            _note(pitch=43, start=1.0, duration=1.0),
            _note(pitch=45, start=2.0, duration=2.0),
        ],
        channel=0,
        instrument=33,
    )
    write_result = write_midi(
        tracks=[
            {
                "name": "freeform_bass",
                "instrument": result["instrument"],
                "notes": result["notes"],
            }
        ],
        tempo=120.0,
        time_sig=[4, 4],
        key="C",
        filename="freeform_smoke",
    )
    path = Path(write_result["path"])
    assert path.exists()
    assert path.stat().st_size > 0
