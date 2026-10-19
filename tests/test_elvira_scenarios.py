from pathlib import Path

import pytest

from tests._helpers import make_act, make_blueprint, make_clock, make_game_state
from tests.elvira.elvira_bot.models import RollRecord, SessionLog, TurnRecord

ELVIRA_CONFIG = Path(__file__).resolve().parent / "elvira" / "elvira_config.yaml"


def test_every_configured_scenario_names_known_targets() -> None:
    from tests.elvira.elvira_bot.runner import load_config
    from tests.elvira.elvira_bot.scenarios import check_expectations

    scenarios = load_config(ELVIRA_CONFIG)["scenarios"]
    assert scenarios
    for spec in scenarios.values():
        check_expectations(spec)


def test_an_unknown_target_is_refused(load_engine: None) -> None:
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    with pytest.raises(ValueError, match="dragon_slain"):
        prepare_scenario(make_game_state(), {"expect": ["dragon_slain"]})


def test_momentum_can_be_set_to_its_maximum(load_engine: None) -> None:
    from straightjacket.engine.ruleset.meters import max_momentum
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    game = make_game_state()
    prepare_scenario(game, {"expect": ["burn_offered"], "resources": {"momentum": "max", "health": 0}})
    assert game.resources.meters["momentum"] == max_momentum(game)
    assert game.resources.meters["health"] == 0


def test_a_meter_the_ruleset_lacks_is_refused(load_engine: None) -> None:
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    with pytest.raises(KeyError, match="helth"):
        prepare_scenario(make_game_state(), {"expect": ["burn_offered"], "resources": {"helth": 0}})


def test_the_story_completes_on_the_next_scene(load_engine: None) -> None:
    from straightjacket.engine.story_state import check_story_completion
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    game = make_game_state()
    game.narrative.story_blueprint = make_blueprint(
        acts=[make_act(scene_range=[1, 5]), make_act(scene_range=[6, 10]), make_act(scene_range=[11, 15])]
    )
    notes = prepare_scenario(game, {"expect": ["chapter_transition"], "story_end": True})
    assert notes == ["final act entered, scene 14 of 15"]
    assert not game.narrative.story_blueprint.story_complete
    game.narrative.scene_count += 1
    check_story_completion(game)
    assert game.narrative.story_blueprint.story_complete


def test_combat_opens_a_track_and_a_position(load_engine: None) -> None:
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    game = make_game_state()
    prepare_scenario(game, {"expect": ["combat"], "combat": True})
    assert game.world.combat_position == "in_control"
    assert any(t.track_type == "combat" and t.status == "active" for t in game.progress_tracks)


def test_an_open_clock_is_one_segment_from_full(load_engine: None) -> None:
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    game = make_game_state()
    game.world.clocks = [make_clock(name="Storm", segments=6, filled=1)]
    prepare_scenario(game, {"expect": ["clock_fired"], "clock_nearly_full": True})
    assert game.world.clocks[0].filled == 5


def test_every_configured_scenario_fixes_only_results_the_ruleset_rolls(load_engine: None) -> None:
    from tests.elvira.elvira_bot.fixed_results import check_results
    from tests.elvira.elvira_bot.runner import load_config

    for spec in load_config(ELVIRA_CONFIG)["scenarios"].values():
        check_results(spec["results"] if "results" in spec else [])


def test_a_result_the_ruleset_does_not_roll_is_refused(load_engine: None) -> None:
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    with pytest.raises(ValueError, match="CRITICAL_HIT"):
        prepare_scenario(make_game_state(), {"expect": ["result:MISS"], "results": ["MISS", "CRITICAL_HIT"]})


def test_each_turn_takes_its_own_fixed_result_and_later_turns_roll_freely() -> None:
    from tests.elvira.elvira_bot.scenarios import fixed_result_of_turn

    spec = {"expect": ["result:MISS"], "results": ["MISS", "WEAK_HIT"]}
    assert [fixed_result_of_turn(spec, turn) for turn in (1, 2, 3)] == ["MISS", "WEAK_HIT", None]
    assert fixed_result_of_turn({"expect": []}, 1) is None
    assert fixed_result_of_turn(None, 1) is None


@pytest.mark.parametrize("result", ["MISS", "WEAK_HIT", "STRONG_HIT"])
@pytest.mark.parametrize("stat_value", [1, 3])
def test_a_fixed_result_comes_out_of_every_action_roll_without_a_match(
    load_engine: None, result: str, stat_value: int
) -> None:
    from straightjacket.engine.ruleset import make_move, move_outcome
    from tests.elvira.elvira_bot.fixed_results import fixed_result

    with fixed_result(result):
        rolled = [
            roll("edge", stat_value, "adventure/face_danger", 2, 0)
            for roll in (make_move.roll_action, move_outcome.roll_action)
            for _ in range(20)
        ]
    assert {r.result for r in rolled} == {result}
    assert not any(r.match for r in rolled)


def test_a_fixed_result_comes_out_of_a_progress_roll(load_engine: None) -> None:
    from straightjacket.engine.ruleset import make_move
    from tests.elvira.elvira_bot.fixed_results import fixed_result

    with fixed_result("STRONG_HIT"):
        roll = make_move.roll_progress("Find the archive", 10, "quest/fulfill_your_vow")
    assert (roll.result, roll.match) == ("STRONG_HIT", False)


def test_a_fixed_result_takes_a_match_only_when_no_other_dice_give_it(load_engine: None) -> None:
    from straightjacket.engine.ruleset import make_move
    from straightjacket.engine.ruleset.config import rules
    from tests.elvira.elvira_bot.fixed_results import fixed_result

    top = rules().dice.challenge_die
    with fixed_result("MISS"):
        roll = make_move.roll_progress("Find the archive", rules().progress.boxes, "quest/fulfill_your_vow")
    assert (roll.result, roll.c1, roll.c2, roll.match) == ("MISS", top, top, True)


def test_a_fixed_result_no_dice_can_give_is_refused(load_engine: None) -> None:
    from straightjacket.engine.ruleset import make_move
    from tests.elvira.elvira_bot.fixed_results import fixed_result

    with fixed_result("STRONG_HIT"), pytest.raises(ValueError, match="no dice give"):
        make_move.roll_progress("Find the archive", 0, "quest/fulfill_your_vow")


def test_the_dice_roll_freely_after_a_fixed_turn(load_engine: None) -> None:
    from straightjacket.engine.ruleset import rolls
    from tests.elvira.elvira_bot.fixed_results import fixed_result

    score_action = rolls.score_action_roll
    with fixed_result("MISS"):
        assert rolls.score_action_roll is not score_action
    assert rolls.score_action_roll is score_action


def test_a_scenario_can_start_at_a_game_over(load_engine: None) -> None:
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    game = make_game_state()
    notes = prepare_scenario(game, {"expect": ["succession"], "game_over": "death"})
    assert game.game_over
    assert game.end_reason == "death"
    assert notes == ["game over (death), a successor waits"]


def test_a_missed_aim_is_a_problem() -> None:
    from tests.elvira.elvira_bot.report import collect_problems

    slog = SessionLog(config={"game": {"setting_id": "starforged"}})
    slog.scenario = {"name": "near_death", "prepared": [], "expect": ["impact_marked", "follow_up_move"]}
    slog.scenario |= {"reached": ["follow_up_move"], "missed": ["impact_marked"]}
    assert collect_problems(slog) == ["Scenario near_death: impact_marked not reached"]


def _audited_turn(turn: int, result: str, integrity: int, overall: int, burned_to: str = "") -> TurnRecord:
    verdict = {c: 3 for c in ("prompt_elements", "npc_voice", "player_agency", "restraint", "prose")}
    verdict |= {"result_integrity": integrity, "overall": overall, "weakness": ""}
    return TurnRecord(
        turn=turn,
        roll=RollRecord(result=result),
        burn_offered=burned_to,
        burn_taken=bool(burned_to),
        judge=verdict,
    )


def test_the_report_scores_misses_apart() -> None:
    from tests.elvira.elvira_bot.report import _audit_lines

    slog = SessionLog(
        turns=[
            _audited_turn(1, "MISS", 2, 4),
            _audited_turn(2, "MISS", 4, 8),
            _audited_turn(3, "STRONG_HIT", 5, 9),
            _audited_turn(4, "MISS", 5, 9, burned_to="WEAK_HIT"),
        ]
    )
    assert "On misses alone, 2 turns: result_integrity 3.0 out of 5, overall 6.0 out of 10." in _audit_lines(slog)


def test_the_report_says_when_no_miss_was_audited() -> None:
    from tests.elvira.elvira_bot.report import _audit_lines

    slog = SessionLog(turns=[_audited_turn(1, "WEAK_HIT", 4, 7)])
    assert "No misses audited." in _audit_lines(slog)
