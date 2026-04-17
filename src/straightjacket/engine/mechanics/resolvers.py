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
    _e = eng()
    cfg = _e.position_resolver
    w = cfg.weights
    chaos_cfg = _e.chaos_resolver
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
    if game.world.chaos_factor >= chaos_cfg.high_threshold:
        score += w.chaos_high
    elif game.world.chaos_factor <= chaos_cfg.low_threshold:
        score += w.chaos_low

    # Recent roll momentum (consecutive results from session log)
    recent = game.narrative.session_log[-chaos_cfg.recent_session_window :] if game.narrative.session_log else []
    recent_results = [e.result for e in recent if e.result]
    streak = chaos_cfg.recent_result_window
    if len(recent_results) >= streak and all(r == "MISS" for r in recent_results[-streak:]):
        score += w.consecutive_misses
    elif len(recent_results) >= streak and all(r == "STRONG_HIT" for r in recent_results[-streak:]):
        score += w.consecutive_strong

    # Threat pressure (clocks at or above pressure threshold filled)
    threat_penalty = 0
    for clock in game.world.clocks:
        if (
            not clock.fired
            and clock.segments > 0
            and clock.filled / clock.segments >= chaos_cfg.clock_pressure_threshold
        ):
            threat_penalty += w.threat_clock_critical
    score += max(threat_penalty, w.threat_clock_critical * chaos_cfg.clock_pressure_cap_multiplier)

    # Secured advantage (previous move was secure_advantage with a hit)
    if recent and recent[-1].move == "secure_advantage" and recent[-1].result in ("STRONG_HIT", "WEAK_HIT"):
        score += w.secured_advantage

    # Move category baseline — move_baselines is a plain dict; 'other' is the
    # canonical bucket for un-categorised moves and is required in yaml.
    cat = move_category(brain.move)
    score += cfg.move_baselines[cat] if cat in cfg.move_baselines else cfg.move_baselines["other"]

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

    log(f"[Position] score={score}, position={position} (move={brain.move}, cat={cat})")
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

    # Move baseline — move_baselines requires an 'other' entry in yaml.
    score += cfg.move_baselines[brain.move] if brain.move in cfg.move_baselines else cfg.move_baselines["other"]

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
    """Engine-computed time progression from move type. No AI needed.

    Yaml-authoritative: `time_progression_map` must define every move and the
    `_with_location_change` / `_default` fallbacks.
    """
    tmap = eng().get_raw("time_progression_map")
    if has_location_change:
        return tmap["_with_location_change"]
    return tmap[move] if move in tmap else tmap["_default"]


def move_category(move: str) -> str:
    """Classify a move into its category for resolver lookups.

    Returns 'other' for any move not listed in `move_categories`. The 'other'
    bucket is intentionally implicit — it's the default category, not a yaml
    entry.
    """
    mc = eng().get_raw("move_categories")
    for cat in ("combat", "social", "endure", "recovery"):
        if move in mc[cat]:
            return cat
    return "other"
