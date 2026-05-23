"""Tests for midi_mcp.theory.harmony.parse_chord."""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


SUCCESS_KEYS = {"root", "bass", "pitch_classes", "pitches", "quality", "tensions"}

# (symbol, expected_root_pc, expected_bass_pc, must_contain_pcs)
PARSE_TABLE = [
    ("Bb7",       10, 10, {10, 2, 5, 8}),     # Bb D F Ab
    ("Cm7b5",      0,  0, {0, 3, 6, 10}),     # C Eb Gb Bb
    ("F7alt",      5,  5, {5, 9, 6}),         # F A + tritone (alt expansion adds #5/b9)
    ("Gmaj7#11",   7,  7, {7, 11, 2, 6, 1}),  # G B D F# C#
    ("D/F#",       2,  6, {2, 6, 9}),         # D F# A; bass = F#
    ("Bbmaj7",    10, 10, {10, 2, 5, 9}),     # Bb D F A
    ("Cdim7",      0,  0, {0, 3, 6, 9}),      # C Eb Gb Bbb(=A)
    ("F7#5",       5,  5, {5, 9, 1, 3}),      # F A C# Eb
    ("Csus2",      0,  0, {0, 2, 7}),         # C D G
    ("Am",         9,  9, {9, 0, 4}),         # A C E
    ("G/B",        7, 11, {7, 11, 2}),        # G B D; bass = B
]


@pytest.mark.parametrize("symbol,root,bass,pcs", PARSE_TABLE)
def test_parse_chord_shape(symbol, root, bass, pcs):
    from midi_mcp.theory.harmony import parse_chord

    result = parse_chord(symbol)
    assert "warning" not in result, f"unexpected warning for {symbol!r}: {result}"
    assert set(result.keys()) == SUCCESS_KEYS
    assert result["root"] == root, f"{symbol}: root pc"
    assert result["bass"] == bass, f"{symbol}: bass pc"
    assert pcs.issubset(result["pitch_classes"]), (
        f"{symbol}: expected pcs {pcs} subset of {result['pitch_classes']}"
    )
    assert isinstance(result["pitches"], list)
    assert all(isinstance(p, int) for p in result["pitches"])
    assert isinstance(result["quality"], str)
    assert isinstance(result["tensions"], list)


def test_slash_chord_bass_differs_from_root():
    from midi_mcp.theory.harmony import parse_chord

    result = parse_chord("D/F#")
    assert result["root"] != result["bass"]
    assert result["root"] == 2
    assert result["bass"] == 6


@pytest.mark.parametrize("symbol", ["Bbz7", "", "   ", "xyz", "!!@@", "9999"])
def test_parse_chord_failures_return_warning(symbol):
    from midi_mcp.theory.harmony import parse_chord

    result = parse_chord(symbol)
    assert "warning" in result, f"{symbol!r} should have warned, got {result}"
    assert isinstance(result["warning"], str)


def test_no_music21_import_at_module_top():
    """grep: music21 must not appear at top-level in the harmony module."""
    src = Path(__file__).resolve().parents[1] / "src" / "midi_mcp" / "theory" / "harmony.py"
    text = src.read_text()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import music21") or stripped.startswith("from music21"):
            # only fail if at indent 0 (module top)
            if line == stripped:
                pytest.fail(f"music21 imported at module top: {line!r}")


def test_lazy_import_first_call_triggers_music21():
    """Subprocess: fresh interpreter, importing the module must NOT load music21.

    Calling parse_chord must then load it. Second call must not re-load.
    """
    code = textwrap.dedent(
        """
        import sys
        from midi_mcp.theory import harmony
        before = "music21" in sys.modules
        harmony.parse_chord("Cmaj7")
        after_first = "music21" in sys.modules
        m1 = sys.modules["music21"]
        harmony.parse_chord("Dm7")
        m2 = sys.modules["music21"]
        print(f"{before}|{after_first}|{m1 is m2}")
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    before, after_first, same_module = proc.stdout.strip().split("|")
    assert before == "False", "music21 was imported by `from midi_mcp.theory import harmony` (should be lazy)"
    assert after_first == "True", "first parse_chord call should have imported music21"
    assert same_module == "True", "second call should reuse the cached music21 module"
