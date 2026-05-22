import os
from pathlib import Path

TICKS_PER_BEAT = 480

_DEFAULT_OUTPUT_DIR = "~/MIDI-MCP/output/"


def output_dir() -> Path:
    raw = os.environ.get("MIDI_MCP_OUTPUT_DIR", _DEFAULT_OUTPUT_DIR)
    return Path(raw).expanduser()


def ensure_output_dir() -> Path:
    path = output_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
