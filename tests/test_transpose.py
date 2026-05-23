"""Tests for transpose: shifts, clamps, empty list."""

import warnings as warn_mod

import pytest


def _notes(*pitches: int) -> list[dict]:
    return [
        {"pitch": p, "start": float(i), "duration": 1.0, "velocity": 80, "channel": 0}
        for i, p in enumerate(pitches)
    ]


def test_positive_shift():
    from midi_mcp.transpose import transpose

    out = transpose(_notes(60, 62, 64), 12)
    assert [n["pitch"] for n in out] == [72, 74, 76]


def test_negative_shift():
    from midi_mcp.transpose import transpose

    out = transpose(_notes(60, 62, 64), -12)
    assert [n["pitch"] for n in out] == [48, 50, 52]


def test_empty_list():
    from midi_mcp.transpose import transpose

    assert transpose([], 7) == []


def test_other_fields_preserved():
    from midi_mcp.transpose import transpose

    notes = _notes(60)
    notes[0]["velocity"] = 99
    notes[0]["channel"] = 3
    notes[0]["duration"] = 2.5
    notes[0]["start"] = 1.5
    out = transpose(notes, 2)
    assert out[0]["pitch"] == 62
    assert out[0]["velocity"] == 99
    assert out[0]["channel"] == 3
    assert out[0]["duration"] == 2.5
    assert out[0]["start"] == 1.5


def test_high_clamp_warns():
    from midi_mcp.transpose import transpose

    with warn_mod.catch_warnings(record=True) as caught:
        warn_mod.simplefilter("always")
        out = transpose(_notes(120, 60), 20)
    assert out[0]["pitch"] == 127
    assert out[1]["pitch"] == 80
    assert any("clamped" in str(w.message) for w in caught)


def test_low_clamp_warns():
    from midi_mcp.transpose import transpose

    with warn_mod.catch_warnings(record=True) as caught:
        warn_mod.simplefilter("always")
        out = transpose(_notes(5, 60), -10)
    assert out[0]["pitch"] == 0
    assert out[1]["pitch"] == 50
    assert any("clamped" in str(w.message) for w in caught)


def test_in_range_does_not_warn():
    from midi_mcp.transpose import transpose

    with warn_mod.catch_warnings(record=True) as caught:
        warn_mod.simplefilter("always")
        transpose(_notes(60, 62), 5)
    assert [w for w in caught if "clamped" in str(w.message)] == []
