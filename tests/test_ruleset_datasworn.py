import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.ruleset import datasworn, impacts, meters, stats
from straightjacket.engine.ruleset.datasworn import load_ruleset, rules_file
from straightjacket.engine.ruleset.impacts import get_impacts
from straightjacket.engine.ruleset.legacy import new_campaign
from straightjacket.engine.ruleset.meters import condition_meters
from straightjacket.engine.ruleset.moves import get_moves, move_of_file
from straightjacket.engine.ruleset.stats import stat_descriptions
from straightjacket.engine.setting import loader, packages
from straightjacket.engine.setting.loader import load_setting
from straightjacket.engine.setting.packages import load_package

_REAL_SETTINGS = PROJECT_ROOT / "data" / "settings"


@pytest.fixture(name="settings_dir")
def fixture_settings_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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


@pytest.fixture(name="change_classic")
def fixture_change_classic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[tuple[str | int, ...], object], None]:
    def change(path: tuple[str | int, ...], value: object) -> None:
        data = json.loads((PROJECT_ROOT / "data" / "classic.json").read_text(encoding="utf-8"))
        if path:
            part = data
            for step in path[:-1]:
                part = part[step]
            part[path[-1]] = value
        else:
            data = value
        (tmp_path / "classic.json").write_text(json.dumps(data), encoding="utf-8")
        for module in (loader, packages, datasworn, meters, impacts, stats):
            monkeypatch.setattr(module, "_cache", {})
        monkeypatch.setattr(loader, "_files", {})
        monkeypatch.setattr(loader, "_DATA_DIR", tmp_path)
        monkeypatch.setattr("straightjacket.engine.ruleset.moves._file_cache", {})

    return change


@pytest.mark.parametrize(
    ("path", "value", "read", "message"),
    [
        (
            ("assets", "combat_talent", "contents", "archer", "abilities", 0, "text"),
            7,
            lambda: rules_file("classic"),
            r"classic\.assets\.combat_talent\.archer\.abilities\[0\]\.text: expected str, got int",
        ),
        (
            ("assets", "combat_talent", "contents", "archer", "abilities", 0, "enabled"),
            "yes",
            lambda: rules_file("classic"),
            r"classic\.assets\.combat_talent\.archer\.abilities\[0\]\.enabled: expected bool, got str",
        ),
        (
            ("moves", "adventure", "contents", "face_danger", "allow_momentum_burn"),
            "yes",
            lambda: move_of_file("classic", "adventure/face_danger"),
            r"classic\.moves\.adventure/face_danger\.allow_momentum_burn: expected bool, got str",
        ),
        (
            ("moves", "adventure", "contents", "face_danger", "trigger", "conditions", 0, "roll_options", 0, "stat"),
            ["edge"],
            lambda: move_of_file("classic", "adventure/face_danger"),
            r"face_danger\.trigger\.conditions\[0\]\.roll_options\[0\]\.stat: expected str, got list",
        ),
        (
            ("oracles", "action_and_theme", "contents", "action", "rows", 0, "roll", "min"),
            "1",
            lambda: load_setting("classic"),
            r"classic\.oracles\.action_and_theme/action\.rows\[0\]\.min: expected int, got str",
        ),
        (
            ("truths",),
            [],
            lambda: load_setting("classic"),
            r"classic\.truths: expected dict, got list",
        ),
        (
            ("truths", "old_world", "options", 0, "description"),
            7,
            lambda: load_setting("classic"),
            r"classic\.truths\.old_world\.options\[0\]\.description: expected str, got int",
        ),
        (
            ("oracles", "character", "contents", "goal", "rows", 32, "oracle_rolls", 0, "number_of_rolls"),
            "2",
            lambda: load_setting("classic"),
            r"character/goal\.rows\[32\]\.oracle_rolls\[0\]\.number_of_rolls: expected int, got str",
        ),
        (
            ("moves", "adventure", "contents", "face_danger", "suggestions"),
            [7],
            lambda: move_of_file("classic", "adventure/face_danger"),
            r"face_danger\.suggestions: expected str, got int",
        ),
        (
            ("rules", "impacts", "conditions", "contents", "wounded", "prevents_recovery"),
            [7],
            lambda: get_impacts("classic"),
            r"impacts\.wounded\.prevents_recovery: expected str, got int",
        ),
        (
            ("rules", "special_tracks", "bonds", "tags"),
            {"classic": {"legacy_track_xp": "yes"}},
            lambda: new_campaign("classic"),
            r"special_tracks\.bonds\.legacy_track_xp: expected bool, got str",
        ),
        (
            ("rules", "condition_meters", "health", "max"),
            True,
            lambda: condition_meters("classic"),
            r"condition_meters\.health\.max: expected int, got bool",
        ),
        ((), [], lambda: load_setting("classic"), r"classic\.json: expected dict, got list"),
        (
            ("rules", "condition_meters", "health", "max"),
            "5",
            lambda: condition_meters("classic"),
            r"classic\.rules\.condition_meters\.health\.max: expected int, got str",
        ),
        (
            ("rules", "stats", "edge", "description"),
            None,
            lambda: stat_descriptions("classic"),
            r"classic\.rules\.stats\.edge\.description: expected str, got NoneType",
        ),
        (
            ("rules", "impacts", "conditions", "contents", "wounded", "permanent"),
            "no",
            lambda: get_impacts("classic"),
            r"classic\.rules\.impacts\.wounded\.permanent: expected bool, got str",
        ),
        (
            ("rules", "special_tracks", "bonds", "optional"),
            "no",
            lambda: new_campaign("classic"),
            r"classic\.rules\.special_tracks\.bonds\.optional: expected bool, got str",
        ),
    ],
    ids=[
        "ability_text",
        "ability_enabled",
        "move_burn",
        "roll_option_stat",
        "oracle_row",
        "truths",
        "truth_option",
        "oracle_roll",
        "suggestion",
        "prevents_recovery",
        "tags",
        "meter_bool",
        "no_mapping",
        "meter",
        "stat",
        "impact",
        "special_track",
    ],
)
def test_a_datasworn_value_of_another_type_than_the_engine_reads_refuses_to_load(
    change_classic: Callable[[tuple[str | int, ...], object], None],
    path: tuple[str | int, ...],
    value: object,
    read: Callable[[], object],
    message: str,
) -> None:
    change_classic(path, value)
    with pytest.raises(ValueError, match=message):
        read()


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
