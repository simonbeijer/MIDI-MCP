"""Tests for list_outputs: filters dotfiles + non-.mid files."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDI_MCP_OUTPUT_DIR", str(tmp_path))
    yield tmp_path


def test_empty_dir_returns_empty_list(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    assert list_outputs() == []


def test_filters_log_and_dotfiles(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    (tmp_path / "foo.mid").write_bytes(b"x")
    (tmp_path / "bar.mid").write_bytes(b"xx")
    (tmp_path / ".log").write_text("seed=1\n")
    (tmp_path / ".hidden").write_text("y")
    (tmp_path / "notes.txt").write_text("z")

    result = list_outputs()
    names = {e["filename"] for e in result}
    assert names == {"foo.mid", "bar.mid"}


def test_entry_shape_has_filename_modified_size(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    (tmp_path / "one.mid").write_bytes(b"abc")
    result = list_outputs()
    assert len(result) == 1
    entry = result[0]
    assert set(entry.keys()) == {"filename", "modified", "size_bytes"}
    assert entry["filename"] == "one.mid"
    assert entry["size_bytes"] == 3
    assert isinstance(entry["modified"], str)
