#!/usr/bin/env python3
"""Tests for Mythic GME 2e fate system: chart, check, likelihood, tool.

Run: python -m pytest tests/test_fate.py -v
"""

# Stubs are set up in conftest.py

import pytest

from straightjacket.engine.mechanics.fate import (
    ODDS_LEVELS,
    _check_chart_random_event,
    _check_check_random_event,
    resolve_fate,
    resolve_fate_chart,
    resolve_fate_check,
    resolve_likelihood,
)
from tests._helpers import make_game_state, make_npc


# ── Fate chart method ────────────────────────────────────────


def test_fate_chart_four_outcomes() -> None:
    """All four outcome branches at fifty_fifty CF5."""
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=10).answer == "exceptional_yes"
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=30).answer == "yes"
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=60).answer == "no"
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=91).answer == "exceptional_no"


def test_fate_chart_certain_high_chaos() -> None:
    """Certain at CF9: yes threshold 99, no exceptional_no possible."""
    assert resolve_fate_chart("certain", chaos_factor=9, roll=99).answer == "yes"
    assert resolve_fate_chart("certain", chaos_factor=9, roll=20).answer == "exceptional_yes"
    assert resolve_fate_chart("certain", chaos_factor=9, roll=100).answer == "no"


def test_fate_chart_impossible_low_chaos() -> None:
    """Impossible at CF1: yes threshold 1, no exceptional_yes possible."""
    assert resolve_fate_chart("impossible", chaos_factor=1, roll=1).answer == "yes"
    assert resolve_fate_chart("impossible", chaos_factor=1, roll=2).answer == "no"


def test_fate_chart_null_thresholds() -> None:
    """Null exceptional thresholds: cannot produce that outcome."""
    # Certain CF7+: exceptional_no is None
    assert resolve_fate_chart("certain", chaos_factor=7, roll=100).answer == "no"
    # Impossible CF1: exceptional_yes is None
    assert resolve_fate_chart("impossible", chaos_factor=1, roll=1).answer == "yes"


def test_fate_chart_unknown_odds_raises() -> None:
    """Unknown odds level raises — no silent fallback on domain data."""
    with pytest.raises(KeyError, match="Unknown odds level"):
        resolve_fate_chart("totally_bonkers", chaos_factor=5, roll=50)


# ── Fate chart random event trigger ──────────────────────────


def test_chart_random_event_doublet_logic() -> None:
    """Doublet rule: doublet AND digit <= CF triggers event."""
    assert _check_chart_random_event(33, 5) is True  # 3 <= 5
    assert _check_chart_random_event(77, 5) is False  # 7 > 5
    assert _check_chart_random_event(34, 9) is False  # not a doublet
    assert _check_chart_random_event(100, 1) is True  # 00: digit 0 always <= CF
    assert _check_chart_random_event(11, 1) is True  # 1 <= 1
    assert _check_chart_random_event(22, 1) is False  # 2 > 1
    assert _check_chart_random_event(5, 9) is False  # below 11, not a doublet


# ── Fate check method ────────────────────────────────────────


def test_fate_check_four_outcomes() -> None:
    """All four outcome branches via controlled dice."""
    # fifty_fifty CF5: mods=0. dice sum determines outcome directly.
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(10, 10)).answer == "exceptional_yes"
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(6, 5)).answer == "yes"
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(3, 4)).answer == "no"
    # unlikely CF4: odds=-1, cf=-1. dice=(3,3): 3+3-1-1=4 → exceptional_no
    assert resolve_fate_check("unlikely", chaos_factor=4, dice=(3, 3)).answer == "exceptional_no"


def test_fate_check_exceptional_priority() -> None:
    """Exceptional No (2-4) takes priority over No (<=10)."""
    # very_unlikely CF4: odds=-2, cf=-1. dice=(3,3): 3+3-2-1=3
    result = resolve_fate_check("very_unlikely", chaos_factor=4, dice=(3, 3))
    assert result.answer == "exceptional_no"


def test_fate_check_modifiers_shift_outcome() -> None:
    """Odds and chaos modifiers shift identical dice to different outcomes."""
    # Same dice (5,5), different context
    assert resolve_fate_check("likely", chaos_factor=6, dice=(5, 5)).answer == "yes"  # 5+5+1+1=12
    assert resolve_fate_check("unlikely", chaos_factor=4, dice=(5, 5)).answer == "no"  # 5+5-1-1=8


# ── Fate check random event trigger ─────────────────────────


def test_check_random_event_doublet_logic() -> None:
    """Both dice same AND digit <= CF triggers event."""
    assert _check_check_random_event(3, 3, 5) is True  # 3 <= 5
    assert _check_check_random_event(7, 7, 5) is False  # 7 > 5
    assert _check_check_random_event(3, 4, 9) is False  # different dice
    assert _check_check_random_event(1, 1, 1) is True  # 1 <= 1


# ── Random event in FateResult ───────────────────────────────


def test_fate_results_carry_random_event_flag() -> None:
    """FateResult.random_event_triggered reflects doublet detection for both methods."""
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=33).random_event_triggered is True
    assert resolve_fate_chart("fifty_fifty", chaos_factor=5, roll=34).random_event_triggered is False
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(3, 3)).random_event_triggered is True
    assert resolve_fate_check("fifty_fifty", chaos_factor=5, dice=(3, 4)).random_event_triggered is False


# ── Unified resolver ─────────────────────────────────────────


def test_resolve_fate_method_override(load_engine: None) -> None:
    """Explicit method parameter overrides engine.yaml default."""
    game = make_game_state()
    game.world.chaos_factor = 5
    chart = resolve_fate(game, "fifty_fifty", chaos_factor=5, method="fate_chart")
    check = resolve_fate(game, "fifty_fifty", chaos_factor=5, method="fate_check")
    assert chart.method == "fate_chart"
    assert check.method == "fate_check"


# ── Exhaustive coverage ──────────────────────────────────────


def test_fate_chart_all_odds_all_cf() -> None:
    """Every (odds, CF) combination resolves without error at boundary rolls."""
    for odds in ODDS_LEVELS:
        for cf in range(1, 10):
            for roll in (1, 50, 100):
                result = resolve_fate_chart(odds, cf, roll=roll)
                assert result.answer in ("yes", "no", "exceptional_yes", "exceptional_no")


def test_fate_check_all_odds_all_cf() -> None:
    """Every (odds, CF) combination resolves without error at edge dice."""
    for odds in ODDS_LEVELS:
        for cf in range(1, 10):
            for dice in ((1, 1), (5, 5), (10, 10), (1, 10)):
                result = resolve_fate_check(odds, cf, dice=dice)
                assert result.answer in ("yes", "no", "exceptional_yes", "exceptional_no")


# ── Likelihood resolver ──────────────────────────────────────


def test_likelihood_default_fifty_fifty(load_engine: None) -> None:
    """No context factors → fifty_fifty."""
    game = make_game_state()
    game.world.chaos_factor = 5
    assert resolve_likelihood(game) == "fifty_fifty"


def test_likelihood_npc_disposition_shifts_odds(load_engine: None) -> None:
    """NPC disposition in context_hint shifts odds in expected direction."""
    game = make_game_state()
    game.world.chaos_factor = 5

    friendly = make_npc(id="npc_1", name="Kira", status="active", disposition="friendly")
    game.npcs = [friendly]
    friendly_odds = resolve_likelihood(game, context_hint="Kira")

    hostile = make_npc(id="npc_1", name="Kira", status="active", disposition="hostile")
    game.npcs = [hostile]
    hostile_odds = resolve_likelihood(game, context_hint="Kira")

    assert ODDS_LEVELS.index(friendly_odds) < ODDS_LEVELS.index(hostile_odds)


def test_likelihood_chaos_shifts_odds(load_engine: None) -> None:
    """High chaos shifts down, low chaos shifts up."""
    high = make_game_state()
    high.world.chaos_factor = 8
    low = make_game_state()
    low.world.chaos_factor = 2

    high_odds = resolve_likelihood(high)
    low_odds = resolve_likelihood(low)
    assert ODDS_LEVELS.index(low_odds) < ODDS_LEVELS.index(high_odds)


def test_likelihood_critical_resources(load_engine: None) -> None:
    """Critical health contributes negative score (stacks with other factors)."""
    game = make_game_state()
    game.world.chaos_factor = 5
    game.resources.health = 1
    odds_critical = resolve_likelihood(game)

    game2 = make_game_state()
    game2.world.chaos_factor = 5
    game2.resources.health = 5
    odds_healthy = resolve_likelihood(game2)

    # Critical should be same or worse than healthy
    assert ODDS_LEVELS.index(odds_critical) >= ODDS_LEVELS.index(odds_healthy)


def test_likelihood_factors_stack(load_engine: None) -> None:
    """Multiple negative factors produce strongly unfavorable odds."""
    game = make_game_state()
    game.world.chaos_factor = 8
    game.resources.health = 1
    npc = make_npc(id="npc_1", name="Kira", status="active", disposition="hostile")
    game.npcs.append(npc)
    odds = resolve_likelihood(game, context_hint="Kira")
    assert odds in ("very_unlikely", "nearly_impossible", "impossible")


# ── Tool integration ─────────────────────────────────────────


def test_fate_question_tool_end_to_end(load_engine: None) -> None:
    """fate_question tool resolves likelihood, rolls fate, returns structured result."""
    from straightjacket.engine.tools.builtins import fate_question

    game = make_game_state()
    game.world.chaos_factor = 5
    npc = make_npc(id="npc_1", name="Kira", status="active", disposition="loyal")
    game.npcs.append(npc)

    result = fate_question(game, question="Does Kira help?", context_hint="Kira")
    assert result["answer"] in ("yes", "no", "exceptional_yes", "exceptional_no")
    assert result["question"] == "Does Kira help?"
    assert result["odds"] in ("likely", "very_likely", "nearly_certain", "certain")
