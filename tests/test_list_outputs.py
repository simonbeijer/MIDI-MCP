"""Tests for list_outputs: returns {folders, files}, recurses one level."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDI_MCP_OUTPUT_DIR", str(tmp_path))
    yield tmp_path


def test_empty_dir_returns_empty_shape(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    assert list_outputs() == {"folders": [], "files": []}


def test_lists_root_level_mid_files(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    (tmp_path / "foo.mid").write_bytes(b"x")
    (tmp_path / "bar.mid").write_bytes(b"xx")

    result = list_outputs()
    assert result["folders"] == []
    paths = {e["path"] for e in result["files"]}
    assert paths == {"foo.mid", "bar.mid"}


def test_filters_dotfiles_and_non_mid(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    (tmp_path / "ok.mid").write_bytes(b"x")
    (tmp_path / ".log").write_text("seed=1\n")
    (tmp_path / ".hidden").write_text("y")
    (tmp_path / "notes.txt").write_text("z")

    result = list_outputs()
    paths = {e["path"] for e in result["files"]}
    assert paths == {"ok.mid"}


def test_returns_folder_names(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    (tmp_path / "blues_demo").mkdir()
    (tmp_path / "2026-06-01").mkdir()
    (tmp_path / ".hidden_dir").mkdir()

    result = list_outputs()
    assert result["folders"] == ["2026-06-01", "blues_demo"]


def test_recurses_one_level_into_folders(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    proj = tmp_path / "blues_demo"
    proj.mkdir()
    (proj / "take_1.mid").write_bytes(b"x")
    (proj / "take_2.mid").write_bytes(b"xx")

    result = list_outputs()
    paths = {e["path"] for e in result["files"]}
    assert paths == {"blues_demo/take_1.mid", "blues_demo/take_2.mid"}


def test_does_not_recurse_past_one_level(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "buried.mid").write_bytes(b"x")
    (tmp_path / "a" / "shallow.mid").write_bytes(b"x")

    result = list_outputs()
    paths = {e["path"] for e in result["files"]}
    assert paths == {"a/shallow.mid"}


def test_file_entry_shape(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    proj = tmp_path / "x"
    proj.mkdir()
    (proj / "one.mid").write_bytes(b"abc")

    result = list_outputs()
    entry = result["files"][0]
    assert set(entry.keys()) == {"path", "modified", "size_bytes"}
    assert entry["path"] == "x/one.mid"
    assert entry["size_bytes"] == 3
    assert isinstance(entry["modified"], str)


def test_mixed_root_and_folder_files(tmp_path):
    from midi_mcp.list_outputs import list_outputs

    (tmp_path / "legacy.mid").write_bytes(b"x")
    proj = tmp_path / "blues_demo"
    proj.mkdir()
    (proj / "take.mid").write_bytes(b"x")

    result = list_outputs()
    assert result["folders"] == ["blues_demo"]
    paths = [e["path"] for e in result["files"]]
    assert paths == ["blues_demo/take.mid", "legacy.mid"]
