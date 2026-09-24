from pathlib import Path

import pytest

from tests._helpers import make_act, make_blueprint, make_clock, make_game_state

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
    from tests.elvira.elvira_bot.scenarios import prepare_scenario

    game = make_game_state()
    prepare_scenario(game, {"expect": ["burn_offered"], "resources": {"momentum": "max", "health": 0}})
    assert game.resources.momentum == game.resources.max_momentum
    assert game.resources.health == 0


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
