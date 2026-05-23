from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import ensure_output_dir
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


def run() -> None:
    ensure_output_dir()
    mcp.run()
