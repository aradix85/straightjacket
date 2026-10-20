import pytest

from straightjacket.engine.models import GameState, labels_of
from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
from tests._creation import library_game


def _bonded(game: GameState) -> GameState:
    from straightjacket.engine.ruleset.bond import seal_bond

    seal_bond(game, game.npcs[0])
    return game


@pytest.mark.parametrize(("result", "marks"), [("STRONG_HIT", 2), ("WEAK_HIT", 1)])
def test_classic_strike_inflicts_one_harm_more_on_a_strong_hit(load_engine: None, result: str, marks: int) -> None:
    outcome = resolve_move_outcome(library_game(), "combat/strike", result, target_npc_id=None, match=False)
    assert outcome.progress_marks == marks


@pytest.mark.parametrize(
    ("setting", "labels"),
    [("classic", ["momentum -2", "obstacle"]), ("starforged", ["obstacle"])],
)
def test_a_missed_vow_meets_an_obstacle_and_classic_presses_on(
    load_engine: None, setting: str, labels: list[str]
) -> None:
    from tests._helpers import make_game_state

    game = make_game_state(setting_id=setting)
    outcome = resolve_move_outcome(game, "quest/swear_an_iron_vow", "MISS", target_npc_id=None, match=False)
    assert labels_of(outcome.consequences) == labels


def test_classic_test_your_bond_asks_loyalty_on_a_weak_hit(load_engine: None) -> None:
    from straightjacket.engine.ruleset.bond import connection_track

    game = _bonded(library_game())
    outcome = resolve_move_outcome(game, "relationship/test_your_bond", "WEAK_HIT", target_npc_id="npc_1", match=False)
    assert labels_of(outcome.consequences) == ["loyalty_test"]
    assert connection_track(game, "npc_1") is not None


def test_a_missed_test_of_a_classic_bond_clears_it(load_engine: None) -> None:
    from straightjacket.engine.gamemaster.questions import answers

    game = _bonded(library_game())
    outcome = resolve_move_outcome(game, "relationship/test_your_bond", "MISS", target_npc_id="npc_1", match=False)
    labels = labels_of(outcome.consequences)
    assert labels[0] == "Mira: bond cleared"
    assert labels[1].startswith("Pay the Price: ")
    assert answers().closeness(game, "npc_1") == 0


def test_test_your_bond_is_offered_only_with_a_bond(load_engine: None) -> None:
    from straightjacket.engine.ruleset.move_availability import available_moves

    game = library_game()
    assert "relationship/test_your_bond" not in available_moves(game)
    assert "relationship/test_your_bond" in available_moves(_bonded(game))


def test_a_cleared_bond_can_be_sealed_again(load_engine: None) -> None:
    from straightjacket.engine.ruleset.bond import connection_track, seal_bond

    game = _bonded(library_game())
    resolve_move_outcome(game, "relationship/test_your_bond", "MISS", target_npc_id="npc_1", match=False)
    assert not [t for t in game.progress_tracks if t.track_type == "connection"]
    seal_bond(game, game.npcs[0])
    assert [t.id for t in game.progress_tracks if t.track_type == "connection"] == ["connection_npc_1"]
    assert connection_track(game, "npc_1") is not None


def test_the_brain_may_not_test_a_bond_with_someone_who_shares_none(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_brain
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from tests._creation import TurnProvider, brain_answer
    from tests._helpers import make_npc

    game = _bonded(library_game())
    game.npcs.append(make_npc(id="npc_2", name="Orla"))
    provider = TurnProvider(brain_answer(move="relationship/test_your_bond", stat="heart", target_npc="npc_2"))
    with pytest.raises(AIUnavailableError, match="needs a connection"):
        call_brain(provider, game, "I ask Orla to stand by me.")
