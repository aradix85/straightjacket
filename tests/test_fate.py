import pytest

from straightjacket.engine.mechanics.fate import (
    _check_chart_random_event,
    _check_check_random_event,
    get_odds_levels,
    resolve_fate,
    resolve_fate_chart,
    resolve_fate_check,
    resolve_likelihood,
)
from tests._helpers import make_game_state, make_npc


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
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(10, 10), question="").answer == "exceptional_yes"
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(6, 5), question="").answer == "yes"
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(3, 4), question="").answer == "no"

    assert resolve_fate_check("unlikely", chaos_factor=4, dice=(3, 3), question="").answer == "exceptional_no"


def test_fate_check_exceptional_priority() -> None:
    result = resolve_fate_check("very_unlikely", chaos_factor=4, dice=(3, 3), question="")
    assert result.answer == "exceptional_no"


def test_fate_check_modifiers_shift_outcome() -> None:
    assert resolve_fate_check("likely", chaos_factor=6, dice=(5, 5), question="").answer == "yes"
    assert resolve_fate_check("unlikely", chaos_factor=4, dice=(5, 5), question="").answer == "no"


def test_check_random_event_doublet_logic() -> None:
    assert _check_check_random_event(3, 3, 5) is True
    assert _check_check_random_event(7, 7, 5) is False
    assert _check_check_random_event(3, 4, 9) is False
    assert _check_check_random_event(1, 1, 1) is True


def test_fate_results_carry_random_event_flag() -> None:
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=33, question="").random_event_triggered is True
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=34, question="").random_event_triggered is False
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(3, 3), question="").random_event_triggered is True
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(3, 4), question="").random_event_triggered is False


def test_resolve_fate_method_override(load_engine: None) -> None:
    game = make_game_state()
    game.world.chaos_factor = 5
    chart = resolve_fate(game, "fifty_fifty", chaos_factor=5, method="fate_chart", question="")
    check = resolve_fate(game, "fifty_fifty", chaos_factor=5, method="fate_check", question="")
    assert chart.method == "fate_chart"
    assert check.method == "fate_check"


def test_fate_chart_all_odds_all_cf(load_engine: None) -> None:
    for odds in get_odds_levels():
        for cf in range(1, 10):
            for roll in (1, 50, 100):
                result = resolve_fate_chart(odds, cf, roll=roll, question="")
                assert result.answer in ("yes", "no", "exceptional_yes", "exceptional_no")


def test_fate_check_all_odds_all_cf(load_engine: None) -> None:
    for odds in get_odds_levels():
        for cf in range(1, 10):
            for dice in ((1, 1), (5, 5), (10, 10), (1, 10)):
                result = resolve_fate_check(odds, cf, dice=dice, question="")
                assert result.answer in ("yes", "no", "exceptional_yes", "exceptional_no")


def test_likelihood_default_fifty_fifty(load_engine: None) -> None:
    game = make_game_state()
    game.world.chaos_factor = 5
    assert resolve_likelihood(game) == "fifty_fifty"


def test_likelihood_npc_disposition_shifts_odds(load_engine: None) -> None:
    game = make_game_state()
    game.world.chaos_factor = 5

    friendly = make_npc(id="npc_1", name="Kira", status="active", disposition="friendly")
    game.npcs = [friendly]
    friendly_odds = resolve_likelihood(game, context_hint="Kira")

    hostile = make_npc(id="npc_1", name="Kira", status="active", disposition="hostile")
    game.npcs = [hostile]
    hostile_odds = resolve_likelihood(game, context_hint="Kira")

    assert get_odds_levels().index(friendly_odds) < get_odds_levels().index(hostile_odds)


def test_likelihood_chaos_shifts_odds(load_engine: None) -> None:
    high = make_game_state()
    high.world.chaos_factor = 8
    low = make_game_state()
    low.world.chaos_factor = 2

    high_odds = resolve_likelihood(high)
    low_odds = resolve_likelihood(low)
    assert get_odds_levels().index(low_odds) < get_odds_levels().index(high_odds)


def test_likelihood_critical_resources(load_engine: None) -> None:
    game = make_game_state()
    game.world.chaos_factor = 5
    game.resources.health = 1
    odds_critical = resolve_likelihood(game)

    game2 = make_game_state()
    game2.world.chaos_factor = 5
    game2.resources.health = 5
    odds_healthy = resolve_likelihood(game2)

    assert get_odds_levels().index(odds_critical) >= get_odds_levels().index(odds_healthy)


def test_likelihood_factors_stack(load_engine: None) -> None:
    game = make_game_state()
    game.world.chaos_factor = 8
    game.resources.health = 1
    npc = make_npc(id="npc_1", name="Kira", status="active", disposition="hostile")
    game.npcs.append(npc)
    odds = resolve_likelihood(game, context_hint="Kira")
    assert odds in ("very_unlikely", "nearly_impossible", "impossible")


def test_fate_question_tool_end_to_end(load_engine: None) -> None:
    from straightjacket.engine.tools.builtins import fate_question

    game = make_game_state()
    game.world.chaos_factor = 5
    npc = make_npc(id="npc_1", name="Kira", status="active", disposition="loyal")
    game.npcs.append(npc)

    result = fate_question(game, question="Does Kira help?", context_hint="Kira")
    assert result["answer"] in ("yes", "no", "exceptional_yes", "exceptional_no")
    assert result["question"] == "Does Kira help?"
    assert result["odds"] in ("likely", "very_likely", "nearly_certain", "certain")
