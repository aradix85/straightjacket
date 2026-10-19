from typing import Any

import pytest

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.fate import (
    _check_chart_random_event,
    _check_check_random_event,
    resolve_fate,
    resolve_fate_chart,
    resolve_fate_check,
    score_to_odds,
)
from straightjacket.engine.models import FateResult
from tests._helpers import fix_dice, make_game_state


def _chart(monkeypatch: pytest.MonkeyPatch, odds: str, chaos_factor: int, roll: int) -> FateResult:
    fix_dice(monkeypatch, roll)
    return resolve_fate_chart(odds, chaos_factor)


def _check(monkeypatch: pytest.MonkeyPatch, odds: str, chaos_factor: int, dice: tuple[int, int]) -> FateResult:
    fix_dice(monkeypatch, *dice)
    return resolve_fate_check(odds, chaos_factor)


def test_fate_chart_four_outcomes(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _chart(monkeypatch, "fifty_fifty", 5, 10).answer == "exceptional_yes"
    assert _chart(monkeypatch, "fifty_fifty", 5, 30).answer == "yes"
    assert _chart(monkeypatch, "fifty_fifty", 5, 60).answer == "no"
    assert _chart(monkeypatch, "fifty_fifty", 5, 91).answer == "exceptional_no"


def test_fate_chart_certain_high_chaos(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _chart(monkeypatch, "certain", 9, 99).answer == "yes"
    assert _chart(monkeypatch, "certain", 9, 20).answer == "exceptional_yes"
    assert _chart(monkeypatch, "certain", 9, 100).answer == "no"


def test_fate_chart_impossible_low_chaos(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _chart(monkeypatch, "impossible", 1, 1).answer == "yes"
    assert _chart(monkeypatch, "impossible", 1, 2).answer == "no"


def test_fate_chart_null_thresholds(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _chart(monkeypatch, "certain", 7, 100).answer == "no"
    assert _chart(monkeypatch, "impossible", 1, 1).answer == "yes"


def test_fate_chart_unknown_odds_raises() -> None:
    with pytest.raises(KeyError, match="Unknown odds level"):
        resolve_fate_chart("totally_bonkers", chaos_factor=5)


def test_chart_random_event_doublet_logic() -> None:
    assert _check_chart_random_event(33, 5) is True
    assert _check_chart_random_event(77, 5) is False
    assert _check_chart_random_event(34, 9) is False
    assert _check_chart_random_event(100, 1) is True
    assert _check_chart_random_event(11, 1) is True
    assert _check_chart_random_event(22, 1) is False
    assert _check_chart_random_event(5, 9) is False


def test_fate_check_four_outcomes(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _check(monkeypatch, "fifty_fifty", 5, (10, 10)).answer == "exceptional_yes"
    assert _check(monkeypatch, "fifty_fifty", 5, (6, 5)).answer == "yes"
    assert _check(monkeypatch, "fifty_fifty", 5, (3, 4)).answer == "no"
    assert _check(monkeypatch, "unlikely", 4, (3, 3)).answer == "exceptional_no"


def test_fate_check_exceptional_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _check(monkeypatch, "very_unlikely", 4, (3, 3)).answer == "exceptional_no"


def test_fate_check_modifiers_shift_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _check(monkeypatch, "likely", 6, (5, 5)).answer == "yes"
    assert _check(monkeypatch, "unlikely", 4, (5, 5)).answer == "no"


def test_check_random_event_doublet_logic() -> None:
    assert _check_check_random_event(3, 3, 5) is True
    assert _check_check_random_event(7, 7, 5) is False
    assert _check_check_random_event(3, 4, 9) is False
    assert _check_check_random_event(1, 1, 1) is True


def test_fate_results_carry_random_event_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _chart(monkeypatch, "fifty_fifty", 5, 33).random_event_triggered is True
    assert _chart(monkeypatch, "fifty_fifty", 5, 34).random_event_triggered is False
    assert _check(monkeypatch, "fifty_fifty", 5, (3, 3)).random_event_triggered is True
    assert _check(monkeypatch, "fifty_fifty", 5, (3, 4)).random_event_triggered is False


def test_resolve_fate_follows_the_configured_method(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from straightjacket.engine.gamemaster import fate

    game = make_game_state()
    game.world.chaos_factor = 7
    asked: list[tuple[str, str, int]] = []

    def answering(method: str) -> Any:
        def resolve(odds: str, chaos_factor: int) -> FateResult:
            asked.append((method, odds, chaos_factor))
            return FateResult(answer="yes", random_event_triggered=False)

        return resolve

    monkeypatch.setattr(fate, "resolve_fate_chart", answering("fate_chart"))
    monkeypatch.setattr(fate, "resolve_fate_check", answering("fate_check"))
    for method in ("fate_chart", "fate_check"):
        monkeypatch.setattr(gm().fate, "default_method", method)
        resolve_fate(game, "fifty_fifty")
    assert asked == [("fate_chart", "fifty_fifty", 7), ("fate_check", "fifty_fifty", 7)]


def _odds_scale() -> list[str]:
    return [entry["odds"] for entry in gm().fate.likelihood_rules.score_to_odds]


def test_fate_chart_all_odds_all_cf(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    for odds in _odds_scale():
        for cf in range(1, 10):
            for roll in (1, 50, 100):
                assert _chart(monkeypatch, odds, cf, roll).answer in ("yes", "no", "exceptional_yes", "exceptional_no")


def test_fate_check_all_odds_all_cf(load_engine: None, monkeypatch: pytest.MonkeyPatch) -> None:
    for odds in _odds_scale():
        for cf in range(1, 10):
            for dice in ((1, 1), (5, 5), (10, 10), (1, 10)):
                assert _check(monkeypatch, odds, cf, dice).answer in ("yes", "no", "exceptional_yes", "exceptional_no")


def test_score_to_odds_covers_the_scale(load_engine: None) -> None:
    assert score_to_odds(10) == "certain"
    assert score_to_odds(3) == "very_likely"
    assert score_to_odds(0) == "fifty_fifty"
    assert score_to_odds(-2) == "unlikely"
    assert score_to_odds(-99) == "impossible"


def test_score_below_the_catch_all_raises(load_engine: None) -> None:
    with pytest.raises(ValueError, match="no matching threshold"):
        score_to_odds(-100)
