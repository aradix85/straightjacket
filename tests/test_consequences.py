#!/usr/bin/env python3
"""Tests for apply_consequences: every move category × position × result type.

Verifies damage table lookups, resource clamping, clock ticking,
bond loss/gain, disposition shifts, momentum changes, and crisis detection.

Run: python -m pytest tests/test_consequences.py -v
"""

from straightjacket.engine import engine_loader
from straightjacket.engine.models import (
    BrainResult,
    ClockData,
    GameState,
    NpcData,
    RollResult,
)


def _load_engine() -> None:
    """Load real engine.yaml (not a stub) for damage table accuracy."""
    engine_loader._eng = None
    engine_loader.eng()


def _game(health: int = 5, spirit: int = 5, supply: int = 5, momentum: int = 3) -> GameState:
    game = GameState(player_name="Hero")
    game.resources.health = health
    game.resources.spirit = spirit
    game.resources.supply = supply
    game.resources.momentum = momentum
    game.resources.max_momentum = 10
    game.narrative.scene_count = 5
    game.world.chaos_factor = 5
    return game


def _roll(move: str, result: str, stat: str = "wits") -> RollResult:
    return RollResult(
        d1=3, d2=3, c1=5, c2=5, stat_name=stat, stat_value=2, action_score=8, result=result, move=move, match=False
    )


def _brain(position: str = "risky", effect: str = "standard", target_npc: str | None = None) -> BrainResult:
    return BrainResult(position=position, effect=effect, target_npc=target_npc)


# ── MISS: combat moves ───────────────────────────────────────


def test_miss_clash_risky_damages_health() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    roll = _roll("clash", "MISS")
    cons, _ = apply_consequences(game, roll, _brain("risky"))
    assert game.resources.health < 5
    assert any("health" in c for c in cons)


def test_miss_strike_desperate_damages_health_more() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game_risky = _game()
    game_desp = _game()
    apply_consequences(game_risky, _roll("strike", "MISS"), _brain("risky"))
    apply_consequences(game_desp, _roll("strike", "MISS"), _brain("desperate"))
    assert game_desp.resources.health < game_risky.resources.health


def test_miss_combat_controlled_less_damage() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    apply_consequences(game, _roll("clash", "MISS"), _brain("controlled"))
    # controlled combat miss = 1 damage (from engine.yaml)
    assert game.resources.health == 4


# ── MISS: social moves ───────────────────────────────────────


def test_miss_compel_loses_bond_and_spirit() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    npc = NpcData(id="npc_1", name="Kira", bond=3, bond_max=4)
    game.npcs = [npc]
    roll = _roll("compel", "MISS")
    cons, _ = apply_consequences(game, roll, _brain("risky", target_npc="npc_1"))
    assert npc.bond < 3
    assert game.resources.spirit < 5
    assert any("bond" in c for c in cons)
    assert any("spirit" in c for c in cons)


def test_miss_social_bond_floor_zero() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    npc = NpcData(id="npc_1", name="Kira", bond=0, bond_max=4)
    game.npcs = [npc]
    roll = _roll("test_bond", "MISS")
    apply_consequences(game, roll, _brain("risky", target_npc="npc_1"))
    assert npc.bond == 0


# ── MISS: endure_harm / endure_stress ─────────────────────────


def test_miss_endure_harm_damages_health() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    apply_consequences(game, _roll("endure_harm", "MISS"), _brain("risky"))
    assert game.resources.health < 5


def test_miss_endure_stress_damages_spirit() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    apply_consequences(game, _roll("endure_stress", "MISS"), _brain("risky"))
    assert game.resources.spirit < 5


# ── MISS: generic move (face_danger etc.) ─────────────────────


def test_miss_face_danger_damages_supply_and_maybe_health() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    apply_consequences(game, _roll("face_danger", "MISS"), _brain("risky"))
    assert game.resources.supply < 5


def test_miss_face_danger_controlled_no_health_loss() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    apply_consequences(game, _roll("face_danger", "MISS"), _brain("controlled"))
    # controlled other.health = 0 in engine.yaml
    assert game.resources.health == 5


# ── MISS: momentum always lost ────────────────────────────────


def test_miss_always_loses_momentum() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(momentum=5)
    apply_consequences(game, _roll("dialog", "MISS"), _brain("risky"))
    assert game.resources.momentum < 5
    assert any(
        "momentum" in c for c in apply_consequences(_game(momentum=5), _roll("clash", "MISS"), _brain("risky"))[0]
    )


# ── MISS: clock ticking ──────────────────────────────────────


def test_miss_ticks_threat_clock() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    clock = ClockData(name="Doom", clock_type="threat", segments=6, filled=2)
    game.world.clocks = [clock]
    apply_consequences(game, _roll("clash", "MISS"), _brain("risky"))
    assert clock.filled > 2


def test_miss_desperate_ticks_clock_more() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    clock = ClockData(name="Doom", clock_type="threat", segments=6, filled=2)
    game.world.clocks = [clock]
    apply_consequences(game, _roll("clash", "MISS"), _brain("desperate"))
    assert clock.filled >= 4  # desperate = 2 ticks


def test_miss_controlled_no_clock_tick() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    clock = ClockData(name="Doom", clock_type="threat", segments=6, filled=2)
    game.world.clocks = [clock]
    apply_consequences(game, _roll("clash", "MISS"), _brain("controlled"))
    assert clock.filled == 2  # controlled = 0 ticks


def test_miss_clock_fires_when_full() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    clock = ClockData(name="Doom", clock_type="threat", segments=4, filled=3, trigger_description="Darkness falls")
    game.world.clocks = [clock]
    _, clock_events = apply_consequences(game, _roll("clash", "MISS"), _brain("risky"))
    assert clock.fired is True
    assert len(clock_events) >= 1
    assert clock_events[0].clock == "Doom"


# ── WEAK_HIT ─────────────────────────────────────────────────


def test_weak_hit_gains_momentum() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(momentum=2)
    apply_consequences(game, _roll("face_danger", "WEAK_HIT"), _brain("risky"))
    assert game.resources.momentum > 2


def test_weak_hit_endure_harm_heals() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(health=3)
    apply_consequences(game, _roll("endure_harm", "WEAK_HIT"), _brain("risky"))
    assert game.resources.health > 3


def test_weak_hit_resupply_heals() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(supply=2)
    apply_consequences(game, _roll("resupply", "WEAK_HIT"), _brain("risky"))
    assert game.resources.supply > 2


def test_weak_hit_make_connection_gains_bond() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    npc = NpcData(id="npc_1", name="Kira", bond=1, bond_max=4)
    game.npcs = [npc]
    apply_consequences(game, _roll("make_connection", "WEAK_HIT"), _brain("risky", target_npc="npc_1"))
    assert npc.bond == 2


def test_weak_hit_desperate_ticks_clock() -> None:
    """WEAK_HIT at desperate position always ticks threat clock."""
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    clock = ClockData(name="Doom", clock_type="threat", segments=6, filled=2)
    game.world.clocks = [clock]
    apply_consequences(game, _roll("face_danger", "WEAK_HIT"), _brain("desperate"))
    assert clock.filled > 2


def test_weak_hit_controlled_no_clock_tick() -> None:
    """WEAK_HIT at controlled position never ticks threat clock."""
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    clock = ClockData(name="Doom", clock_type="threat", segments=6, filled=2)
    game.world.clocks = [clock]
    apply_consequences(game, _roll("face_danger", "WEAK_HIT"), _brain("controlled"))
    assert clock.filled == 2


# ── STRONG_HIT ────────────────────────────────────────────────


def test_strong_hit_gains_momentum() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(momentum=2)
    apply_consequences(game, _roll("face_danger", "STRONG_HIT"), _brain("risky"))
    assert game.resources.momentum > 2


def test_strong_hit_great_effect_more_momentum() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game_std = _game(momentum=2)
    game_great = _game(momentum=2)
    apply_consequences(game_std, _roll("face_danger", "STRONG_HIT"), _brain(effect="standard"))
    apply_consequences(game_great, _roll("face_danger", "STRONG_HIT"), _brain(effect="great"))
    assert game_great.resources.momentum > game_std.resources.momentum


def test_strong_hit_endure_harm_heals() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(health=2)
    apply_consequences(game, _roll("endure_harm", "STRONG_HIT"), _brain("risky"))
    assert game.resources.health > 2


def test_strong_hit_compel_gains_bond_no_disposition() -> None:
    """v0.9.86: compel STRONG_HIT grants bond+1 but NOT disposition shift."""
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    npc = NpcData(id="npc_1", name="Kira", bond=1, bond_max=4, disposition="neutral")
    game.npcs = [npc]
    apply_consequences(game, _roll("compel", "STRONG_HIT"), _brain("risky", target_npc="npc_1"))
    assert npc.bond == 2
    assert npc.disposition == "neutral"  # NOT friendly


def test_strong_hit_test_bond_gains_bond_and_disposition() -> None:
    """v0.9.86: test_bond STRONG_HIT grants bond+1 AND disposition shift."""
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    npc = NpcData(id="npc_1", name="Kira", bond=1, bond_max=4, disposition="neutral")
    game.npcs = [npc]
    apply_consequences(game, _roll("test_bond", "STRONG_HIT"), _brain("risky", target_npc="npc_1"))
    assert npc.bond == 2
    assert npc.disposition == "friendly"


def test_strong_hit_make_connection_disposition_shift() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    npc = NpcData(id="npc_1", name="Kira", bond=0, bond_max=4, disposition="distrustful")
    game.npcs = [npc]
    apply_consequences(game, _roll("make_connection", "STRONG_HIT"), _brain("risky", target_npc="npc_1"))
    assert npc.bond == 1
    assert npc.disposition == "neutral"


# ── Crisis detection ──────────────────────────────────────────


def test_crisis_when_health_zero() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(health=1)
    apply_consequences(game, _roll("endure_harm", "MISS"), _brain("risky"))
    assert game.crisis_mode is True
    assert game.game_over is False  # spirit still > 0


def test_game_over_when_both_zero() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(health=1, spirit=1)
    # Two misses to drain both
    apply_consequences(game, _roll("endure_harm", "MISS"), _brain("desperate"))
    apply_consequences(game, _roll("endure_stress", "MISS"), _brain("desperate"))
    if game.resources.health <= 0 and game.resources.spirit <= 0:
        assert game.game_over is True


def test_crisis_clears_when_resources_recover() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(health=1, spirit=5)
    apply_consequences(game, _roll("endure_harm", "MISS"), _brain("risky"))
    assert game.crisis_mode is True
    # Recover health
    apply_consequences(game, _roll("endure_harm", "STRONG_HIT"), _brain("risky"))
    if game.resources.health > 0 and game.resources.spirit > 0:
        assert game.crisis_mode is False


# ── Resource clamping ─────────────────────────────────────────


def test_health_never_goes_below_zero() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game(health=1)
    apply_consequences(game, _roll("clash", "MISS"), _brain("desperate"))
    assert game.resources.health >= 0


def test_bond_capped_at_bond_max() -> None:
    _load_engine()
    from straightjacket.engine.mechanics import apply_consequences

    game = _game()
    npc = NpcData(id="npc_1", name="Kira", bond=4, bond_max=4, disposition="loyal")
    game.npcs = [npc]
    apply_consequences(game, _roll("test_bond", "STRONG_HIT"), _brain("risky", target_npc="npc_1"))
    assert npc.bond == 4  # capped


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
