#!/usr/bin/env python3
"""Engine resolvers: position, effect, time progression, move category."""

from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, GameState
from ..npc import find_npc, get_npc_bond


def resolve_position(game: GameState, brain: BrainResult) -> str:
    """Engine-computed position from game state. Replaces Brain's position field.

    Weighted scoring: each factor adds a signed weight. Sum maps to position
    via thresholds. Situational overrides apply after the sum for edge cases.
    """
    cfg = eng().position_resolver
    w = cfg.weights
    score = 0

    # Resource pressure
    res = game.resources
    for val in (res.health, res.spirit, res.supply):
        if val < w.resource_critical_below:
            score += w.resource_critical
        elif val < w.resource_low_below:
            score += w.resource_low

    # NPC disposition + bond (only when move targets an NPC)
    if brain.target_npc:
        target = find_npc(game, brain.target_npc)
        if target:
            disp_weights = {
                "hostile": w.npc_hostile,
                "distrustful": w.npc_distrustful,
                "friendly": w.npc_friendly,
                "loyal": w.npc_loyal,
            }
            score += disp_weights.get(target.disposition, 0)
            if get_npc_bond(game, target.id) >= 3:
                score += w.npc_bond_high
            elif get_npc_bond(game, target.id) <= 0:
                score += w.npc_bond_low

    # Chaos factor
    if game.world.chaos_factor >= 7:
        score += w.chaos_high
    elif game.world.chaos_factor <= 3:
        score += w.chaos_low

    # Recent roll momentum (consecutive results from session log)
    recent = game.narrative.session_log[-3:] if game.narrative.session_log else []
    recent_results = [e.result for e in recent if e.result]
    if len(recent_results) >= 2 and all(r == "MISS" for r in recent_results[-2:]):
        score += w.consecutive_misses
    elif len(recent_results) >= 2 and all(r == "STRONG_HIT" for r in recent_results[-2:]):
        score += w.consecutive_strong

    # Threat pressure (clocks at >= 75% filled)
    threat_penalty = 0
    for clock in game.world.clocks:
        if not clock.fired and clock.segments > 0 and clock.filled / clock.segments >= 0.75:
            threat_penalty += w.threat_clock_critical
    score += max(threat_penalty, w.threat_clock_critical * 2)  # cap at 2 clocks

    # Secured advantage (previous move was secure_advantage with a hit)
    if recent and recent[-1].move == "secure_advantage" and recent[-1].result in ("STRONG_HIT", "WEAK_HIT"):
        score += w.secured_advantage

    # Move category baseline
    move = brain.move
    cat = move_category(move)
    score += cfg.move_baselines.get(cat, cfg.move_baselines.get("other", 0))

    # Map sum to position
    if score <= cfg.desperate_below:
        position = "desperate"
    elif score >= cfg.controlled_above:
        position = "controlled"
    else:
        position = "risky"

    # Situational overrides
    has_secured = bool(
        recent and recent[-1].move == "secure_advantage" and recent[-1].result in ("STRONG_HIT", "WEAK_HIT")
    )
    any_resource_critical = any(v < w.resource_critical_below for v in (res.health, res.spirit, res.supply))

    for override in cfg.overrides:
        _cond_checks: dict[str, bool] = {
            "secured_advantage": has_secured,
            "any_resource_critical": any_resource_critical,
            "crisis_mode": game.crisis_mode,
            "recovery_move": cat == "recovery",
            "previous_match": bool(recent and recent[-1].result and getattr(recent[-1], "match", False)),
            "same_target_npc": bool(
                recent and brain.target_npc and getattr(recent[-1], "target_npc", None) == brain.target_npc
            ),
        }
        match = all(_cond_checks.get(cond, False) for cond in override.conditions)

        if match and override.conditions:
            if override.effect == "cap_at_risky" and position == "controlled":  # noqa: SIM114
                position = "risky"
            elif override.effect == "floor_at_risky" and position == "desperate":
                position = "risky"
            elif override.effect == "shift_up_one":
                if position == "desperate":
                    position = "risky"
                elif position == "risky":
                    position = "controlled"
            log(f"[Position] Override '{override.name}' applied → {position}")

    log(f"[Position] score={score}, position={position} (move={move}, cat={cat})")
    return position


def resolve_effect(game: GameState, brain: BrainResult, position: str) -> str:
    """Engine-computed effect from game state + resolved position."""
    cfg = eng().effect_resolver
    w = cfg.weights
    score = 0

    # Position correlation
    pos_weights = {"desperate": w.desperate, "controlled": w.controlled}
    score += pos_weights.get(position, 0)

    # NPC bond (social moves)
    if brain.target_npc:
        target = find_npc(game, brain.target_npc)
        if target:
            if get_npc_bond(game, target.id) >= 3:
                score += w.bond_high
            elif get_npc_bond(game, target.id) <= 0:
                score += w.bond_low

    # Secured advantage
    recent = game.narrative.session_log[-1:] if game.narrative.session_log else []
    if recent and recent[0].move == "secure_advantage" and recent[0].result in ("STRONG_HIT", "WEAK_HIT"):
        score += w.secured_advantage

    # Move baseline
    score += cfg.move_baselines.get(brain.move, cfg.move_baselines.get("other", 0))

    # Map to effect
    if score <= cfg.limited_below:
        effect = "limited"
    elif score >= cfg.great_above:
        effect = "great"
    else:
        effect = "standard"

    log(f"[Effect] score={score}, effect={effect} (position={position}, move={brain.move})")
    return effect


def resolve_time_progression(move: str, has_location_change: bool = False) -> str:
    """Engine-computed time progression from move type. No AI needed."""
    _e = eng()
    tmap = _e.get_raw("time_progression_map", {})
    if has_location_change:
        return tmap.get("_with_location_change", "long")
    return tmap.get(move, tmap.get("_default", "short"))


def move_category(move: str) -> str:
    """Classify a move into its category for resolver lookups."""
    _e = eng()
    mc = _e.get_raw("move_categories", {})
    for cat in ("combat", "social", "endure", "recovery"):
        if move in mc.get(cat, []):
            return cat
    return "other"
