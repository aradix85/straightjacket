from collections.abc import Generator
from pathlib import Path

import pytest

from straightjacket.engine.ruleset.datasworn import load_ruleset
from straightjacket.engine.ruleset.moves import get_moves
from straightjacket.engine.setting import packages
from straightjacket.engine.setting.packages import clear_cache, load_package

_REAL_SETTINGS = packages._SETTINGS_DIR


@pytest.fixture
def settings_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[Path, None, None]:
    clear_cache()
    monkeypatch.setattr(packages, "_SETTINGS_DIR", tmp_path)
    yield tmp_path
    clear_cache()


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
