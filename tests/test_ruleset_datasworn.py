from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine.ruleset.datasworn import load_ruleset
from straightjacket.engine.ruleset.moves import get_moves
from straightjacket.engine.setting import packages
from straightjacket.engine.setting.packages import load_package

_REAL_SETTINGS = packages._SETTINGS_DIR


@pytest.fixture
def settings_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(packages, "_cache", {})
    monkeypatch.setattr(packages, "_SETTINGS_DIR", tmp_path)
    return tmp_path


def _copy(settings_dir: Path, setting_id: str, new_id: str, parent: str = "") -> None:
    lines = (_REAL_SETTINGS / f"{setting_id}.yaml").read_text(encoding="utf-8").splitlines()
    lines = [f"id: {new_id}" if line.startswith("id:") else line for line in lines]
    lines = [line for line in lines if not line.startswith("parent:")]
    if parent:
        lines.append(f"parent: {parent}")
    (settings_dir / f"{new_id}.yaml").write_text("\n".join(lines), encoding="utf-8")


@pytest.mark.parametrize(
    ("setting_id", "ruleset", "files"),
    [
        ("classic", "classic", ["classic"]),
        ("delve", "classic", ["classic", "delve"]),
        ("starforged", "starforged", ["starforged"]),
        ("sundered_isles", "starforged", ["starforged", "sundered_isles"]),
    ],
)
def test_a_setting_names_its_ruleset_through_its_datasworn_file(
    setting_id: str, ruleset: str, files: list[str]
) -> None:
    assert load_package(setting_id).ruleset_id == ruleset
    loaded = load_ruleset(setting_id)
    assert loaded.id == ruleset
    assert [f.datasworn_id for f in loaded.files] == files
    assert loaded.setting_file.datasworn_id == load_package(setting_id).datasworn_id


def test_a_setting_whose_chain_holds_no_ruleset_file_still_plays_its_ruleset(settings_dir: Path) -> None:
    _copy(settings_dir, "starforged", "starforged")
    _copy(settings_dir, "sundered_isles", "sundered_isles", parent="starforged")
    _copy(settings_dir, "sundered_isles", "isles_alone")
    assert [pkg.id for pkg in load_package("isles_alone").chain()] == ["isles_alone"]
    assert [f.datasworn_id for f in load_ruleset("isles_alone").files] == ["starforged", "sundered_isles"]
    moves = get_moves("isles_alone")
    assert moves["adventure/face_danger"] == get_moves("starforged")["adventure/face_danger"]
    assert moves["recover/repair"] == get_moves("sundered_isles")["recover/repair"]


def test_a_setting_chain_that_names_two_rulesets_raises(settings_dir: Path) -> None:
    _copy(settings_dir, "classic", "classic")
    _copy(settings_dir, "sundered_isles", "mixed", parent="classic")
    with pytest.raises(ValueError, match="more than one ruleset"):
        load_package("mixed")


def _probe() -> dict[str, Any]:
    return {
        "id": "probe",
        "title": "Probe",
        "datasworn_id": "probe",
        "playable": True,
        "description": "Probe setting.",
        "oracle_paths": {"threats": "a/b"},
        "generators": {"location": {"theme": "themes/type", "feature": "themes/{theme}/feature"}},
        "vocabulary": {"substitutions": {}, "sensory_palette": ""},
        "creation_flow": {"has_truths": False},
    }


def _write(settings_dir: Path, file_name: str, data: dict[str, Any]) -> None:
    (settings_dir / f"{file_name}.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_a_generator_role_names_only_earlier_roles(settings_dir: Path) -> None:
    data = _probe()
    data["generators"] = {"location": {"feature": "themes/{theme}/feature", "theme": "themes/type"}}
    _write(settings_dir, "probe", data)
    with pytest.raises(KeyError, match="no earlier role"):
        load_package("probe")


@pytest.mark.parametrize("section", [None, "oracle_paths", "vocabulary", "creation_flow"])
def test_a_key_the_setting_yaml_does_not_know_raises(settings_dir: Path, section: str | None) -> None:
    data = _probe()
    target = data if section is None else data[section]
    target["factions"] = "factions"
    _write(settings_dir, "probe", data)
    with pytest.raises(KeyError, match=r"Unknown key\(s\) \['factions'\]"):
        load_package("probe")


def test_a_setting_id_must_equal_its_file_name(settings_dir: Path) -> None:
    _write(settings_dir, "other", _probe())
    with pytest.raises(ValueError, match="must equal the file name 'other'"):
        load_package("other")


@pytest.mark.parametrize(("playable", "error"), [(None, KeyError), ("yes", TypeError)])
def test_a_setting_must_say_whether_it_is_playable(settings_dir: Path, playable: str | None, error: type) -> None:
    data = _probe()
    if playable is None:
        del data["playable"]
    else:
        data["playable"] = playable
    _write(settings_dir, "probe", data)
    with pytest.raises(error, match="playable"):
        load_package("probe")
