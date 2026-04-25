"""Engine resolvers: position, effect, time progression, move category."""

from __future__ import annotations

from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, GameState
from ..npc import find_npc, get_npc_bond


def _score_resource_pressure(game: GameState) -> int:
    """Each of health/spirit/supply contributes a signed weight based on critical/low thresholds."""
    w = eng().position_resolver.weights
    score = 0
    res = game.resources
    for val in (res.health, res.spirit, res.supply):
        if val < w.resource_critical_below:
            score += w.resource_critical
        elif val < w.resource_low_below:
            score += w.resource_low
    return score


def _score_npc_relationship(game: GameState, brain: BrainResult) -> int:
    """Score the relationship with a target NPC (disposition + bond extremes)."""
    if not brain.target_npc:
        return 0
    target = find_npc(game, brain.target_npc)
    if not target:
        return 0
    cfg = eng().position_resolver
    score = cfg.disposition_weights[target.disposition]
    bond = get_npc_bond(game, target.id)
    w = cfg.weights
    if bond >= cfg.npc_bond_high_min:
        score += w.npc_bond_high
    elif bond <= cfg.npc_bond_low_max:
        score += w.npc_bond_low
    return score


def _score_chaos_factor(chaos_factor: int) -> int:
    """High chaos worsens position, low chaos improves it."""
    _e = eng()
    w = _e.position_resolver.weights
    chaos_cfg = _e.chaos_resolver
    if chaos_factor >= chaos_cfg.high_threshold:
        return w.chaos_high
    if chaos_factor <= chaos_cfg.low_threshold:
        return w.chaos_low
    return 0


def _score_recent_streak(recent_results: list[str]) -> int:
    """Consecutive misses push toward desperate; consecutive strong hits toward controlled."""
    _e = eng()
    w = _e.position_resolver.weights
    streak = _e.chaos_resolver.recent_result_window
    if len(recent_results) < streak:
        return 0
    tail = recent_results[-streak:]
    if all(r == "MISS" for r in tail):
        return w.consecutive_misses
    if all(r == "STRONG_HIT" for r in tail):
        return w.consecutive_strong
    return 0


def _score_threat_clocks(game: GameState) -> int:
    """Every clock at/above pressure threshold adds threat_clock_critical, capped
    by cap_multiplier — so a cascade of threats doesn't spiral out of control.
    """
    _e = eng()
    w = _e.position_resolver.weights
    chaos_cfg = _e.chaos_resolver
    penalty = 0
    for clock in game.world.clocks:
        if (
            not clock.fired
            and clock.segments > 0
            and clock.filled / clock.segments >= chaos_cfg.clock_pressure_threshold
        ):
            penalty += w.threat_clock_critical
    return max(penalty, w.threat_clock_critical * chaos_cfg.clock_pressure_cap_multiplier)


def _score_secured_advantage(recent_log: list) -> int:
    """Previous successful secure_advantage move grants a position bonus."""
    w = eng().position_resolver.weights
    if recent_log and recent_log[-1].move == "secure_advantage" and recent_log[-1].result in ("STRONG_HIT", "WEAK_HIT"):
        return w.secured_advantage
    return 0


def _score_move_category_baseline(cat: str) -> int:
    """Move-category baseline — 'other' is the canonical bucket for un-categorised moves."""
    cfg = eng().position_resolver
    return cfg.move_baselines[cat] if cat in cfg.move_baselines else cfg.move_baselines["other"]


def _score_position_factors(game: GameState, brain: BrainResult, cat: str) -> int:
    """Sum all signed weights that contribute to position: resources,
    NPC relationship, chaos factor, recent roll streak, threat clocks,
    secured advantage, move-category baseline.
    """
    chaos_cfg = eng().chaos_resolver
    recent = game.narrative.session_log[-chaos_cfg.recent_session_window :] if game.narrative.session_log else []
    recent_results = [e.result for e in recent if e.result]

    return (
        _score_resource_pressure(game)
        + _score_npc_relationship(game, brain)
        + _score_chaos_factor(game.world.chaos_factor)
        + _score_recent_streak(recent_results)
        + _score_threat_clocks(game)
        + _score_secured_advantage(recent)
        + _score_move_category_baseline(cat)
    )


def _map_score_to_position(score: int) -> str:
    """Threshold map from a score to controlled / risky / desperate."""
    cfg = eng().position_resolver
    if score <= cfg.desperate_below:
        return "desperate"
    if score >= cfg.controlled_above:
        return "controlled"
    return "risky"


def _apply_position_overrides(position: str, game: GameState, brain: BrainResult, cat: str) -> str:
    """Situational overrides applied after the threshold mapping.
    Effects: cap_at_risky, floor_at_risky, shift_up_one.
    """
    cfg = eng().position_resolver
    w = cfg.weights

    recent = (
        game.narrative.session_log[-eng().chaos_resolver.recent_session_window :] if game.narrative.session_log else []
    )
    res = game.resources
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
        match = all(_cond_checks[cond] for cond in override.conditions)

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

    return position


def resolve_position(game: GameState, brain: BrainResult) -> str:
    """Engine-computed position from game state. Replaces Brain's position field.

    Three phases: score the factors, map the sum to a position, then apply
    situational overrides for edge cases.
    """
    cat = move_category(brain.move)
    score = _score_position_factors(game, brain, cat)
    position = _map_score_to_position(score)
    position = _apply_position_overrides(position, game, brain, cat)
    log(f"[Position] score={score}, position={position} (move={brain.move}, cat={cat})")
    return position


def resolve_effect(game: GameState, brain: BrainResult, position: str) -> str:
    """Engine-computed effect from game state + resolved position."""
    cfg = eng().effect_resolver
    w = cfg.weights
    score = 0

    # Position correlation
    score += cfg.position_weights[position]

    # NPC bond (social moves)
    if brain.target_npc:
        target = find_npc(game, brain.target_npc)
        if target:
            bond = get_npc_bond(game, target.id)
            if bond >= cfg.bond_high_min:
                score += w.bond_high
            elif bond <= cfg.bond_low_max:
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
    `_with_location_change` / `_catchall` fallbacks.
    """
    tmap = eng().get_raw("time_progression_map")
    if has_location_change:
        return tmap["_with_location_change"]
    return tmap[move] if move in tmap else tmap["_catchall"]


def move_category(move: str) -> str:
    """Classify a move into its category for resolver lookups.

    Returns 'other' for any move not listed in `move_categories`. The 'other'
    bucket is intentionally implicit — it's the default category, not a yaml
    entry.
    """
    mc = eng().get_raw("move_categories")
    for cat in mc:
        if move in mc[cat]:
            return cat
    return "other"
