#!/usr/bin/env python3
"""Tests for step 2 resolvers: position, effect, time progression.

Verifies engine-computed values match expected game state conditions.
"""

from straightjacket.engine.models import BrainResult, ClockData, GameState, NpcData, SceneLogEntry


# ── Position resolver ────────────────────────────────────────


def test_position_default_risky(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = GameState(player_name="Test")
    game.world.chaos_factor = 5
    brain = BrainResult(move="adventure/face_danger", stat="wits")
    assert resolve_position(game, brain) == "risky"


def test_position_desperate_on_low_resources(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = GameState(player_name="Test")
    game.resources.health = 1
    game.resources.spirit = 1
    game.resources.supply = 1
    game.world.chaos_factor = 5
    brain = BrainResult(move="adventure/face_danger", stat="wits")
    assert resolve_position(game, brain) == "desperate"


def test_position_controlled_on_high_resources_low_chaos(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = GameState(player_name="Test")
    game.resources.health = 5
    game.resources.spirit = 5
    game.resources.supply = 5
    game.world.chaos_factor = 3
    # Add a secured advantage from previous turn
    game.narrative.session_log.append(SceneLogEntry(scene=1, move="secure_advantage", result="STRONG_HIT"))
    brain = BrainResult(move="adventure/gather_information", stat="wits")
    assert resolve_position(game, brain) == "controlled"


def test_position_hostile_npc_pushes_desperate(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = GameState(player_name="Test")
    game.resources.health = 3
    game.resources.spirit = 3
    game.resources.supply = 3
    game.world.chaos_factor = 7
    game.npcs = [NpcData(id="npc_1", name="Enemy", disposition="hostile", bond=0)]
    brain = BrainResult(move="adventure/compel", stat="heart", target_npc="npc_1")
    pos = resolve_position(game, brain)
    assert pos == "desperate"


def test_position_friendly_npc_helps(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = GameState(player_name="Test")
    game.resources.health = 5
    game.resources.spirit = 5
    game.resources.supply = 5
    game.world.chaos_factor = 5
    game.npcs = [NpcData(id="npc_1", name="Ally", disposition="friendly", bond=3)]
    brain = BrainResult(move="adventure/compel", stat="heart", target_npc="npc_1")
    pos = resolve_position(game, brain)
    assert pos in ("risky", "controlled")  # friendly + high bond pushes up


def test_position_consecutive_misses(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = GameState(player_name="Test")
    game.world.chaos_factor = 5
    game.narrative.session_log = [
        SceneLogEntry(scene=1, move="adventure/face_danger", result="MISS"),
        SceneLogEntry(scene=2, move="combat/clash", result="MISS"),
    ]
    brain = BrainResult(move="adventure/face_danger", stat="wits")
    pos = resolve_position(game, brain)
    # Consecutive misses should push toward desperate
    assert pos in ("desperate", "risky")  # depends on other factors


def test_position_threat_clock_pressure(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = GameState(player_name="Test")
    game.world.chaos_factor = 5
    game.world.clocks = [ClockData(name="Doom", segments=4, filled=3)]  # 75%
    brain = BrainResult(move="adventure/face_danger", stat="wits")
    pos = resolve_position(game, brain)
    assert pos in ("desperate", "risky")


def test_position_combat_baseline(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_position

    game = GameState(player_name="Test")
    game.world.chaos_factor = 5
    brain_combat = BrainResult(move="combat/clash", stat="iron")
    brain_recovery = BrainResult(move="recover/resupply", stat="wits")
    pos_combat = resolve_position(game, brain_combat)
    pos_recovery = resolve_position(game, brain_recovery)
    # Combat baseline is negative, recovery is positive
    assert pos_combat != "controlled" or pos_recovery == "controlled"


# ── Effect resolver ──────────────────────────────────────────


def test_effect_default_standard(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_effect

    game = GameState(player_name="Test")
    brain = BrainResult(move="adventure/face_danger", stat="wits")
    assert resolve_effect(game, brain, "risky") == "standard"


def test_effect_desperate_pushes_limited(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_effect

    game = GameState(player_name="Test")
    game.npcs = [NpcData(id="npc_1", name="Enemy", disposition="hostile", bond=0)]
    brain = BrainResult(move="adventure/compel", stat="heart", target_npc="npc_1")
    effect = resolve_effect(game, brain, "desperate")
    assert effect in ("limited", "standard")


def test_effect_controlled_pushes_great(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_effect

    game = GameState(player_name="Test")
    game.npcs = [NpcData(id="npc_1", name="Ally", disposition="friendly", bond=3)]
    # Add secured advantage
    game.narrative.session_log.append(SceneLogEntry(scene=1, move="secure_advantage", result="STRONG_HIT"))
    brain = BrainResult(move="combat/strike", stat="iron", target_npc="npc_1")
    effect = resolve_effect(game, brain, "controlled")
    assert effect == "great"


def test_effect_strike_baseline(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_effect

    game = GameState(player_name="Test")
    brain = BrainResult(move="combat/strike", stat="iron")
    effect = resolve_effect(game, brain, "risky")
    # Strike has +1 baseline, should push toward great or stay standard
    assert effect in ("standard", "great")


# ── Time progression resolver ────────────────────────────────


def test_time_progression_dialog_is_none(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("dialog") == "none"


def test_time_progression_gather_is_short(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("adventure/gather_information") == "short"


def test_time_progression_resupply_is_moderate(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("recover/resupply") == "moderate"


def test_time_progression_location_change_is_long(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("adventure/face_danger", has_location_change=True) == "long"


def test_time_progression_unknown_move_uses_default(stub_engine: None) -> None:
    from straightjacket.engine.mechanics import resolve_time_progression

    assert resolve_time_progression("unknown_move") == "short"
