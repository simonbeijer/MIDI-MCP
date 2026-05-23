"""Chord symbol parser wrapping music21.harmony.ChordSymbol.

music21 is lazy-imported inside parse_chord; do not import it at module top.
"""

import re
from typing import Any

_FLAT_ROOT = re.compile(r"^([A-G])b")
_FLAT_BASS = re.compile(r"/([A-G])b")
_ALT_SUFFIX = re.compile(r"alt\b")


def _normalize_for_music21(symbol: str) -> str:
    """User chord vocab → music21's expected spelling.

    - Note-letter flats use `-` in music21 (e.g. `Bb` → `B-`); `b` after a note
      letter at start-of-string or after `/` is the only place this swap is safe
      (alteration suffixes like `b5`, `b9` already use `b` correctly).
    - `alt` is a jazz shorthand music21 does not recognize; expand to a textbook
      altered-dominant spelling (`#5b9`).
    """
    s = _FLAT_ROOT.sub(r"\1-", symbol)
    s = _FLAT_BASS.sub(r"/\1-", s)
    s = _ALT_SUFFIX.sub("#5b9", s)
    return s


def parse_chord(symbol: str) -> dict[str, Any]:
    """Parse a chord symbol.

    Returns on success::

        {
            "root":          int,        # pitch class 0-11
            "bass":          int,        # pitch class 0-11 (== root if no slash)
            "pitch_classes": set[int],   # pitch-class set (0-11)
            "pitches":       list[int],  # octave-resolved MIDI pitches, sorted
            "quality":       str,        # music21's quality label
            "tensions":      list[str],  # chord step modifications, e.g. ["add11"]
        }

    Returns on failure::

        {"warning": str}
    """
    if not isinstance(symbol, str) or not symbol.strip():
        return {"warning": f"empty or non-string chord symbol: {symbol!r}"}

    from music21 import harmony  # lazy: keep server cold-start fast

    normalized = _normalize_for_music21(symbol.strip())

    try:
        chord = harmony.ChordSymbol(normalized)
        pitches = list(chord.pitches)
    except Exception as exc:
        return {"warning": f"unparseable chord symbol {symbol!r}: {exc}"}

    if not pitches:
        return {"warning": f"unparseable chord symbol {symbol!r}: no pitches"}

    root_obj = chord.root()
    bass_obj = chord.bass()
    return {
        "root": root_obj.pitchClass,
        "bass": bass_obj.pitchClass if bass_obj is not None else root_obj.pitchClass,
        "pitch_classes": {p.pitchClass for p in pitches},
        "pitches": sorted(p.midi for p in pitches),
        "quality": chord.quality,
        "tensions": [f"{mod.modType}{mod.degree}" for mod in chord.chordStepModifications],
    }
