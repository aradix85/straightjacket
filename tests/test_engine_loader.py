from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.mythic_data import load_mythic
from straightjacket.engine.ruleset import config as ruleset_config
from tests._helpers import change_config


def test_miss_clock_ticks_cover_every_position() -> None:
    assert set(gm().clocks.miss_ticks_by_position) == set(gm().effect_resolver.position_weights)


def test_npc_status_groups_name_only_known_statuses() -> None:
    groups = gm().npc_status_groups
    known = set(gm().enums.npc_statuses)
    for group in fields(groups):
        assert set(getattr(groups, group.name)) <= known, group.name


def test_dice_sizes_cover_the_tables_they_roll() -> None:
    dice = gm().mythic_dice
    mythic = load_mythic()
    assert max(row["max"] for row in mythic["event_focus"]) == dice.event_focus_die
    assert max(row["max"] for row in mythic["scene_adjustment"]) == dice.scene_adjustment_die
    assert max(crafter().adventure_crafter.theme_die_table) == crafter().adventure_crafter_dice.theme_die


@pytest.mark.parametrize("gate", ["active_track", "no_active_track"])
def test_a_move_gate_on_a_track_type_that_does_not_exist_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gate: str
) -> None:
    def gate_on_a_missing_type(section: dict[str, Any]) -> None:
        section["adventure/reach_your_destination"]["available"] = [{gate: "has_journey"}]

    change_config(monkeypatch, tmp_path, ruleset_config, "move_availability", gate_on_a_missing_type)
    with pytest.raises(ValueError, match="'has_journey', which is no track type"):
        ruleset_config.rules()


@pytest.mark.parametrize(
    ("rule", "message"),
    [
        ({"never": False}, "never=false is not allowed"),
        ({"never": True, "available": []}, "Expected exactly one of: never, available"),
        ({"available": [{"active_track": "vow", "bonded_track": "connection"}]}, "Invalid move_availability condition"),
    ],
    ids=["never_false", "two_keys", "condition_with_two_keys"],
)
def test_a_move_availability_rule_of_the_wrong_shape_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rule: dict[str, object], message: str
) -> None:
    def reshape(section: dict[str, Any]) -> None:
        section["adventure/face_danger"] = rule

    change_config(monkeypatch, tmp_path, ruleset_config, "move_availability", reshape)
    with pytest.raises(ValueError, match=message):
        ruleset_config.rules()
