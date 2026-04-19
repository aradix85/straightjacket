#!/usr/bin/env python3
"""Tests for Mythic GME 2e scene structure: chaos check, altered, interrupt.

Run: python -m pytest tests/test_scene.py -v
"""

# Stubs are set up in conftest.py

from straightjacket.engine.mechanics.scene import (
    SceneSetup,
    _roll_adjustments,
    adjustment_descriptions,
    check_scene,
)
from tests._helpers import make_game_state, make_random_event


# ── Scene test (chaos check) ────────────────────────────────


def test_expected_when_roll_above_cf() -> None:
    """Roll > CF → expected scene."""
    game = make_game_state()
    game.world.chaos_factor = 5
    setup = check_scene(game, roll=6)
    assert setup.scene_type == "expected"


def test_expected_when_roll_is_10() -> None:
    """Roll 10 is always expected regardless of CF."""
    game = make_game_state()
    game.world.chaos_factor = 9
    setup = check_scene(game, roll=10)
    assert setup.scene_type == "expected"


def test_altered_when_roll_le_cf_odd() -> None:
    """Roll ≤ CF and odd → altered scene."""
    game = make_game_state()
    game.world.chaos_factor = 5
    setup = check_scene(game, roll=3)
    assert setup.scene_type == "altered"
    assert len(setup.adjustments) >= 1


def test_interrupt_when_roll_le_cf_even() -> None:
    """Roll ≤ CF and even → interrupt scene with random event."""
    game = make_game_state()
    game.world.chaos_factor = 5
    setup = check_scene(game, roll=4)
    assert setup.scene_type == "interrupt"
    assert setup.interrupt_event is not None
    assert setup.interrupt_event.source == "interrupt_scene"
    assert setup.interrupt_event.focus != ""


def test_cf1_only_roll1_triggers() -> None:
    """At CF1, only roll=1 (odd, ≤1) triggers altered. Roll 2+ is expected."""
    game = make_game_state()
    game.world.chaos_factor = 1
    assert check_scene(game, roll=1).scene_type == "altered"
    assert check_scene(game, roll=2).scene_type == "expected"


def test_cf9_most_rolls_trigger() -> None:
    """At CF9, rolls 1-9 trigger altered/interrupt. Only 10 is expected."""
    game = make_game_state()
    game.world.chaos_factor = 9
    assert check_scene(game, roll=10).scene_type == "expected"
    assert check_scene(game, roll=9).scene_type == "altered"  # 9 odd
    assert check_scene(game, roll=8).scene_type == "interrupt"  # 8 even


def test_chaos_roll_stored() -> None:
    """SceneSetup records the chaos roll."""
    game = make_game_state()
    game.world.chaos_factor = 5
    setup = check_scene(game, roll=7)
    assert setup.chaos_roll == 7


# ── Scene adjustments ────────────────────────────────────────


def test_single_adjustment() -> None:
    """Rolls 1-6 produce a single adjustment."""
    for roll in range(1, 7):
        adjs = _roll_adjustments(roll)
        assert len(adjs) == 1
        assert adjs[0] != "make_2_adjustments"


def test_double_adjustment() -> None:
    """Rolls 7-10 produce two adjustments, each from 1-6 range."""
    adjs = _roll_adjustments(7)
    assert len(adjs) == 2
    for a in adjs:
        assert a != "make_2_adjustments"


def test_adjustment_types() -> None:
    """All six single adjustment types map to d10 values 1-6."""
    expected = {
        "remove_character",
        "add_character",
        "reduce_activity",
        "increase_activity",
        "remove_object",
        "add_object",
    }
    seen = set()
    for roll in range(1, 7):
        adjs = _roll_adjustments(roll)
        seen.add(adjs[0])
    assert seen == expected


def test_adjustment_descriptions_maps_all() -> None:
    """Every adjustment type has a narrator description."""
    types = ["remove_character", "add_character", "reduce_activity", "increase_activity", "remove_object", "add_object"]
    descs = adjustment_descriptions(types)
    assert len(descs) == 6
    for d in descs:
        assert len(d) > 10  # non-trivial description


# ── SceneSetup serialization ─────────────────────────────────


def test_scene_setup_roundtrip() -> None:
    """SceneSetup with adjustments round-trips through to_dict/from_dict."""
    setup = SceneSetup(scene_type="altered", chaos_roll=3, adjustments=["add_character", "remove_object"])
    d = setup.to_dict()
    restored = SceneSetup.from_dict(d)
    assert restored.scene_type == "altered"
    assert restored.chaos_roll == 3
    assert restored.adjustments == ["add_character", "remove_object"]


def test_scene_setup_interrupt_roundtrip() -> None:
    """SceneSetup with interrupt event round-trips."""

    event = make_random_event(focus="npc_action", meaning_action="Betray", meaning_subject="Trust")
    setup = SceneSetup(scene_type="interrupt", chaos_roll=4, interrupt_event=event)
    d = setup.to_dict()
    restored = SceneSetup.from_dict(d)
    assert restored.scene_type == "interrupt"
    assert restored.interrupt_event is not None
    assert restored.interrupt_event.focus == "npc_action"
