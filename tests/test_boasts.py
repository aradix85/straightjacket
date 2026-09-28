import json

import pytest

from straightjacket.engine.models import RollResult
from tests._helpers import make_brain_result, make_game_state

_MOVE = "relationship/draw_the_circle"


def _duel(result: str, boasts: list[str]) -> tuple[int, int, list[str]]:
    from straightjacket.engine.game.finalization import resolve_action_consequences

    game = make_game_state(setting_id="classic")
    momentum, health = game.resources.momentum, game.resources.health
    brain = make_brain_result(move=_MOVE, stat="heart", boasts=boasts)
    roll = RollResult(3, 1, 9, "heart", 2, 5, result, _MOVE, match=False)
    outcome = resolve_action_consequences(game, brain, roll, "risky")
    return game.resources.momentum - momentum, game.resources.health - health, outcome.consequences


def test_a_strong_hit_takes_momentum_and_up_to_two_boasts(load_engine: None) -> None:
    momentum, health, consequences = _duel("STRONG_HIT", ["bloody_yourself", "to_the_death"])
    assert momentum == 3
    assert health == -1
    assert any("bloody yourself" in c for c in consequences)
    assert any("to the death" in c for c in consequences)


def test_a_weak_hit_gives_momentum_only_for_one_boast(load_engine: None) -> None:
    assert _duel("WEAK_HIT", [])[0] == 0
    momentum, _health, consequences = _duel("WEAK_HIT", ["hold_no_iron", "bare_yourself"])
    assert momentum == 1
    assert any("hold no iron" in c for c in consequences)
    assert not any("bare yourself" in c for c in consequences)


def test_a_miss_ignores_boasts(load_engine: None) -> None:
    _momentum, _health, consequences = _duel("MISS", ["to_the_death"])
    assert not any("to the death" in c for c in consequences)


def test_the_brain_offers_the_boasts_of_the_rules(load_engine: None) -> None:
    from straightjacket.engine.ai.schemas import get_brain_output_schema
    from straightjacket.engine.engine_loader import eng

    boasts = get_brain_output_schema([_MOVE], [], [], [])["properties"]["boasts"]
    assert boasts["items"]["enum"] == sorted(eng().boasts.options)
    assert len(boasts["items"]["enum"]) == 5
    assert boasts["maxItems"] == 2


def test_the_brain_rejects_an_unknown_boast(load_engine: None) -> None:
    from straightjacket.engine.ai.brain import call_brain
    from straightjacket.engine.ai.provider_base import AIUnavailableError
    from tests._mocks import MockProvider
    from tests.test_fact_resolution import _brain, _game

    content = json.dumps(_brain(undetermined_facts=[], boasts=["fight_naked"]))
    with pytest.raises(AIUnavailableError, match="boasts"):
        call_brain(MockProvider(response_content=content), _game(), "I challenge him")
