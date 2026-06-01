"""Tests for midi_mcp.paths: sanitize, reject path-like, auto-suffix, folder routing."""

from datetime import date

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


SANITIZE_PROJECT_TABLE = [
    ("Blues Demo",     "blues_demo"),
    ("BLUES",          "blues"),
    ("café session",   "cafe_session"),
    ("!!!@@@",         "untitled"),
    ("",               "untitled"),
    ("project.mid",    "projectmid"),  # no extension strip on project names
]


@pytest.mark.parametrize("raw,expected", SANITIZE_PROJECT_TABLE)
def test_sanitize_project(raw, expected):
    from midi_mcp.paths import sanitize_project

    assert sanitize_project(raw) == expected


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
    assert "Suggestion" in str(exc.value)
    assert list(tmp_path.iterdir()) == []


def test_resolve_output_defaults_to_date_folder(tmp_path):
    from midi_mcp.paths import resolve_output

    path = resolve_output("my_take")
    today = date.today().isoformat()
    assert path == tmp_path / today / "my_take.mid"
    assert (tmp_path / today).is_dir()


def test_resolve_output_with_project_routes_to_project_folder(tmp_path):
    from midi_mcp.paths import resolve_output

    path = resolve_output("take", project="Blues Demo")
    assert path == tmp_path / "blues_demo" / "take.mid"
    assert (tmp_path / "blues_demo").is_dir()


def test_resolve_target_dir_reuses_existing(tmp_path):
    from midi_mcp.paths import resolve_target_dir

    a = resolve_target_dir("blues_demo")
    b = resolve_target_dir("blues_demo")
    assert a == b == tmp_path / "blues_demo"


def test_resolve_target_dir_none_uses_today(tmp_path):
    from midi_mcp.paths import resolve_target_dir

    target = resolve_target_dir(None)
    assert target == tmp_path / date.today().isoformat()


def test_resolve_target_dir_rejects_path_like_project(tmp_path):
    from midi_mcp.paths import PathRejected, resolve_target_dir

    for bad in ("../foo", "/etc", "~/x", r"a\b"):
        with pytest.raises(PathRejected):
            resolve_target_dir(bad)


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
    assert p1.parent == p2.parent == p3.parent


def test_resolve_output_collision_is_per_folder(tmp_path):
    """Same filename in two projects = no collision."""
    from midi_mcp.paths import resolve_output

    p1 = resolve_output("take", project="alpha")
    p1.write_bytes(b"x")
    p2 = resolve_output("take", project="beta")
    assert p1.name == "take.mid"
    assert p2.name == "take.mid"
    assert p1.parent.name == "alpha"
    assert p2.parent.name == "beta"


def test_resolve_output_overwrite_returns_same_path(tmp_path):
    from midi_mcp.paths import resolve_output

    p1 = resolve_output("take", project="x")
    p1.write_bytes(b"x")
    p2 = resolve_output("take", project="x", overwrite=True)
    assert p1 == p2 == tmp_path / "x" / "take.mid"


def test_resolve_output_empty_string_raises(tmp_path):
    from midi_mcp.paths import resolve_output

    with pytest.raises(ValueError):
        resolve_output("")


def test_path_rejected_suggestion_is_sanitized(tmp_path):
    from midi_mcp.paths import PathRejected, resolve_output

    with pytest.raises(PathRejected) as exc:
        resolve_output("../../etc/passwd")
    assert exc.value.suggestion == "passwd"
