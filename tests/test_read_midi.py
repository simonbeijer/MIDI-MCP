"""Behavior tests for read_midi: round-trip metadata + notes truncation shape."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDI_MCP_OUTPUT_DIR", str(tmp_path))
    yield tmp_path


def _scale_fixture() -> dict:
    pitches = [60, 62, 64, 65, 67, 69, 71, 72]
    notes = [
        {"pitch": p, "start": float(i), "duration": 1.0, "velocity": 80, "channel": 0}
        for i, p in enumerate(pitches)
    ]
    return {
        "tracks": [{"name": "scale", "notes": notes}],
        "tempo": 120.0,
        "time_sig": [4, 4],
        "key": "C",
        "filename": "scale_for_read",
    }


def test_read_midi_returns_expected_shape(tmp_path):
    from midi_mcp.read_midi import read_midi
    from midi_mcp.write_midi import write_midi

    written = write_midi(**_scale_fixture())
    result = read_midi(written["path"])

    assert set(result.keys()) == {
        "summary",
        "notes",
        "total_note_count",
        "notes_truncated",
        "note_limit",
        "tempo",
        "time_sig",
        "key",
        "track_count",
    }
    assert isinstance(result["summary"], str)
    assert isinstance(result["notes"], list)
    assert result["note_limit"] == 500
    assert result["notes_truncated"] is False
    assert result["total_note_count"] == 8


def test_round_trip_preserves_tempo_time_sig_key(tmp_path):
    from midi_mcp.read_midi import read_midi
    from midi_mcp.write_midi import write_midi

    fx = _scale_fixture()
    fx["tempo"] = 96.0
    fx["time_sig"] = [3, 4]
    fx["key"] = "Bb"
    written = write_midi(**fx)

    result = read_midi(written["path"])
    assert result["tempo"] == pytest.approx(96.0, abs=1e-3)
    assert result["time_sig"] == [3, 4]
    assert result["key"] == "Bb"


def test_round_trip_preserves_note_count(tmp_path):
    from midi_mcp.read_midi import read_midi
    from midi_mcp.write_midi import write_midi

    written = write_midi(**_scale_fixture())
    result = read_midi(written["path"])
    # 8 notes written → 8 notes parseable from the file
    assert len(result["notes"]) == 8
    assert result["total_note_count"] == 8


def test_notes_truncate_at_limit(tmp_path):
    from midi_mcp.read_midi import read_midi
    from midi_mcp.write_midi import write_midi

    notes = [
        {"pitch": 60, "start": float(i) * 0.25, "duration": 0.25, "velocity": 80, "channel": 0}
        for i in range(600)
    ]
    fx = _scale_fixture()
    fx["tracks"] = [{"name": "many", "notes": notes}]
    fx["filename"] = "many_notes"
    written = write_midi(**fx)

    result = read_midi(written["path"])
    assert len(result["notes"]) == 500
    assert result["total_note_count"] == 600
    assert result["notes_truncated"] is True
    assert "TRUNCATED" in result["summary"]


def test_track_count_matches_written_file(tmp_path):
    from midi_mcp.read_midi import read_midi
    from midi_mcp.write_midi import write_midi

    written = write_midi(**_scale_fixture())
    result = read_midi(written["path"])
    # conductor + 1 note track
    assert result["track_count"] == 2


def test_missing_file_raises(tmp_path):
    from midi_mcp.read_midi import read_midi

    with pytest.raises(FileNotFoundError):
        read_midi(str(tmp_path / "nope.mid"))
