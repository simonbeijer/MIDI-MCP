"""Tests for midi_mcp.paths: sanitize, reject path-like, auto-suffix."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDI_MCP_OUTPUT_DIR", str(tmp_path))
    yield tmp_path


SANITIZE_TABLE = [
    ("Lo-fi Loop åäö",        "lo-fi_loop_aao"),
    ("Indie G Open Voicings", "indie_g_open_voicings"),
    ("UPPER CASE",            "upper_case"),
    ("file.mid",              "file"),
    ("Track 01.MIDI",         "track_01"),
    ("!!@@##",                "untitled"),
    ("",                      "untitled"),
    ("a" * 100,               "a" * 60),
    ("naïve café",            "naive_cafe"),
    ("Ångström",              "angstrom"),
]


@pytest.mark.parametrize("raw,expected", SANITIZE_TABLE)
def test_sanitize_basename(raw, expected):
    from midi_mcp.paths import sanitize_basename

    assert sanitize_basename(raw) == expected


REJECT_TABLE = [
    "../../etc/passwd",
    "/tmp/x",
    "~/secret",
    "~user/x",
    r"C:\Windows\notes",
    "subdir/file",
    r"a\b",
]


@pytest.mark.parametrize("raw", REJECT_TABLE)
def test_resolve_output_rejects_path_like(raw, tmp_path):
    from midi_mcp.paths import PathRejected, resolve_output

    with pytest.raises(PathRejected) as exc:
        resolve_output(raw)
    assert exc.value.suggestion
    assert exc.value.suggestion == exc.value.suggestion.lower()
    # message includes a suggestion
    assert "Suggestion" in str(exc.value)
    # nothing was written
    assert list(tmp_path.iterdir()) == []


def test_resolve_output_returns_path_under_output_dir(tmp_path):
    from midi_mcp.paths import resolve_output

    path = resolve_output("my_take")
    assert path == tmp_path / "my_take.mid"


def test_resolve_output_auto_suffix_on_collision(tmp_path):
    from midi_mcp.paths import resolve_output

    p1 = resolve_output("take")
    p1.write_bytes(b"x")
    p2 = resolve_output("take")
    p2.write_bytes(b"x")
    p3 = resolve_output("take")
    assert p1.name == "take.mid"
    assert p2.name == "take-2.mid"
    assert p3.name == "take-3.mid"


def test_resolve_output_overwrite_returns_same_path(tmp_path):
    from midi_mcp.paths import resolve_output

    p1 = resolve_output("take")
    p1.write_bytes(b"x")
    p2 = resolve_output("take", overwrite=True)
    assert p1 == p2 == tmp_path / "take.mid"


def test_resolve_output_empty_string_raises(tmp_path):
    from midi_mcp.paths import resolve_output

    with pytest.raises(ValueError):
        resolve_output("")


def test_path_rejected_suggestion_is_sanitized(tmp_path):
    from midi_mcp.paths import PathRejected, resolve_output

    with pytest.raises(PathRejected) as exc:
        resolve_output("../../etc/passwd")
    assert exc.value.suggestion == "passwd"
