from typing import Any

import pytest

from tests._creation import TurnProvider, brain_answer, library_game
from tests._helpers import fix_dice


@pytest.fixture
def dice(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    from straightjacket.engine.game import turn
    from straightjacket.engine.ruleset import make_move
    from straightjacket.engine.ruleset.rolls import score_action_roll

    counts = {"rolls": 0, "scenes": 0, "scene_roll": 10}
    real_scene = turn.check_scene

    def _roll(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> Any:
        counts["rolls"] += 1
        return score_action_roll(3, 4, 6, stat_name, stat_value, move, momentum, adds)

    def _scene(game: Any) -> Any:
        counts["scenes"] += 1
        fix_dice(monkeypatch, counts["scene_roll"])
        return real_scene(game)

    monkeypatch.setattr(make_move, "roll_action", _roll)
    monkeypatch.setattr(turn, "check_scene", _scene)
    return counts


def _turn_then_correct(provider: TurnProvider) -> tuple[Any, Any, str, Any]:
    import copy

    from straightjacket.engine.correction import process_correction
    from straightjacket.engine.game import process_turn

    game = library_game()
    _n, _r, _o, _d = process_turn(provider, game, "I slip into the vault", stream=None)
    before = copy.deepcopy(game)
    narration, offer, _director = process_correction(provider, game, "I meant I use force")
    return before, game, narration, offer


def test_a_misread_correction_keeps_the_dice_and_scores_the_new_stat(
    load_engine: None, stub_emotions: None, dice: dict[str, int]
) -> None:
    before, game, _narration, _offer = _turn_then_correct(TurnProvider(brain_answer(), brain_answer(stat="iron")))

    assert before.narrative.session_log[-1].result == "WEAK_HIT"
    assert game.narrative.session_log[-1].result == "MISS"
    snap = game.last_turn_snapshot
    assert snap is not None
    assert snap.roll is not None
    assert (snap.roll.d1, snap.roll.c1, snap.roll.c2, snap.roll.stat_name) == (3, 4, 6, "iron")
    assert dice["rolls"] == 1


def test_a_misread_correction_with_the_same_stat_keeps_its_result(
    load_engine: None, stub_emotions: None, dice: dict[str, int]
) -> None:
    _before, game, _narration, _offer = _turn_then_correct(TurnProvider(brain_answer(), brain_answer()))

    last = game.narrative.session_log[-1]
    assert (last.move, last.result) == ("adventure/face_danger", "WEAK_HIT")


def test_a_misread_correction_keeps_the_scene_and_carries_the_correction_to_the_narrator(
    load_engine: None, stub_emotions: None, dice: dict[str, int]
) -> None:
    dice["scene_roll"] = 2
    provider = TurnProvider(brain_answer(), brain_answer(stat="iron"))
    _turn_then_correct(provider)

    assert dice["scenes"] == 1
    assert "<interrupt_scene" in provider.prompts[-1]
    assert "<correction_context>" in provider.prompts[-1]


def test_a_corrected_miss_can_offer_a_burn(load_engine: None, stub_emotions: None, dice: dict[str, int]) -> None:
    _before, _game_after, _narration, offer = _turn_then_correct(
        TurnProvider(brain_answer(), brain_answer(stat="iron"))
    )

    assert offer is not None
    assert offer.new_result == "WEAK_HIT"


def test_elvira_accepts_a_replayed_turn_and_a_burn(
    load_engine: None, stub_emotions: None, dice: dict[str, int]
) -> None:
    import copy

    from straightjacket.engine.game import process_momentum_burn
    from tests.elvira.elvira_bot.invariants import check_turn_replacement

    before, game, narration, offer = _turn_then_correct(TurnProvider(brain_answer(), brain_answer(stat="iron")))
    assert check_turn_replacement(before, game, narration, 1, "correction", keeps_location=False) == []

    assert offer is not None
    before_burn = copy.deepcopy(game)
    narration, _director = process_momentum_burn(TurnProvider(brain_answer(stat="iron")), game, offer)
    assert check_turn_replacement(before_burn, game, narration, 1, "momentum burn", keeps_location=True) == []
