from pathlib import Path

import pytest

from straightjacket.engine.yaml_merge import load_yaml_dir


def test_a_missing_config_directory_names_the_hint(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="restore it"):
        load_yaml_dir(tmp_path / "absent", missing_dir_hint="restore it")


def test_a_config_directory_without_yaml_files_stops_loading(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No yaml files"):
        load_yaml_dir(tmp_path, missing_dir_hint="")


def test_a_yaml_file_that_is_not_a_mapping_stops_loading(tmp_path: Path) -> None:
    (tmp_path / "list.yaml").write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(TypeError, match="not a valid YAML dict"):
        load_yaml_dir(tmp_path, missing_dir_hint="")


def test_a_top_level_key_in_two_files_stops_loading(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("dice: 1\n", encoding="utf-8")
    (tmp_path / "b.yaml").write_text("dice: 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate top-level key 'dice'"):
        load_yaml_dir(tmp_path, missing_dir_hint="")
