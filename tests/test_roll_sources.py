from typing import Any

from straightjacket.engine.models import ProgressTrack
from tests._helpers import make_brain_result, make_game_state, make_npc


def _starforged() -> Any:
    game = make_game_state(setting_id="starforged")
    game.last_turn_snapshot = game.snapshot()
    return game


def test_check_your_gear_rolls_with_supply(load_engine: None) -> None:
    from straightjacket.engine.game.turn import _execute_roll

    game = _starforged()
    game.resources.supply = 3
    outcome = _execute_roll(game, make_brain_result(move="adventure/check_your_gear", stat="none"), None)
    assert outcome.roll.stat_name == "supply"
    assert outcome.roll.stat_value == 3


def test_a_stat_the_brain_names_for_a_meter_move_is_ignored(load_engine: None) -> None:
    from straightjacket.engine.game.turn import _execute_roll

    game = _starforged()
    game.resources.supply = 2
    outcome = _execute_roll(game, make_brain_result(move="exploration/set_a_course", stat="wits"), None)
    assert (outcome.roll.stat_name, outcome.roll.stat_value) == ("supply", 2)


def test_develop_your_relationship_rolls_with_the_rank_of_the_connection(load_engine: None) -> None:
    from straightjacket.engine.game.turn import _execute_roll

    game = _starforged()
    game.npcs = [make_npc(id="npc_1", name="Vex")]
    game.progress_tracks.append(
        ProgressTrack.new(id="connection_npc_1", name="Vex", track_type="connection", rank="dangerous")
    )
    brain = make_brain_result(move="connection/develop_your_relationship", stat="none", target_npc="npc_1")
    outcome = _execute_roll(game, brain, None)
    assert (outcome.roll.stat_name, outcome.roll.stat_value) == ("dangerous", 2)


def test_a_meter_move_does_not_turn_into_dialog(load_engine: None) -> None:
    from straightjacket.engine.game.turn import _sanitize_brain_output

    brain = make_brain_result(move="adventure/check_your_gear", stat="none", dialog_only=False)
    _sanitize_brain_output(_starforged(), brain)
    assert brain.dialog_only is False
