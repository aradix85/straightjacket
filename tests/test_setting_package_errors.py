from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from straightjacket.engine.setting import packages
from straightjacket.engine.setting.packages import load_package

_STARFORGED = Path(__file__).resolve().parent.parent / "data" / "settings" / "starforged.yaml"


def _drop(key: str) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        del data[key]

    return change


def _put(key: str, value: object) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        data[key] = value

    return change


def _put_generator(value: object) -> Callable[[dict[str, Any]], None]:
    def change(data: dict[str, Any]) -> None:
        data["generators"]["npc"] = value

    return change


@pytest.mark.parametrize(
    ("change", "error", "message"),
    [
        (_drop("title"), KeyError, "Required key 'title' missing"),
        (_put("title", ["Starforged"]), TypeError, "Expected str at 'title'"),
        (_drop("oracle_paths"), KeyError, "Required key 'oracle_paths' missing"),
        (_put("oracle_paths", "core/action"), TypeError, "Expected dict at 'oracle_paths'"),
        (_put("id", "elsewhere"), ValueError, "must equal the file name"),
        (_put_generator("character/name/given_name"), TypeError, "Expected a mapping of roles to oracle paths"),
        (_put_generator({"given_name": 7}), TypeError, "Expected an oracle path at generators.npc.given_name"),
    ],
    ids=["no_title", "title_not_text", "no_oracle_paths", "oracle_paths_not_a_mapping", "id", "roles", "path"],
)
def test_a_setting_yaml_of_the_wrong_shape_refuses_to_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    change: Callable[[dict[str, object]], None],
    error: type[Exception],
    message: str,
) -> None:
    data = yaml.safe_load(_STARFORGED.read_text(encoding="utf-8"))
    change(data)
    (tmp_path / "starforged.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    monkeypatch.setattr(packages, "_SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(packages, "_cache", {})
    with pytest.raises(error, match=message):
        load_package("starforged")


def test_a_setting_that_is_not_there_is_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(packages, "_SETTINGS_DIR", tmp_path)
    monkeypatch.setattr(packages, "_cache", {})
    with pytest.raises(FileNotFoundError, match="Setting package not found"):
        load_package("starforged")
