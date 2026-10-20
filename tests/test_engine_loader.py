from pathlib import Path
from typing import Any

import pytest

from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.gamemaster.config import gm


def test_miss_clock_ticks_cover_every_position(load_engine: None) -> None:
    assert set(gm().clocks.miss_ticks_by_position) == set(gm().effect_resolver.position_weights)


def test_npc_status_groups_name_only_known_statuses(load_engine: None) -> None:
    from dataclasses import fields

    groups = gm().npc_status_groups
    known = set(gm().enums.npc_statuses)
    for group in fields(groups):
        assert set(getattr(groups, group.name)) <= known, group.name


def test_dice_sizes_cover_the_tables_they_roll(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.mythic_data import load_mythic

    dice = gm().mythic_dice
    mythic = load_mythic()
    assert max(row["max"] for row in mythic["event_focus"]) == dice.event_focus_die
    assert max(row["max"] for row in mythic["scene_adjustment"]) == dice.scene_adjustment_die
    assert max(crafter().adventure_crafter.theme_die_table) == crafter().adventure_crafter_dice.theme_die


@pytest.mark.parametrize("gate", ["active_track", "no_active_track"])
def test_a_move_gate_on_a_track_type_that_does_not_exist_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gate: str
) -> None:
    from straightjacket.engine.ruleset import config as ruleset_config
    from tests._helpers import change_config

    def gate_on_a_missing_type(section: dict[str, Any]) -> None:
        section["adventure/reach_your_destination"]["available"] = [{gate: "has_journey"}]

    change_config(monkeypatch, tmp_path, ruleset_config, "_rules", "move_availability", gate_on_a_missing_type)
    with pytest.raises(ValueError, match="'has_journey', which is no track type"):
        ruleset_config.rules()
