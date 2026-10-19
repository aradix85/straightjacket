from straightjacket.engine.crafters.config import crafter
from straightjacket.engine.gamemaster.config import gm


def test_miss_clock_ticks_cover_every_position(load_engine: None) -> None:

    assert set(gm().clocks.miss_ticks_by_position) == set(gm().effect_resolver.position_weights)


def test_eng_returns_settings(load_engine: None) -> None:
    from straightjacket.engine.engine_config import EngineSettings
    from straightjacket.engine.engine_loader import eng

    assert isinstance(eng(), EngineSettings)


def test_eng_is_cached(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    a = eng()
    b = eng()
    assert a is b


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


def test_a_move_gate_on_a_track_type_that_does_not_exist_is_refused() -> None:
    import pytest

    from straightjacket.engine.ruleset.config import _parse_move_availability_rule
    from straightjacket.engine.ruleset.config_types import ActiveTrackCondition

    track_types = {"vow", "journey"}
    rule = _parse_move_availability_rule({"available": [{"active_track": "journey"}]}, track_types)
    assert rule.available == [ActiveTrackCondition(active_track="journey")]
    for key in ("active_track", "no_active_track"):
        with pytest.raises(ValueError, match="'has_journey', which is no track type"):
            _parse_move_availability_rule({"available": [{key: "has_journey"}]}, track_types)
