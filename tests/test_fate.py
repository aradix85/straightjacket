import pytest

from straightjacket.engine.engine_loader import eng
from straightjacket.engine.mechanics.fate import (
    _check_chart_random_event,
    _check_check_random_event,
    resolve_fate,
    resolve_fate_chart,
    resolve_fate_check_with_dice,
    score_to_odds,
)
from tests._helpers import make_game_state


def test_fate_chart_four_outcomes() -> None:
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=10, question="").answer == "exceptional_yes"
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=30, question="").answer == "yes"
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=60, question="").answer == "no"
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=91, question="").answer == "exceptional_no"


def test_fate_chart_certain_high_chaos() -> None:
    assert resolve_fate_chart("certain", chaos_factor=9, roll=99, question="").answer == "yes"
    assert resolve_fate_chart("certain", chaos_factor=9, roll=20, question="").answer == "exceptional_yes"
    assert resolve_fate_chart("certain", chaos_factor=9, roll=100, question="").answer == "no"


def test_fate_chart_impossible_low_chaos() -> None:
    assert resolve_fate_chart("impossible", chaos_factor=1, roll=1, question="").answer == "yes"
    assert resolve_fate_chart("impossible", chaos_factor=1, roll=2, question="").answer == "no"


def test_fate_chart_null_thresholds() -> None:
    assert resolve_fate_chart("certain", chaos_factor=7, roll=100, question="").answer == "no"

    assert resolve_fate_chart("impossible", chaos_factor=1, roll=1, question="").answer == "yes"


def test_fate_chart_unknown_odds_raises() -> None:
    with pytest.raises(KeyError, match="Unknown odds level"):
        resolve_fate_chart("totally_bonkers", chaos_factor=5, roll=50, question="")


def test_chart_random_event_doublet_logic() -> None:
    assert _check_chart_random_event(33, 5) is True
    assert _check_chart_random_event(77, 5) is False
    assert _check_chart_random_event(34, 9) is False
    assert _check_chart_random_event(100, 1) is True
    assert _check_chart_random_event(11, 1) is True
    assert _check_chart_random_event(22, 1) is False
    assert _check_chart_random_event(5, 9) is False


def test_fate_check_four_outcomes() -> None:
    assert (
        resolve_fate_check_with_dice("fifty_fifty", chaos_factor=5, dice=(10, 10), question="").answer
        == "exceptional_yes"
    )
    assert resolve_fate_check_with_dice("fifty_fifty", chaos_factor=5, dice=(6, 5), question="").answer == "yes"
    assert resolve_fate_check_with_dice("fifty_fifty", chaos_factor=5, dice=(3, 4), question="").answer == "no"

    assert resolve_fate_check_with_dice("unlikely", chaos_factor=4, dice=(3, 3), question="").answer == "exceptional_no"


def test_fate_check_exceptional_priority() -> None:
    result = resolve_fate_check_with_dice("very_unlikely", chaos_factor=4, dice=(3, 3), question="")
    assert result.answer == "exceptional_no"


def test_fate_check_modifiers_shift_outcome() -> None:
    assert resolve_fate_check_with_dice("likely", chaos_factor=6, dice=(5, 5), question="").answer == "yes"
    assert resolve_fate_check_with_dice("unlikely", chaos_factor=4, dice=(5, 5), question="").answer == "no"


def test_check_random_event_doublet_logic() -> None:
    assert _check_check_random_event(3, 3, 5) is True
    assert _check_check_random_event(7, 7, 5) is False
    assert _check_check_random_event(3, 4, 9) is False
    assert _check_check_random_event(1, 1, 1) is True


def test_fate_results_carry_random_event_flag() -> None:
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=33, question="").random_event_triggered is True
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=34, question="").random_event_triggered is False
    assert (
        resolve_fate_check_with_dice("fifty_fifty", chaos_factor=5, dice=(3, 3), question="").random_event_triggered
        is True
    )
    assert (
        resolve_fate_check_with_dice("fifty_fifty", chaos_factor=5, dice=(3, 4), question="").random_event_triggered
        is False
    )


def test_resolve_fate_method_override(load_engine: None) -> None:
    game = make_game_state()
    game.world.chaos_factor = 5
    chart = resolve_fate(game, "fifty_fifty", chaos_factor=5, method="fate_chart", question="")
    check = resolve_fate(game, "fifty_fifty", chaos_factor=5, method="fate_check", question="")
    assert chart.method == "fate_chart"
    assert check.method == "fate_check"


def test_fate_chart_all_odds_all_cf(load_engine: None) -> None:
    for odds in eng().enums.odds_levels:
        for cf in range(1, 10):
            for roll in (1, 50, 100):
                result = resolve_fate_chart(odds, cf, roll=roll, question="")
                assert result.answer in ("yes", "no", "exceptional_yes", "exceptional_no")


def test_fate_check_all_odds_all_cf(load_engine: None) -> None:
    for odds in eng().enums.odds_levels:
        for cf in range(1, 10):
            for dice in ((1, 1), (5, 5), (10, 10), (1, 10)):
                result = resolve_fate_check_with_dice(odds, cf, dice=dice, question="")
                assert result.answer in ("yes", "no", "exceptional_yes", "exceptional_no")


def test_score_to_odds_covers_the_scale(load_engine: None) -> None:
    assert score_to_odds(10) == "certain"
    assert score_to_odds(3) == "very_likely"
    assert score_to_odds(0) == "fifty_fifty"
    assert score_to_odds(-2) == "unlikely"
    assert score_to_odds(-99) == "impossible"


def test_score_below_the_catch_all_raises(load_engine: None) -> None:
    with pytest.raises(ValueError, match="no matching threshold"):
        score_to_odds(-100)
