"""Tests for chord_track: voicings, RNG, validation, snapshots.

Snapshots are byte-compares of the .mid file produced by piping
chord_track output through write_midi. To regenerate after an
intentional change:

    UPDATE_SNAPSHOTS=1 uv run pytest tests/test_chord_track.py -k snapshot
"""

import os
import warnings
from pathlib import Path

import pytest


SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

ALL_VOICINGS = [
    "drop2",
    "triad",
    "sustained_pad",
    "shell",
    "rootless",
    "power",
    "quartal",
]

# I-vi-IV-V in C, one chord per bar, 4 bars, 4/4. Fixed seed for
# deterministic snapshots.
_CHANGES = [
    {"bar": 1, "beat": 1.0, "symbol": "Cmaj7"},
    {"bar": 2, "beat": 1.0, "symbol": "Am7"},
    {"bar": 3, "beat": 1.0, "symbol": "Fmaj7"},
    {"bar": 4, "beat": 1.0, "symbol": "G7"},
]


def _fixture(voicing: str, seed: int = 1234) -> dict:
    return {
        "changes": _CHANGES,
        "bars": 4,
        "key": "C",
        "time_sig": [4, 4],
        "tempo": 120.0,
        "voicing": voicing,
        "seed": seed,
        "humanize": False,
    }


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDI_MCP_OUTPUT_DIR", str(tmp_path))
    yield tmp_path


# ----- Return shape -----------------------------------------------------------


def test_return_shape_notes_summary_seed():
    from midi_mcp.chord_track import chord_track

    result = chord_track(**_fixture("triad"))
    assert set(result.keys()) == {"notes", "summary", "seed"}
    assert isinstance(result["notes"], list)
    assert isinstance(result["summary"], str)
    assert isinstance(result["seed"], int)
    assert all(set(n) == {"pitch", "start", "duration", "velocity", "channel"} for n in result["notes"])


def test_seed_appears_in_summary():
    from midi_mcp.chord_track import chord_track

    result = chord_track(**_fixture("drop2", seed=42))
    assert "seed=42" in result["summary"]
    assert result["seed"] == 42


# ----- Voicing validation -----------------------------------------------------


def test_unknown_voicing_raises_with_allowed_list():
    from midi_mcp.chord_track import ALLOWED_VOICINGS, chord_track

    fx = _fixture("triad")
    fx["voicing"] = "not_a_voicing"
    with pytest.raises(ValueError) as exc:
        chord_track(**fx)
    msg = str(exc.value)
    assert "not_a_voicing" in msg
    for v in ALLOWED_VOICINGS:
        assert v in msg, f"allowed voicing {v!r} missing from error message"


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_each_voicing_produces_notes(voicing):
    from midi_mcp.chord_track import chord_track

    result = chord_track(**_fixture(voicing))
    assert len(result["notes"]) > 0


# ----- Property: pitch-class subset ------------------------------------------


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_pitch_classes_subset_of_chord_pcs(voicing):
    """Each chord region's notes must use only the chord's own pitch classes."""
    from midi_mcp.chord_track import chord_track
    from midi_mcp.theory.harmony import parse_chord

    result = chord_track(**_fixture(voicing))
    notes = result["notes"]
    beats_per_bar = 4.0
    for i, ch in enumerate(_CHANGES):
        start = (ch["bar"] - 1) * beats_per_bar + (ch["beat"] - 1)
        end = (
            (_CHANGES[i + 1]["bar"] - 1) * beats_per_bar + (_CHANGES[i + 1]["beat"] - 1)
            if i < len(_CHANGES) - 1
            else 4 * beats_per_bar
        )
        chord_pcs = parse_chord(ch["symbol"])["pitch_classes"]
        region_pcs = {n["pitch"] % 12 for n in notes if start <= n["start"] < end}
        assert region_pcs.issubset(chord_pcs), (
            f"{voicing} @ bar {ch['bar']}: region pcs {region_pcs} not subset of "
            f"chord {ch['symbol']} pcs {chord_pcs}"
        )


# ----- Property: rootless explicitly omits the chord root -------------------


def test_rootless_omits_chord_root():
    """rootless must not include the chord root pitch class in any region.

    The subset test allows root absence; this one asserts it.
    """
    from midi_mcp.chord_track import chord_track
    from midi_mcp.theory.harmony import parse_chord

    result = chord_track(**_fixture("rootless"))
    notes = result["notes"]
    beats_per_bar = 4.0
    for i, ch in enumerate(_CHANGES):
        start = (ch["bar"] - 1) * beats_per_bar + (ch["beat"] - 1)
        end = (
            (_CHANGES[i + 1]["bar"] - 1) * beats_per_bar + (_CHANGES[i + 1]["beat"] - 1)
            if i < len(_CHANGES) - 1
            else 4 * beats_per_bar
        )
        root_pc = parse_chord(ch["symbol"])["root"]
        region_pcs = {n["pitch"] % 12 for n in notes if start <= n["start"] < end}
        assert root_pc not in region_pcs, (
            f"rootless @ bar {ch['bar']} ({ch['symbol']}): root pc {root_pc} "
            f"present in {region_pcs}"
        )


# ----- Property: voicing-specific register -----------------------------------


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_pitches_within_voicing_register(voicing):
    from midi_mcp.chord_track import VOICING_REGISTER, chord_track

    lo, hi = VOICING_REGISTER[voicing]
    result = chord_track(**_fixture(voicing))
    for n in result["notes"]:
        assert lo <= n["pitch"] <= hi, (
            f"{voicing}: pitch {n['pitch']} outside register window [{lo}, {hi}]"
        )


# ----- Property: RNG isolation (same seed → same notes) ----------------------


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_same_seed_same_notes(voicing):
    from midi_mcp.chord_track import chord_track

    r1 = chord_track(**_fixture(voicing, seed=999))
    r2 = chord_track(**_fixture(voicing, seed=999))
    assert r1["notes"] == r2["notes"]
    assert r1["seed"] == r2["seed"] == 999


def test_rng_isolation_between_calls():
    """A second call with a different seed must not be perturbed by the first."""
    from midi_mcp.chord_track import chord_track

    r_a1 = chord_track(**_fixture("drop2", seed=1))
    _ = chord_track(**_fixture("drop2", seed=2))
    r_a2 = chord_track(**_fixture("drop2", seed=1))
    assert r_a1["notes"] == r_a2["notes"]


# ----- Property: bar coverage -------------------------------------------------


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_notes_span_bars(voicing):
    """Final chord must extend to end of `bars` (no premature stop)."""
    from midi_mcp.chord_track import chord_track

    result = chord_track(**_fixture(voicing))
    notes = result["notes"]
    total_beats = 4 * 4.0  # bars * beats_per_bar
    last_end = max(n["start"] + n["duration"] for n in notes)
    assert last_end == pytest.approx(total_beats, abs=1e-6), (
        f"{voicing}: last note ends at {last_end}, expected {total_beats}"
    )


# ----- Auto-seed + .log line --------------------------------------------------


def test_auto_seed_returned_and_logged(tmp_path):
    from midi_mcp.chord_track import chord_track

    fx = _fixture("triad")
    fx["seed"] = None
    result = chord_track(**fx)
    assert isinstance(result["seed"], int)
    assert f"seed={result['seed']}" in result["summary"]
    log_path = tmp_path / ".log"
    assert log_path.exists(), ".log file should be created on auto-seed"
    content = log_path.read_text()
    assert "chord_track" in content
    assert f"seed={result['seed']}" in content


def test_explicit_seed_does_not_log(tmp_path):
    from midi_mcp.chord_track import chord_track

    chord_track(**_fixture("triad", seed=7))
    log_path = tmp_path / ".log"
    assert not log_path.exists() or "seed=7" not in log_path.read_text()


# ----- Missing key handling ---------------------------------------------------


def test_missing_key_warns_and_uses_first_chord_root():
    from midi_mcp.chord_track import chord_track

    fx = _fixture("triad")
    fx["key"] = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = chord_track(**fx)
    msgs = [str(w.message) for w in caught]
    assert any("key missing" in m for m in msgs), f"no key-missing warning in {msgs}"
    # first chord is Cmaj7 → C major key
    assert "key=C" in result["summary"]


# ----- Snapshot tests ---------------------------------------------------------


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_voicing_snapshot(tmp_path, voicing):
    """Pipe chord_track output through write_midi; byte-compare the .mid file."""
    from midi_mcp.chord_track import chord_track
    from midi_mcp.write_midi import write_midi

    result = chord_track(**_fixture(voicing))
    write_result = write_midi(
        tracks=[{"name": f"chords_{voicing}", "notes": result["notes"]}],
        tempo=120.0,
        time_sig=[4, 4],
        key="C",
        filename=f"chord_track_{voicing}",
    )
    produced = Path(write_result["path"]).read_bytes()
    snap_path = SNAPSHOT_DIR / f"chord_track_{voicing}.mid"

    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not snap_path.exists():
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        snap_path.write_bytes(produced)
        pytest.skip(f"snapshot written at {snap_path}")

    expected = snap_path.read_bytes()
    assert produced == expected, (
        f"{voicing}: byte mismatch ({len(produced)}B vs {len(expected)}B). "
        f"If intentional, re-run with UPDATE_SNAPSHOTS=1."
    )


# ----- Humanize (slice 08) ---------------------------------------------------


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_humanize_true_differs_from_false(voicing):
    """Sanity: humanize=True must produce different notes than humanize=False."""
    from midi_mcp.chord_track import chord_track

    fx = _fixture(voicing, seed=1234)
    plain = chord_track(**fx)
    fx["humanize"] = True
    humanized = chord_track(**fx)
    assert humanized["notes"] != plain["notes"], (
        f"{voicing}: humanize=True did not change any note"
    )


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_humanize_deterministic_same_seed(voicing):
    from midi_mcp.chord_track import chord_track

    fx = _fixture(voicing, seed=2024)
    fx["humanize"] = True
    r1 = chord_track(**fx)
    r2 = chord_track(**fx)
    assert r1["notes"] == r2["notes"]


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_humanize_start_not_before_bar_downbeat(voicing):
    from midi_mcp.chord_track import chord_track

    fx = _fixture(voicing, seed=2024)
    fx["humanize"] = True
    result = chord_track(**fx)
    beats_per_bar = 4.0
    for n in result["notes"]:
        bar_index = int(n["start"] // beats_per_bar)
        bar_start = bar_index * beats_per_bar
        assert n["start"] >= bar_start - 1e-9, (
            f"{voicing}: humanized start {n['start']} earlier than bar downbeat "
            f"{bar_start}"
        )


@pytest.mark.parametrize("voicing", ALL_VOICINGS)
def test_humanize_snapshot(tmp_path, voicing):
    """Pipe humanized chord_track output through write_midi; byte-compare."""
    from midi_mcp.chord_track import chord_track
    from midi_mcp.write_midi import write_midi

    fx = _fixture(voicing, seed=1234)
    fx["humanize"] = True
    result = chord_track(**fx)
    write_result = write_midi(
        tracks=[{"name": f"chords_{voicing}_h", "notes": result["notes"]}],
        tempo=120.0,
        time_sig=[4, 4],
        key="C",
        filename=f"chord_track_humanize_{voicing}",
    )
    produced = Path(write_result["path"]).read_bytes()
    snap_path = SNAPSHOT_DIR / f"chord_track_humanize_{voicing}.mid"

    if os.environ.get("UPDATE_SNAPSHOTS") == "1" or not snap_path.exists():
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        snap_path.write_bytes(produced)
        pytest.skip(f"snapshot written at {snap_path}")

    expected = snap_path.read_bytes()
    assert produced == expected, (
        f"{voicing} humanize: byte mismatch ({len(produced)}B vs {len(expected)}B). "
        f"If intentional, re-run with UPDATE_SNAPSHOTS=1."
    )


# ----- No random import leakage into pure-data modules -----------------------


def test_chord_track_module_owns_random_import():
    """random is allowed in chord_track.py (seeded RNG lives here)."""
    src = Path(__file__).resolve().parents[1] / "src" / "midi_mcp" / "chord_track.py"
    text = src.read_text()
    assert "import random" in text, "chord_track.py must own its seeded RNG"
