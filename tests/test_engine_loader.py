def test_miss_clock_ticks_cover_every_position(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    assert set(eng().clocks.miss_ticks_by_position) == set(eng().effect_resolver.position_weights)


def test_eng_returns_settings(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.engine_config import EngineSettings

    assert isinstance(eng(), EngineSettings)


def test_eng_is_cached(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng

    a = eng()
    b = eng()
    assert a is b


def test_npc_status_groups_name_only_known_statuses(load_engine: None) -> None:
    from dataclasses import fields

    from straightjacket.engine.engine_loader import eng

    groups = eng().npc_status_groups
    known = set(eng().enums.npc_statuses)
    for group in fields(groups):
        assert set(getattr(groups, group.name)) <= known, group.name


def test_dice_sizes_cover_the_tables_they_roll(load_engine: None) -> None:
    from straightjacket.engine.engine_loader import eng
    from straightjacket.engine.mechanics.fate import _load_mythic

    dice = eng().dice
    mythic = _load_mythic()
    assert max(row["max"] for row in mythic["event_focus"]) == dice.event_focus_die
    assert max(row["max"] for row in mythic["scene_adjustment"]) == dice.scene_adjustment_die
    assert max(eng().adventure_crafter.theme_die_table) == dice.adventure_crafter_theme_die


def test_a_move_gate_on_a_track_type_that_does_not_exist_is_refused() -> None:
    import pytest

    from straightjacket.engine.engine_config import ActiveTrackCondition, _parse_move_availability_rule

    track_types = {"vow", "journey"}
    rule = _parse_move_availability_rule({"available": [{"active_track": "journey"}]}, track_types)
    assert rule.available == [ActiveTrackCondition(active_track="journey")]
    for key in ("active_track", "no_active_track"):
        with pytest.raises(ValueError, match="'has_journey', which is no track type"):
            _parse_move_availability_rule({"available": [{key: "has_journey"}]}, track_types)
