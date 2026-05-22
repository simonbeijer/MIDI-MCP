# MIDI-MCP

Local MCP server that generates `.mid` files (bass lines, voiced chord comps) from natural-language prompts in Claude Desktop. Drag the file into Logic Pro and keep working.

Status: v1 in progress. Slice 01 ships the empty FastMCP stdio server; no tools registered yet.

## Requirements

- macOS
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Claude Desktop

## Setup

```bash
uv sync
```

Run the server directly to confirm it starts (it will block on stdio — `Ctrl+C` to exit):

```bash
uv run python -m midi_mcp
```

Tests:

```bash
uv run pytest
```

## Claude Desktop wiring

Add an entry to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "midi-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/MIDI-MCP",
        "run",
        "python",
        "-m",
        "midi_mcp"
      ],
      "env": {
        "MIDI_MCP_OUTPUT_DIR": "~/MIDI-MCP/output/"
      }
    }
  }
}
```

Replace `/ABSOLUTE/PATH/TO/MIDI-MCP` with the absolute path to this checkout. Restart Claude Desktop after editing. The server appears under MCP integrations; in slice 01 it exposes zero tools (the connection itself is what we are validating).

## Configuration

- `MIDI_MCP_OUTPUT_DIR` — directory for written `.mid` files and the seed log. Default `~/MIDI-MCP/output/`. Created on startup if missing.
- `ticks_per_beat` is fixed at 480 (see `src/midi_mcp/config.py`).

## Layout

```
src/midi_mcp/      # package (FastMCP entry, config)
tests/             # pytest
tests/snapshots/   # binary .mid snapshots (added in later slices)
.scratch/          # internal issue tracker (gitignored)
docs/              # ADRs and agent docs
```
