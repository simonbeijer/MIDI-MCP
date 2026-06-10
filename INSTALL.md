# MIDI-MCP — Install Guide (Mac)

Get MIDI-MCP running and connected to Claude Desktop. A few steps, mostly waiting.

You'll install:

1. Claude Desktop
2. `uv` (runs the MIDI server, brings its own Python — don't install Python separately)
3. The MIDI-MCP project folder

Then point Claude Desktop at it.

Commands in code blocks go in Terminal. Paste, press `Return`.

---

## Step 1 — Claude Desktop

Download from https://claude.ai/download. Drag into Applications. Launch once, sign in, quit.

---

## Step 2 — Open Terminal

`Cmd + Space`, type `Terminal`, `Return`.

---

## Step 3 — Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Close Terminal and open a new one** so the new tool is found. Confirm:

```bash
uv --version
```

If you see `command not found`, close and reopen Terminal again.

> `uv` includes Python. You do **not** need to install Python from python.org.

---

## Step 4 — Get the project

You need the MIDI-MCP folder somewhere on your Mac. Two options:

- **ZIP:** unzip it, drag the folder anywhere you'll remember (Documents is fine).
- **GitHub:** `cd` into a folder, then `git clone https://github.com/simonbeijer/MIDI-MCP.git`. If `git` isn't installed, run `xcode-select --install` first.

Then `cd` into the project folder and install its pieces:

```bash
cd /path/to/MIDI-MCP
uv sync
```

First run downloads Python + libraries (~100MB, 1–2 min on decent net, longer on slow).

Confirm the server starts:

```bash
uv run python -m midi_mcp
```

Cursor sits doing nothing = running and waiting. Press `Ctrl + C` to stop. No red error = good.

---

## Step 5 — Grab the two paths Claude Desktop needs

While still in the project folder:

```bash
pwd
which uv
```

Copy both outputs exactly. They look like:

```
/Users/yourname/Documents/MIDI-MCP
/Users/yourname/.local/bin/uv
```

---

## Step 6 — Tell Claude Desktop about the server

Open the config file:

```bash
open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

If TextEdit says the file doesn't exist:

```bash
mkdir -p ~/Library/Application\ Support/Claude
touch ~/Library/Application\ Support/Claude/claude_desktop_config.json
open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Paste this in, then **replace the two `<...>` placeholders** with the paths from Step 5. Pick any output folder you want for `MIDI_MCP_OUTPUT_DIR` — must be a full path starting with `/Users/`, never `~`.

```json
{
  "mcpServers": {
    "midi-mcp": {
      "command": "<UV_PATH>",
      "args": [
        "--directory",
        "<PROJECT_PATH>",
        "run",
        "python",
        "-m",
        "midi_mcp"
      ],
      "env": {
        "MIDI_MCP_OUTPUT_DIR": "/Users/yourname/Documents/MIDI-MCP/"
      }
    }
  }
}
```

Save (`Cmd + S`), close TextEdit.

---

## Step 7 — Restart Claude Desktop

Fully quit (`Cmd + Q` — closing the window is not enough). Reopen. Click the hammer icon in the chat box. You should see **midi-mcp** listed.

---

## Where do my files go?

In whatever folder you set as `MIDI_MCP_OUTPUT_DIR`, sorted into subfolders:

```
<output_dir>/<YYYY-MM-DD>/    # default — today's date
<output_dir>/<your_song>/     # if you name a song in chat
```

Folders are created automatically. Open in Finder.

---

## Try it

Once `midi-mcp` shows in the hammer menu, ask Claude things like:

- *"Make a bass line for 8 bars of C — F — G — C in 4/4 at 90 BPM, walking style."*
- *"Comp those same chords with a smooth jazz voicing on channel 2."*
- *"List the MIDI files I've generated so far."*

---

## If something breaks

- **midi-mcp missing from hammer menu** → fully quit Claude (`Cmd + Q`) and reopen. Then Settings → Developer → MCP for any error message.
- **`command not found: uv`** → close and reopen Terminal.
- **Config JSON paths** → always full path starting with `/Users/`, never `~`.
