from typing import Any

import pytest

from straightjacket.engine.ruleset.progress import new_track
from tests._helpers import make_brain_result, make_game_state, make_npc


def _starforged() -> Any:
    game = make_game_state(setting_id="starforged")
    game.last_turn_snapshot = game.snapshot()
    return game


@pytest.mark.parametrize(
    ("move", "stat", "dialog_only", "rolled"),
    [
        ("adventure/check_your_gear", "none", False, ("supply", 3)),
        ("world_shaping", "wits", False, ("wits", 1)),
        ("world_shaping", "none", False, None),
        ("adventure/face_danger", "wits", True, None),
        ("dialog", "none", False, None),
    ],
)
def test_what_a_turn_rolls_with_or_plays_as_dialog(
    load_engine: None, move: str, stat: str, dialog_only: bool, rolled: tuple[str, int] | None
) -> None:
    from straightjacket.engine.game import process_turn
    from tests._creation import TurnProvider, brain_answer, create_game

    game = create_game(
        "starforged",
        location="Drift Station",
        npcs=[],
        stats=(3, 2, 2, 1, 1),
        player_name="Kael",
        background_vow="Keep the station running",
    )
    game.resources.meters["supply"] = 3
    brain = brain_answer(
        move=move, stat=stat, dialog_only=dialog_only, location_change=None, track_name=None, track_rank=None
    )
    _narration, roll, _offer, _director = process_turn(TurnProvider(brain), game, "I act.", stream=None)
    assert (None if roll is None else (roll.stat_name, roll.stat_value)) == rolled


def test_a_stat_the_brain_names_for_a_meter_move_is_ignored(load_engine: None) -> None:
    from straightjacket.engine.ruleset.make_move import roll_move

    game = _starforged()
    game.resources.meters["supply"] = 2
    outcome = roll_move(game, make_brain_result(move="exploration/set_a_course", stat="wits"), None)
    assert (outcome.roll.stat_name, outcome.roll.stat_value) == ("supply", 2)


def test_develop_your_relationship_rolls_with_the_rank_of_a_bonded_connection(load_engine: None) -> None:
    from straightjacket.engine.ruleset.make_move import roll_move

    game = _starforged()
    game.npcs = [make_npc(id="npc_1", name="Vex")]
    track = new_track(id="connection_npc_1", name="Vex", track_type="connection", rank="dangerous")
    track.status = "bonded"
    game.progress_tracks.append(track)
    brain = make_brain_result(move="connection/develop_your_relationship", stat="none", target_npc="npc_1")
    outcome = roll_move(game, brain, None)
    assert (outcome.roll.stat_name, outcome.roll.stat_value) == ("dangerous", 2)


def test_a_connection_without_a_bond_gives_develop_your_relationship_nothing_to_roll(load_engine: None) -> None:
    from straightjacket.engine.ruleset.moves import get_moves
    from straightjacket.engine.ruleset.roll_sources import roll_source_without_stat

    game = _starforged()
    game.progress_tracks.append(new_track(id="connection_npc_1", name="Vex", track_type="connection", rank="dangerous"))
    develop = get_moves("starforged")["connection/develop_your_relationship"]
    assert roll_source_without_stat(game, develop, "npc_1") is None
