from typing import Any

from mcp.server.fastmcp import FastMCP

from .chord_track import chord_track as _chord_track
from .config import ensure_output_dir
from .freeform_track import freeform_track as _freeform_track
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
    project: str | None = None,
) -> dict[str, Any]:
    """Write tracks to a .mid file under MIDI_MCP_OUTPUT_DIR.

    Files land in `<output_dir>/<project>/` when `project` is given,
    otherwise in `<output_dir>/<YYYY-MM-DD>/` (today's date folder).
    Call list_outputs() first to see which project folders already exist
    so you can reuse one for ongoing work.

    Args:
        tracks: list of {name, instrument, notes}; notes are
            {pitch, start (beats), duration (beats), velocity, channel}.
        tempo: bpm (must be > 0).
        time_sig: [numerator, denominator], e.g. [4, 4].
        key: key signature string (e.g. "C", "Bb", "F#m"); invalid → warn + "C".
        filename: bare filename; path-like input is rejected.
        overwrite: if True, overwrite an existing file with the same name.
        project: optional project folder name. Sanitized like filenames
            (lowercase alnum/dash/underscore). When set, replaces the
            date folder. Reuses the folder if it already exists.

    Returns {path, warnings, summary, duration_seconds}.
    """
    return _write_midi(tracks, tempo, time_sig, key, filename, overwrite, project)


@mcp.tool()
def read_midi(path: str) -> dict[str, Any]:
    """Read a .mid file and return its structured contents.

    Returns {summary, notes, total_note_count, notes_truncated, note_limit,
    tempo, time_sig, key, track_count}. Notes are capped at `note_limit`
    (currently 500) to bound context size. When `notes_truncated` is True,
    `notes` holds the first 500 by start time and later notes are not
    returned — tell the user the read was partial.
    """
    return _read_midi(path)


@mcp.tool()
def list_outputs() -> dict[str, Any]:
    """List folders and .mid files in MIDI_MCP_OUTPUT_DIR.

    Returns `{folders, files}`:
    - `folders`: top-level subdirectory names (project folders + date folders).
    - `files`: `[{path, modified, size_bytes}, ...]` recursed one level deep.
      `path` is relative to MIDI_MCP_OUTPUT_DIR (e.g. "blues_demo/take.mid").

    Use the `folders` list to discover existing project names so you can
    reuse them when calling write_midi(project=...). Excludes dotfiles
    (seed .log) and non-.mid files.
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


@mcp.tool()
def freeform_track(
    notes: list[dict[str, Any]],
    channel: int,
    instrument: int | None = None,
) -> dict[str, Any]:
    """Validate caller-composed notes; no music theory applied.

    The style escape hatch: anything outside chord_track's rule-bound
    voicing palette (bass lines, melodies, leads) flows through here.
    The caller — typically the LLM — owns the melodic/rhythmic decisions.

    Args:
        notes: non-empty list of {pitch, start, duration, velocity[, channel]}.
            Pitch in [0, 127]; velocity in [1, 127]; start >= 0; duration > 0.
            A note that omits `channel` inherits the track-level `channel`.
        channel: default MIDI channel (0-15) when a note omits its own.
        instrument: optional GM program number (0-127). Echoed in the
            result so the caller can forward it into write_midi as the
            track's `instrument`.

    Returns {notes, instrument, summary}. notes are sorted by start.
    """
    return _freeform_track(notes=notes, channel=channel, instrument=instrument)


def run() -> None:
    ensure_output_dir()
    mcp.run()
