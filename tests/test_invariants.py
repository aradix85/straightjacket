import sys as _sys
from pathlib import Path as _Path

from straightjacket.engine.models import GameState
from tests._helpers import make_clock, make_game_state, make_memory, make_npc, make_scene_log_entry

_sys.path.insert(0, str(_Path(__file__).resolve().parent / "elvira"))

from elvira_bot.invariants import assert_game_state
from elvira_bot.quality_checks import check_narration_quality


def _clean_game() -> GameState:
    game = make_game_state(player_name="Hero")
    game.resources.meters["health"] = 5
    game.resources.meters["spirit"] = 5
    game.resources.meters["supply"] = 5
    game.resources.meters["momentum"] = 3
    game.world.chaos_factor = 5
    game.narrative.scene_count = 3
    game.npcs = [
        make_npc(
            id="npc_1",
            name="Kira",
            status="active",
            disposition="friendly",
            memory=[make_memory(scene=1, event="Met player", type="observation", importance=3)],
        ),
    ]
    game.world.clocks = [
        make_clock(name="Doom", clock_type="threat", segments=6, filled=2),
    ]
    game.narrative.session_log = [
        make_scene_log_entry(scene=3, summary="Last scene"),
    ]
    return game


def test_clean_state_no_violations(load_engine: None) -> None:
    game = _clean_game()
    violations = assert_game_state(game, turn=1)
    assert violations == []


def test_catches_health_out_of_range(load_engine: None) -> None:
    game = _clean_game()
    game.resources.meters["health"] = 7
    violations = assert_game_state(game, turn=1)
    assert any("health" in v for v in violations)


def test_catches_negative_spirit(load_engine: None) -> None:
    game = _clean_game()
    game.resources.meters["spirit"] = -1
    violations = assert_game_state(game, turn=1)
    assert any("spirit" in v for v in violations)


def test_catches_momentum_exceeds_max(load_engine: None) -> None:
    game = _clean_game()
    game.resources.meters["momentum"] = 12
    violations = assert_game_state(game, turn=1)
    assert any("momentum" in v for v in violations)


def test_catches_chaos_below_min(load_engine: None) -> None:
    game = _clean_game()
    game.world.chaos_factor = 0
    violations = assert_game_state(game, turn=1)
    assert any("chaos" in v.lower() for v in violations)


def test_catches_chaos_above_max(load_engine: None) -> None:
    game = _clean_game()
    game.world.chaos_factor = 10
    violations = assert_game_state(game, turn=1)
    assert any("chaos" in v.lower() for v in violations)


def test_catches_crisis_mode_when_both_positive(load_engine: None) -> None:
    game = _clean_game()
    game.crisis_mode = True
    violations = assert_game_state(game, turn=1)
    assert any("crisis" in v.lower() for v in violations)


def test_catches_crisis_mode_missing_at_zero(load_engine: None) -> None:
    game = _clean_game()
    game.resources.meters["spirit"] = 0
    game.crisis_mode = False
    violations = assert_game_state(game, turn=1)
    assert any("crisis_mode=False" in v for v in violations)


def test_meters_at_zero_without_game_over_are_no_violation(load_engine: None) -> None:
    game = _clean_game()
    game.resources.meters["health"] = 0
    game.resources.meters["spirit"] = 0
    game.crisis_mode = True
    assert assert_game_state(game, turn=1) == []


def test_catches_npc_empty_id(load_engine: None) -> None:
    game = _clean_game()
    game.npcs[0].id = ""
    violations = assert_game_state(game, turn=1)
    assert any("empty id" in v for v in violations)


def test_catches_npc_invalid_disposition(load_engine: None) -> None:
    game = _clean_game()
    game.npcs[0].disposition = "angry"
    violations = assert_game_state(game, turn=1)
    assert any("disposition" in v for v in violations)


def test_catches_npc_memory_missing_fields(load_engine: None) -> None:
    game = _clean_game()
    game.npcs[0].memory = [make_memory(scene=1, event="", type="", importance=0)]
    violations = assert_game_state(game, turn=1)
    assert any("event" in v for v in violations)
    assert any("type" in v for v in violations)
    assert any("importance" in v for v in violations)


def test_catches_alias_duplicates_name(load_engine: None) -> None:
    game = _clean_game()
    game.npcs[0].aliases = ["Kira"]
    violations = assert_game_state(game, turn=1)
    assert any("alias" in v.lower() and "duplicate" in v.lower() for v in violations)


def test_catches_clock_overfilled(load_engine: None) -> None:
    game = _clean_game()
    game.world.clocks[0].filled = 8
    violations = assert_game_state(game, turn=1)
    assert any("filled" in v for v in violations)


def test_catches_fired_but_not_full(load_engine: None) -> None:
    game = _clean_game()
    game.world.clocks[0].fired = True
    game.world.clocks[0].filled = 3
    violations = assert_game_state(game, turn=1)
    assert any("fired" in v.lower() for v in violations)


def test_catches_invalid_clock_type(load_engine: None) -> None:
    game = _clean_game()
    game.world.clocks[0].clock_type = "timer"
    violations = assert_game_state(game, turn=1)
    assert any("clock_type" in v for v in violations)


def test_a_dying_clock_is_a_valid_clock(load_engine: None) -> None:
    from straightjacket.engine.ruleset.suffer import start_dying_clock

    game = _clean_game()
    game.resources.meters["health"] = 0
    game.crisis_mode = True
    start_dying_clock(game)
    assert assert_game_state(game, turn=1) == []


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])


def test_quality_catches_leaked_result_type() -> None:
    issues = check_narration_quality("The warrior strikes. STRONG_HIT. The blade bites deep.")
    assert any("result type" in i for i in issues)


def test_quality_catches_leaked_stat_value() -> None:
    issues = check_narration_quality("You feel weakened. health = 3. The wound bleeds.")
    assert any("stat value" in i for i in issues)


def test_quality_catches_xml_tags() -> None:
    issues = check_narration_quality("The door creaks. <memory_updates>test</memory_updates>")
    assert any("XML" in i for i in issues)


def test_quality_catches_markdown() -> None:
    issues = check_narration_quality("She said **hello** to the stranger.")
    assert any("markdown bold" in i for i in issues)


def test_quality_passes_clean_narration() -> None:
    issues = check_narration_quality(
        "The wind howled through the broken windows. She stepped inside, her boots crunching on shattered glass."
    )
    assert issues == []


def test_quality_catches_bracket_annotations() -> None:
    issues = check_narration_quality("The blade struck true. [CLOCK CREATED: Shadow Rising 0/6]")
    assert any("bracket" in i for i in issues)
