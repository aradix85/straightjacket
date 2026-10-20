import pytest

from straightjacket.engine.models import GameState, Resources, labels_of
from straightjacket.engine.ruleset.move_outcome import resolve_move_outcome
from tests._helpers import fix_dice, make_game_state

STRONG_FOCUS = (6, 1, 1)
WEAK_FOCUS = (2, 3, 10)
MISSED_FOCUS = (1, 10, 10)


def _game(health: int, spirit: int, supply: int, impacts: list[str]) -> GameState:
    game = make_game_state(player_name="Hero", setting_id="classic")
    game.resources = Resources(
        meters={"health": health, "spirit": spirit, "supply": supply, "momentum": 2}, next_move_bonus=0
    )
    game.impacts = list(impacts)
    return game


def _sojourn(game: GameState, result: str, aided_by: str | None) -> list[str]:
    outcome = resolve_move_outcome(
        game, "relationship/sojourn", result, target_npc_id=None, aided_by=aided_by, match=False
    )
    return labels_of(outcome.consequences)


def test_a_strong_hit_takes_two_recoveries_for_the_lowest_meters_and_focuses_the_first(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _game(health=1, spirit=3, supply=5, impacts=[])
    fix_dice(monkeypatch, *STRONG_FOCUS)
    labels = _sojourn(game, "STRONG_HIT", None)
    assert labels == ["Recuperate, rolled again: STRONG_HIT", "health +4", "spirit +2"]
    assert (game.resources.meters["health"], game.resources.meters["spirit"]) == (5, 5)


def test_a_weak_hit_clears_the_oldest_condition_first(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game(health=2, spirit=2, supply=5, impacts=["shaken", "wounded"])
    fix_dice(monkeypatch, *WEAK_FOCUS)
    labels = _sojourn(game, "WEAK_HIT", None)
    assert labels == ["Hearten, rolled again: WEAK_HIT", "clear shaken", "spirit +2"]
    assert (game.impacts, game.resources.meters["health"]) == (["wounded"], 2)


def test_a_missed_focus_loses_that_benefit_only(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    game = _game(health=2, spirit=2, supply=5, impacts=["wounded"])
    fix_dice(monkeypatch, *MISSED_FOCUS)
    labels = _sojourn(game, "STRONG_HIT", None)
    assert labels == ["Mend, rolled again: MISS", "Mend goes badly; its benefit is lost", "spirit +2"]
    assert game.impacts == ["wounded"]
    assert (game.resources.meters["health"], game.resources.meters["spirit"]) == (2, 4)


def test_a_shared_bond_adds_a_pick_and_one_to_the_focus_roll(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = _game(health=1, spirit=5, supply=5, impacts=[])
    fix_dice(monkeypatch, 5, 7, 7)
    labels = _sojourn(game, "WEAK_HIT", "npc_1")
    assert labels == ["Recuperate, rolled again: STRONG_HIT", "health +4", "momentum +2"]


def test_a_miss_pays_the_price(load_engine: None) -> None:
    labels = _sojourn(_game(health=5, spirit=5, supply=5, impacts=[]), "MISS", None)
    assert labels[0].startswith("Pay the Price: ")


def test_a_sojourn_aided_by_a_bond_takes_its_extra_pick_through_a_turn(
    load_engine: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from straightjacket.engine.game import process_turn
    from straightjacket.engine.ruleset import sojourn
    from straightjacket.engine.ruleset.bond import seal_bond
    from tests._creation import TurnProvider, brain_answer, fixed_roll, force_result, library_game

    game = library_game()
    seal_bond(game, game.npcs[0])
    game.resources.meters.update({"health": 1, "spirit": 5, "supply": 5})
    force_result(monkeypatch, "WEAK_HIT")
    monkeypatch.setattr(sojourn, "roll_action", fixed_roll("STRONG_HIT"))
    brain = brain_answer(
        move="relationship/sojourn",
        stat="heart",
        bonus_id="connection:npc_1",
        player_intent="I rest a while in Mira's village",
        location_change=None,
    )
    process_turn(TurnProvider(brain), game, "I rest a while in Mira's village", None)
    labels = labels_of(game.narrative.session_log[-1].consequences)
    assert labels[:3] == ["Recuperate, rolled again: STRONG_HIT", "health +4", "momentum +2"]
