"""Tests for bass_line: walking style only in slice 07a.

Snapshots are byte-compares of the .mid file produced by piping
bass_line output through write_midi. To regenerate after an
intentional change:

    UPDATE_SNAPSHOTS=1 uv run pytest tests/test_bass_line.py -k snapshot
"""

import os
import warnings
from pathlib import Path

import pytest


SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

ALL_STYLES = ["walking"]

_CHANGES = [
    {"bar": 1, "beat": 1.0, "symbol": "Cmaj7"},
    {"bar": 2, "beat": 1.0, "symbol": "Am7"},
    {"bar": 3, "beat": 1.0, "symbol": "Fmaj7"},
    {"bar": 4, "beat": 1.0, "symbol": "G7"},
]


def _fixture(style: str, seed: int = 1234) -> dict:
    return {
        "changes": _CHANGES,
        "bars": 4,
        "key": "C",
        "time_sig": [4, 4],
        "tempo": 120.0,
        "style": style,
        "swing": None,
        "seed": seed,
        "humanize": False,
    }


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDI_MCP_OUTPUT_DIR", str(tmp_path))
    yield tmp_path


# ----- Return shape -----------------------------------------------------------


def test_return_shape_notes_summary_seed():
    from midi_mcp.bass_line import bass_line

    result = bass_line(**_fixture("walking"))
    assert set(result.keys()) == {"notes", "summary", "seed"}
    assert isinstance(result["notes"], list)
    assert isinstance(result["summary"], str)
    assert isinstance(result["seed"], int)
    assert all(
        set(n) == {"pitch", "start", "duration", "velocity", "channel"}
        for n in result["notes"]
    )


def test_seed_appears_in_summary():
    from midi_mcp.bass_line import bass_line

    result = bass_line(**_fixture("walking", seed=42))
    assert "seed=42" in result["summary"]
    assert result["seed"] == 42


# ----- Style validation ------------------------------------------------------


def test_unknown_style_raises_with_allowed_list():
    from midi_mcp.bass_line import ALLOWED_STYLES, bass_line

    fx = _fixture("walking")
    fx["style"] = "not_a_style"
    with pytest.raises(ValueError) as exc:
        bass_line(**fx)
    msg = str(exc.value)
    assert "not_a_style" in msg
    for s in ALLOWED_STYLES:
        assert s in msg, f"allowed style {s!r} missing from error message"


@pytest.mark.parametrize("style", ALL_STYLES)
def test_each_style_produces_notes(style):
    from midi_mcp.bass_line import bass_line

    result = bass_line(**_fixture(style))
    assert len(result["notes"]) > 0


# ----- Property: walking beat-1 is chord tone --------------------------------


def test_walking_beat_one_is_chord_tone():
    """Beat 1 of each bar must use a pitch class in that bar's chord."""
    from midi_mcp.bass_line import bass_line
    from midi_mcp.theory.harmony import parse_chord

    result = bass_line(**_fixture("walking"))
    notes = result["notes"]
    beats_per_bar = 4.0
    for ch in _CHANGES:
        bar_start = (ch["bar"] - 1) * beats_per_bar
        chord_pcs = parse_chord(ch["symbol"])["pitch_classes"]
        beat_one = [n for n in notes if n["start"] == pytest.approx(bar_start)]
        assert beat_one, f"no note on beat 1 of bar {ch['bar']}"
        for n in beat_one:
            assert n["pitch"] % 12 in chord_pcs, (
                f"bar {ch['bar']} beat 1 pitch {n['pitch']} (pc {n['pitch'] % 12}) "
                f"not in chord {ch['symbol']} pcs {chord_pcs}"
            )


# ----- Property: grid alignment, no cross-barline ----------------------------


@pytest.mark.parametrize("style", ALL_STYLES)
def test_starts_on_grid_and_within_bars(style):
    """With humanize=False every start is on the integer-beat grid (4/4 here)
    and no note crosses a barline."""
    from midi_mcp.bass_line import bass_line

    result = bass_line(**_fixture(style))
    beats_per_bar = 4.0
    total_beats = 4 * beats_per_bar
    for n in result["notes"]:
        assert n["start"] == pytest.approx(round(n["start"])), (
            f"{style}: start {n['start']} not on integer-beat grid"
        )
        bar_index = int(n["start"] // beats_per_bar)
        bar_end = (bar_index + 1) * beats_per_bar
        end = n["start"] + n["duration"]
        assert end <= bar_end + 1e-9, (
            f"{style}: note start={n['start']} dur={n['duration']} crosses "
            f"barline at {bar_end}"
        )
        assert end <= total_beats + 1e-9


# ----- Property: register window ---------------------------------------------


@pytest.mark.parametrize("style", ALL_STYLES)
def test_pitches_within_register(style):
    from midi_mcp.bass_line import BASS_REGISTER, bass_line

    lo, hi = BASS_REGISTER[style]
    result = bass_line(**_fixture(style))
    for n in result["notes"]:
        assert lo <= n["pitch"] <= hi, (
            f"{style}: pitch {n['pitch']} outside register [{lo}, {hi}]"
        )


# ----- Property: determinism --------------------------------------------------


@pytest.mark.parametrize("style", ALL_STYLES)
def test_same_seed_same_notes(style):
    from midi_mcp.bass_line import bass_line

    r1 = bass_line(**_fixture(style, seed=999))
    r2 = bass_line(**_fixture(style, seed=999))
    assert r1["notes"] == r2["notes"]
    assert r1["seed"] == r2["seed"] == 999


def test_rng_isolation_between_calls():
    from midi_mcp.bass_line import bass_line

    r_a1 = bass_line(**_fixture("walking", seed=1))
    _ = bass_line(**_fixture("walking", seed=2))
    r_a2 = bass_line(**_fixture("walking", seed=1))
    assert r_a1["notes"] == r_a2["notes"]


# ----- Property: bar coverage -------------------------------------------------


@pytest.mark.parametrize("style", ALL_STYLES)
def test_notes_span_bars(style):
    """Final note must reach the end of `bars` (no premature stop)."""
    from midi_mcp.bass_line import bass_line

    result = bass_line(**_fixture(style))
    notes = result["notes"]
    total_beats = 4 * 4.0
    last_end = max(n["start"] + n["duration"] for n in notes)
    assert last_end == pytest.approx(total_beats, abs=1e-6), (
        f"{style}: last note ends at {last_end}, expected {total_beats}"
    )


# ----- Auto-seed + .log line --------------------------------------------------


def test_auto_seed_returned_and_logged(tmp_path):
    from midi_mcp.bass_line import bass_line

    fx = _fixture("walking")
    fx["seed"] = None
    result = bass_line(**fx)
    assert isinstance(result["seed"], int)
    assert f"seed={result['seed']}" in result["summary"]
    log_path = tmp_path / ".log"
    assert log_path.exists(), ".log file should be created on auto-seed"
    content = log_path.read_text()
    assert "bass_line" in content
    assert f"seed={result['seed']}" in content


def test_explicit_seed_does_not_log(tmp_path):
    from midi_mcp.bass_line import bass_line

    bass_line(**_fixture("walking", seed=7))
    log_path = tmp_path / ".log"
    assert not log_path.exists() or "seed=7" not in log_path.read_text()


# ----- Missing key handling ---------------------------------------------------


def test_missing_key_warns_and_uses_first_chord_root():
    from midi_mcp.bass_line import bass_line

    fx = _fixture("walking")
    fx["key"] = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = bass_line(**fx)
    msgs = [str(w.message) for w in caught]
    assert any("key missing" in m for m in msgs), f"no key-missing warning in {msgs}"
    assert "key=C" in result["summary"]


# ----- Snapshot tests ---------------------------------------------------------


@pytest.mark.parametrize("style", ALL_STYLES)
def test_style_snapshot(tmp_path, style):
    """Pipe bass_line output through write_midi; byte-compare the .mid file."""
    from midi_mcp.bass_line import bass_line
    from midi_mcp.write_midi import write_midi

    result = bass_line(**_fixture(style))
    write_result = write_midi(
        tracks=[{"name": f"bass_{style}", "notes": result["notes"]}],
        tempo=120.0,
        time_sig=[4, 4],
        key="C",
        filename=f"bass_line_{style}",
    )
    produced = Path(write_result["path"]).read_bytes()
    snap_path = SNAPSHOT_DIR / f"bass_line_{style}.mid"

    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not snap_path.exists():
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        snap_path.write_bytes(produced)
        pytest.skip(f"snapshot written at {snap_path}")

    expected = snap_path.read_bytes()
    assert produced == expected, (
        f"{style}: byte mismatch ({len(produced)}B vs {len(expected)}B). "
        f"If intentional, re-run with UPDATE_SNAPSHOTS=1."
    )


# ----- Module owns random ----------------------------------------------------


def test_bass_line_module_owns_random_import():
    src = Path(__file__).resolve().parents[1] / "src" / "midi_mcp" / "bass_line.py"
    text = src.read_text()
    assert "import random" in text, "bass_line.py must own its seeded RNG"
