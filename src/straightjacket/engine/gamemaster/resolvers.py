from __future__ import annotations

from ..logging_util import log
from ..models import BrainResult, GameState, NpcData
from .config import gm
from .npc.matching import find_npc
from .questions import answers, outcome_of


def _target_npc(game: GameState, brain: BrainResult) -> NpcData | None:
    if brain.target_npc is None:
        return None
    target = find_npc(game, brain.target_npc)
    if target is None:
        raise ValueError(f"Target NPC {brain.target_npc!r} is not in the game")
    return target


def _score_strain(game: GameState) -> int:
    weights = gm().position_resolver.strain_weights
    return sum(weights[level] for level in answers().strain(game))


def _score_npc_relationship(game: GameState, brain: BrainResult) -> int:
    target = _target_npc(game, brain)
    if target is None:
        return 0
    cfg = gm().position_resolver
    score = cfg.disposition_weights[target.disposition]
    closeness = answers().closeness(game, target.id)
    w = cfg.weights
    if closeness >= cfg.npc_bond_high_min:
        score += w.npc_bond_high
    elif closeness <= cfg.npc_bond_low_max:
        score += w.npc_bond_low
    return score


def _score_chaos_factor(chaos_factor: int) -> int:
    w = gm().position_resolver.weights
    chaos_cfg = gm().chaos_resolver
    if chaos_factor >= chaos_cfg.high_threshold:
        return w.chaos_high
    if chaos_factor <= chaos_cfg.low_threshold:
        return w.chaos_low
    return 0


def _score_recent_streak(recent_outcomes: list[str]) -> int:
    w = gm().position_resolver.weights
    streak = gm().chaos_resolver.recent_result_window
    if len(recent_outcomes) < streak:
        return 0
    tail = recent_outcomes[-streak:]
    if all(o == "failure" for o in tail):
        return w.consecutive_failures
    if all(o == "success" for o in tail):
        return w.consecutive_successes
    return 0


def _score_threat_clocks(game: GameState) -> int:
    w = gm().position_resolver.weights
    chaos_cfg = gm().chaos_resolver
    penalty = 0
    for clock in game.world.clocks:
        if not clock.fired and clock.filled / clock.segments >= chaos_cfg.clock_pressure_threshold:
            penalty += w.threat_clock_critical
    return max(penalty, w.threat_clock_critical * chaos_cfg.clock_pressure_cap_multiplier)


def _score_position_factors(game: GameState, brain: BrainResult, kind: str) -> int:
    recent = game.narrative.session_log[-gm().chaos_resolver.recent_session_window :]
    recent_outcomes = [outcome_of(e.result) for e in recent if e.result]
    advantage = gm().position_resolver.weights.secured_advantage if answers().gained_advantage(game) else 0
    return (
        _score_strain(game)
        + _score_npc_relationship(game, brain)
        + _score_chaos_factor(game.world.chaos_factor)
        + _score_recent_streak(recent_outcomes)
        + _score_threat_clocks(game)
        + advantage
        + gm().position_resolver.move_baselines[kind]
    )


def _map_score_to_position(score: int) -> str:
    cfg = gm().position_resolver
    if score <= cfg.desperate_below:
        return "desperate"
    if score >= cfg.controlled_above:
        return "controlled"
    return "risky"


def _apply_position_overrides(position: str, game: GameState, kind: str) -> str:
    cfg = gm().position_resolver
    conditions: dict[str, bool] = {
        "secured_advantage": answers().gained_advantage(game),
        "any_strain_critical": "critical" in answers().strain(game),
        "crisis_mode": game.crisis_mode,
        "recovery_move": kind == "recovery",
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
    kind = answers().action_kind(brain.move)
    score = _score_position_factors(game, brain, kind)
    position = _map_score_to_position(score)
    position = _apply_position_overrides(position, game, kind)
    log(f"[Position] score={score}, position={position} (move={brain.move}, kind={kind})")
    return position


def resolve_effect(game: GameState, brain: BrainResult, position: str) -> str:
    cfg = gm().effect_resolver
    w = cfg.weights
    score = 0

    score += cfg.position_weights[position]

    target = _target_npc(game, brain)
    if target is not None:
        closeness = answers().closeness(game, target.id)
        if closeness >= cfg.bond_high_min:
            score += w.bond_high
        elif closeness <= cfg.bond_low_max:
            score += w.bond_low

    if answers().gained_advantage(game):
        score += w.secured_advantage

    score += answers().effect_bonus(brain.move)

    if score <= cfg.limited_below:
        effect = "limited"
    elif score >= cfg.great_above:
        effect = "great"
    else:
        effect = "standard"

    log(f"[Effect] score={score}, effect={effect} (position={position}, move={brain.move})")
    return effect
