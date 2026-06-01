# MIDI-MCP — Install Guide (Mac, non-technical)

This guide walks a fresh Mac through installing MIDI-MCP and connecting it to Claude Desktop. No prior coding setup is assumed. Copy and paste each command exactly.

You will install four things:

1. Claude Desktop (the app you chat with)
2. Command Line Tools (a one-time Apple install needed by the rest)
3. `uv` (a small tool that runs the MIDI server)
4. The MIDI-MCP project itself

Then you tell Claude Desktop where to find it. Total time: about 15 minutes.

---

## Step 1 — Install Claude Desktop

1. Go to https://claude.ai/download
2. Download the macOS version.
3. Open the `.dmg` and drag **Claude** into **Applications**.
4. Launch Claude once and sign in. Quit it again.

---

## Step 2 — Open Terminal

Press `Cmd + Space`, type `Terminal`, press `Return`. A black or white window opens. This is where you paste commands. You press `Return` after each one.

---

## Step 3 — Install Apple Command Line Tools

Paste this and press `Return`:

```bash
xcode-select --install
```

A popup appears. Click **Install**. Wait for it to finish (a few minutes). If it says "already installed", skip ahead.

---

## Step 4 — Install `uv`

`uv` is the tool that will run the MIDI server. Paste this and press `Return`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

When it finishes, **close Terminal and open a new one** so the new tool is found.

Check it worked:

```bash
uv --version
```

You should see something like `uv 0.5.x`. If you see "command not found", restart Terminal again.

---

## Step 5 — Download MIDI-MCP

Pick a folder you'll remember. We'll use your Documents folder.

```bash
cd ~/Documents
git clone https://github.com/simonbeijer/MIDI-MCP.git
cd MIDI-MCP
```

> If you were given a ZIP instead, double-click it, drag the unzipped folder into `Documents`, then in Terminal type `cd ~/Documents/MIDI-MCP`.

Install the project's pieces:

```bash
uv sync
```

This downloads Python and the music libraries. First run takes a minute or two.

Confirm the server starts:

```bash
uv run python -m midi_mcp
```

The cursor will sit there doing nothing — that means it's running and waiting. Press `Ctrl + C` to stop it. If you saw no red error text, you're good.

---

## Step 6 — Find your project path

You need the full path so Claude Desktop knows where to look. Paste:

```bash
pwd
```

It will print something like `/Users/yourname/Documents/MIDI-MCP`. **Copy that line — you'll need it in the next step.**

---

## Step 7 — Tell Claude Desktop about the server

Open the Claude config file in TextEdit:

```bash
open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

If TextEdit says the file doesn't exist, create it first:

```bash
mkdir -p ~/Library/Application\ Support/Claude
touch ~/Library/Application\ Support/Claude/claude_desktop_config.json
open -a TextEdit ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Paste this into the file:

```json
{
  "mcpServers": {
    "midi-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/yourname/Documents/MIDI-MCP",
        "run",
        "python",
        "-m",
        "midi_mcp"
      ],
      "env": {
        "MIDI_MCP_OUTPUT_DIR": "~/Documents/MIDI-MCP/"
      }
    }
  }
}
```

**Replace `/Users/yourname/Documents/MIDI-MCP` with the path you copied in Step 6.** The path must be the full one (starting with `/Users/`), not `~/Documents/...`.

Save (`Cmd + S`) and close TextEdit.

---

## Step 8 — Point `uv` at the right place

Claude Desktop runs apps in a stripped-down environment and may not find `uv`. Fix it by giving the full path:

```bash
which uv
```

Copy what it prints (e.g. `/Users/yourname/.local/bin/uv`). In the config file from Step 7, replace `"command": "uv"` with the full path, e.g. `"command": "/Users/yourname/.local/bin/uv"`. Save again.

---

## Step 9 — Restart Claude Desktop

Fully quit Claude (`Cmd + Q` — closing the window is not enough). Reopen it.

Click the small tools/hammer icon in the chat box. You should see **midi-mcp** listed with its tools. If it's missing, open the Claude **Settings → Developer → MCP** view to read any error message.

---

## Where do my files go?

Generated `.mid` files appear in:

```
~/Documents/MIDI-MCP/<YYYY-MM-DD>/    # default — today's date folder
~/Documents/MIDI-MCP/<your_song>/     # if Claude knows the song name
```

By default each day gets its own folder so today's work is easy to find. If you tell Claude something like "save it in the blues demo project", it groups all takes for that song together across days. Open the parent folder in Finder.

---

## Quick start — useful prompts

Once Claude Desktop shows the midi-mcp tools, you can ask it things like:

- *"Make a bass line for 8 bars of C — F — G — C in 4/4 at 90 BPM, walking style."*
- *"Comp those same chords with a smooth jazz voicing on channel 2."*
- *"List the MIDI files I've generated so far."*
- *"Read back the notes in my last bass file."*

Claude will pick the right tool, write the `.mid`, and tell you the filename.

### Optional — make a reusable starter prompt

You don't need to remember the exact tool names. Save a personal prompt template in Claude Desktop (Settings → Profile → Custom instructions, or pin it as a project) like:

```
When I describe music, use the midi-mcp tools to generate the file.
Default to 4/4, 90 BPM, channel 1 unless I say otherwise.
After writing each file, tell me the filename and the seed.
```

That way every new chat already knows how you like to work, and you can just type *"4 bars of Am G F E, walking bass"* and get a file back.

---

That's it. If something breaks, the most common fix is **fully quitting Claude Desktop** and reopening it after any config change.
