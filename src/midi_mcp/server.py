from typing import Any

from mcp.server.fastmcp import FastMCP

from .chord_track import chord_track as _chord_track
from .config import ensure_output_dir
from .list_outputs import list_outputs as _list_outputs
from .read_midi import read_midi as _read_midi
from .transpose import transpose as _transpose
from .write_midi import write_midi as _write_midi

mcp = FastMCP("midi-mcp")


@mcp.tool()
def write_midi(
    tracks: list[dict[str, Any]],
    tempo: float,
    time_sig: list[int],
    key: str,
    filename: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write tracks to a .mid file under MIDI_MCP_OUTPUT_DIR.

    Args:
        tracks: list of {name, instrument, notes}; notes are
            {pitch, start (beats), duration (beats), velocity, channel}.
        tempo: bpm (must be > 0).
        time_sig: [numerator, denominator], e.g. [4, 4].
        key: key signature string (e.g. "C", "Bb", "F#m"); invalid → warn + "C".
        filename: bare filename; path-like input is rejected.
        overwrite: if True, overwrite an existing file with the same name.

    Returns {path, warnings, summary, duration_seconds}.
    """
    return _write_midi(tracks, tempo, time_sig, key, filename, overwrite)


@mcp.tool()
def read_midi(path: str) -> dict[str, Any]:
    """Read a .mid file and return its structured contents.

    Returns {summary, first_50_notes, tempo, time_sig, key, track_count}.
    Notes are truncated to the first 50 to bound context size.
    """
    return _read_midi(path)


@mcp.tool()
def list_outputs() -> list[dict[str, Any]]:
    """List .mid files in MIDI_MCP_OUTPUT_DIR.

    Returns [{filename, modified, size_bytes}, ...]. Excludes dotfiles
    (including the seed .log) and any non-.mid files.
    """
    return _list_outputs()


@mcp.tool()
def transpose(notes: list[dict[str, Any]], semitones: int) -> list[dict[str, Any]]:
    """Shift each note's pitch by `semitones`. Returns the new notes list.

    Operates on the data-contract notes list (not on a file). Pitches outside
    [0, 127] after the shift are clamped and a warning is emitted.
    """
    return _transpose(notes, semitones)


@mcp.tool()
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
    """Render a chord progression to a voiced notes list.

    Args:
        changes: list of {bar, beat, symbol}; bar/beat are 1-based, beat is float.
        bars: total length in bars (required; NOT inferred from max bar).
        key: key signature; if missing, defaults to first-chord root as major + warn.
        time_sig: [numerator, denominator]; numerator = beats-per-bar.
        tempo: bpm (passed through; rendering itself is tempo-independent).
        voicing: REQUIRED. One of "drop2", "triad", "sustained_pad",
            "shell", "rootless", "power", "quartal". Unknown values raise
            ValueError listing the allowed set.
        seed: RNG seed; auto-generated if missing and written to .log.
        humanize: accepted; True path is wired in a later slice.

    Returns {notes, summary, seed}.
    """
    return _chord_track(
        changes=changes,
        bars=bars,
        key=key,
        time_sig=time_sig,
        tempo=tempo,
        voicing=voicing,
        seed=seed,
        humanize=humanize,
    )


def run() -> None:
    ensure_output_dir()
    mcp.run()
