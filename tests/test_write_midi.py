"""Snapshot + behavior tests for write_midi.

The snapshot is a binary byte-compare against a checked-in .mid file.
We do not parse-and-compare notes; the point is to lock the exact bytes
Logic Pro will see, catching mido upgrades / rounding / meta-order drift.

To regenerate the snapshot after an intentional format change:
    UPDATE_SNAPSHOTS=1 uv run pytest tests/test_write_midi.py::test_c_major_scale_snapshot
"""

import os
from pathlib import Path

import pytest


SNAPSHOT_DIR = Path(__file__).parent / "snapshots"
SNAPSHOT_PATH = SNAPSHOT_DIR / "c_major_scale.mid"


def _c_major_scale_fixture() -> dict:
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
        "filename": "c_major_scale",
    }


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDI_MCP_OUTPUT_DIR", str(tmp_path))
    yield tmp_path


def test_c_major_scale_snapshot(tmp_path):
    from midi_mcp.write_midi import write_midi

    fx = _c_major_scale_fixture()
    result = write_midi(**fx)
    out_path = Path(result["path"])
    produced = out_path.read_bytes()

    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not SNAPSHOT_PATH.exists():
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_bytes(produced)
        pytest.skip(f"snapshot {'updated' if SNAPSHOT_PATH.exists() else 'created'} at {SNAPSHOT_PATH}")

    expected = SNAPSHOT_PATH.read_bytes()
    assert produced == expected, (
        f"byte mismatch: {len(produced)}B produced vs {len(expected)}B snapshot. "
        f"If the change is intentional, re-run with UPDATE_SNAPSHOTS=1."
    )


def test_return_shape_has_path_warnings_summary_duration(tmp_path):
    from midi_mcp.write_midi import write_midi

    fx = _c_major_scale_fixture()
    result = write_midi(**fx)
    assert set(result.keys()) == {"path", "warnings", "summary", "duration_seconds"}
    assert isinstance(result["path"], str)
    assert isinstance(result["warnings"], list)
    assert isinstance(result["summary"], str)
    assert isinstance(result["duration_seconds"], float)
    # 8 quarter notes at 120 bpm = 8 beats = 4 seconds
    assert result["duration_seconds"] == pytest.approx(4.0, abs=1e-6)


def test_track_0_is_conductor_only(tmp_path):
    """Track 0 has no note_on/note_off; notes appear from track 1 onward."""
    import mido

    from midi_mcp.write_midi import write_midi

    result = write_midi(**_c_major_scale_fixture())
    mid = mido.MidiFile(result["path"])
    assert len(mid.tracks) >= 2, "must have conductor + at least one note track"
    note_msgs_t0 = [m for m in mid.tracks[0] if m.type in ("note_on", "note_off")]
    assert note_msgs_t0 == [], "track 0 must be conductor-only (no note events)"
    note_msgs_t1 = [m for m in mid.tracks[1] if m.type in ("note_on", "note_off")]
    assert len(note_msgs_t1) > 0, "track 1 must contain notes"


def test_meta_event_order_at_track_0(tmp_path):
    """Track 0 meta order: set_tempo → time_signature → key_signature → end_of_track."""
    import mido

    from midi_mcp.write_midi import write_midi

    result = write_midi(**_c_major_scale_fixture())
    mid = mido.MidiFile(result["path"])
    types = [m.type for m in mid.tracks[0]]
    expected_order = ["set_tempo", "time_signature", "key_signature", "end_of_track"]
    # filter to the four we care about, preserving order
    seen = [t for t in types if t in expected_order]
    assert seen == expected_order, f"meta order wrong: {seen}"


def test_uses_real_note_off_not_velocity_zero(tmp_path):
    import mido

    from midi_mcp.write_midi import write_midi

    result = write_midi(**_c_major_scale_fixture())
    mid = mido.MidiFile(result["path"])
    for track in mid.tracks[1:]:
        for msg in track:
            if msg.type == "note_on":
                assert msg.velocity > 0, "note_on with velocity=0 used instead of note_off"


def test_path_like_filename_rejected(tmp_path):
    from midi_mcp.paths import PathRejected
    from midi_mcp.write_midi import write_midi

    fx = _c_major_scale_fixture()
    fx["filename"] = "../../etc/passwd"
    with pytest.raises(PathRejected):
        write_midi(**fx)
    assert list(tmp_path.iterdir()) == []


def test_collision_auto_suffix(tmp_path):
    from midi_mcp.write_midi import write_midi

    fx = _c_major_scale_fixture()
    r1 = write_midi(**fx)
    r2 = write_midi(**fx)
    r3 = write_midi(**fx)
    assert Path(r1["path"]).name == "c_major_scale.mid"
    assert Path(r2["path"]).name == "c_major_scale-2.mid"
    assert Path(r3["path"]).name == "c_major_scale-3.mid"


def test_overwrite_true_reuses_name(tmp_path):
    from midi_mcp.write_midi import write_midi

    fx = _c_major_scale_fixture()
    r1 = write_midi(**fx)
    fx["overwrite"] = True
    r2 = write_midi(**fx)
    assert r1["path"] == r2["path"]
    target_dir = Path(r2["path"]).parent
    assert list(target_dir.iterdir()) == [Path(r2["path"])]


def test_project_folder_routes_file_into_project_dir(tmp_path):
    from midi_mcp.write_midi import write_midi

    fx = _c_major_scale_fixture()
    fx["project"] = "blues_demo"
    result = write_midi(**fx)
    out_path = Path(result["path"])
    assert out_path.parent == tmp_path / "blues_demo"
    assert out_path.exists()


def test_default_routes_to_today_date_folder(tmp_path):
    from datetime import date

    from midi_mcp.write_midi import write_midi

    result = write_midi(**_c_major_scale_fixture())
    out_path = Path(result["path"])
    assert out_path.parent == tmp_path / date.today().isoformat()


def test_invalid_key_warns_and_defaults_to_C(tmp_path):
    from midi_mcp.write_midi import write_midi

    fx = _c_major_scale_fixture()
    fx["key"] = "Q"
    result = write_midi(**fx)
    assert any("invalid key" in w for w in result["warnings"])
    assert "key C" in result["summary"]


def test_no_random_import_in_write_midi_module():
    src = Path(__file__).resolve().parents[1] / "src" / "midi_mcp" / "write_midi.py"
    text = src.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("import random"), (
            f"`import random` found in write_midi.py: {line!r}"
        )
        assert not stripped.startswith("from random"), (
            f"`from random` found in write_midi.py: {line!r}"
        )


def test_no_random_import_in_midi_io_module():
    src = Path(__file__).resolve().parents[1] / "src" / "midi_mcp" / "midi_io.py"
    text = src.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("import random"), (
            f"`import random` found in midi_io.py: {line!r}"
        )
        assert not stripped.startswith("from random"), (
            f"`from random` found in midi_io.py: {line!r}"
        )
