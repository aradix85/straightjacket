from __future__ import annotations

from typing import Any
from ..engine_loader import eng
from ..logging_util import log
from ..models import BrainResult, GameState, NpcData
from ..npc import find_npc, get_npc_bond


def _target_npc(game: GameState, brain: BrainResult) -> NpcData | None:
    if brain.target_npc is None:
        return None
    target = find_npc(game, brain.target_npc)
    if target is None:
        raise ValueError(f"Target NPC {brain.target_npc!r} is not in the game")
    return target


def _score_resource_pressure(game: GameState) -> int:
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
    target = _target_npc(game, brain)
    if target is None:
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
    _e = eng()
    w = _e.position_resolver.weights
    chaos_cfg = _e.chaos_resolver
    if chaos_factor >= chaos_cfg.high_threshold:
        return w.chaos_high
    if chaos_factor <= chaos_cfg.low_threshold:
        return w.chaos_low
    return 0


def _score_recent_streak(recent_results: list[str]) -> int:
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
    _e = eng()
    w = _e.position_resolver.weights
    chaos_cfg = _e.chaos_resolver
    penalty = 0
    for clock in game.world.clocks:
        if not clock.fired and clock.filled / clock.segments >= chaos_cfg.clock_pressure_threshold:
            penalty += w.threat_clock_critical
    return max(penalty, w.threat_clock_critical * chaos_cfg.clock_pressure_cap_multiplier)


def _secured_advantage(recent_log: list[Any]) -> bool:
    return bool(
        recent_log
        and recent_log[-1].move == eng().position_resolver.secured_advantage_move
        and recent_log[-1].result in eng().dice.hit_results
    )


def _score_secured_advantage(recent_log: list[Any]) -> int:
    return eng().position_resolver.weights.secured_advantage if _secured_advantage(recent_log) else 0


def _score_move_category_baseline(cat: str) -> int:
    return eng().position_resolver.move_baselines[cat]


def _score_position_factors(game: GameState, brain: BrainResult, cat: str) -> int:
    chaos_cfg = eng().chaos_resolver
    recent = game.narrative.session_log[-chaos_cfg.recent_session_window :]
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
    cfg = eng().position_resolver
    if score <= cfg.desperate_below:
        return "desperate"
    if score >= cfg.controlled_above:
        return "controlled"
    return "risky"


def _apply_position_overrides(position: str, game: GameState, cat: str) -> str:
    cfg = eng().position_resolver
    w = cfg.weights

    recent = game.narrative.session_log[-eng().chaos_resolver.recent_session_window :]
    res = game.resources
    conditions: dict[str, bool] = {
        "secured_advantage": _secured_advantage(recent),
        "any_resource_critical": any(v < w.resource_critical_below for v in (res.health, res.spirit, res.supply)),
        "crisis_mode": game.crisis_mode,
        "recovery_move": cat == "recovery",
    }

    for override in cfg.overrides:
        if all(conditions[cond] for cond in override.conditions):
            if (override.effect == "cap_at_risky" and position == "controlled") or (
                override.effect == "floor_at_risky" and position == "desperate"
            ):
                position = "risky"
            log(f"[Position] Override '{override.name}' applied → {position}")

    return position


def resolve_position(game: GameState, brain: BrainResult) -> str:
    cat = move_category(brain.move)
    score = _score_position_factors(game, brain, cat)
    position = _map_score_to_position(score)
    position = _apply_position_overrides(position, game, cat)
    log(f"[Position] score={score}, position={position} (move={brain.move}, cat={cat})")
    return position


def resolve_effect(game: GameState, brain: BrainResult, position: str) -> str:
    cfg = eng().effect_resolver
    w = cfg.weights
    score = 0

    score += cfg.position_weights[position]

    target = _target_npc(game, brain)
    if target is not None:
        bond = get_npc_bond(game, target.id)
        if bond >= cfg.bond_high_min:
            score += w.bond_high
        elif bond <= cfg.bond_low_max:
            score += w.bond_low

    if _secured_advantage(game.narrative.session_log[-1:]):
        score += w.secured_advantage

    score += cfg.move_baselines[brain.move] if brain.move in cfg.move_baselines else cfg.move_baselines["other"]

    if score <= cfg.limited_below:
        effect = "limited"
    elif score >= cfg.great_above:
        effect = "great"
    else:
        effect = "standard"

    log(f"[Effect] score={score}, effect={effect} (position={position}, move={brain.move})")
    return effect


def resolve_time_progression(move: str, has_location_change: bool) -> str:
    tmap = eng().get_raw("time_progression_map")
    if has_location_change:
        key = "_with_location_change"
    else:
        key = move if move in tmap else "_catchall"
    result: str = tmap[key]
    return result


def move_category(move: str) -> str:
    mc = eng().get_raw("move_categories")
    cat: str
    for cat in mc:
        if move in mc[cat]:
            return cat
    return "other"


def is_dialog_branch(brain: BrainResult) -> bool:
    if brain.dialog_only:
        return True
    return brain.move == "dialog" or brain.move == "ask_the_oracle"


def is_dialog_memory(brain: BrainResult, roll_present: bool) -> bool:
    return is_dialog_branch(brain) or not roll_present
