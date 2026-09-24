from __future__ import annotations

from typing import Any
from ..engine_loader import eng
from ..models import GameState
from .impacts import apply_impact, blocks_recovery, clear_impact
from .move_effects import OutcomeResult, _roll_pay_the_price


def _can_recover(game: GameState, params: dict[str, Any], blocked: bool) -> bool:
    track = params["track"]
    if track not in ("health", "spirit", "supply") or blocked:
        return False
    value = int(getattr(game.resources, track))
    if value <= 0 and not params["recover_from_zero"]:
        return False
    return value < int(getattr(eng().resources, f"{track}_max"))


def _recover(game: GameState, params: dict[str, Any], cost: int, result: OutcomeResult) -> None:
    _e = eng()
    labels = _e.ai_text.consequence_labels
    track = params["track"]
    if cost:
        game.resources.adjust_momentum(-cost, floor=_e.momentum.floor, ceiling=_e.momentum.max)
        result.consequences.append(labels["momentum_change"].format(value=f"-{cost}"))
    gained = game.resources.heal(track, params["recovery"], cap=getattr(_e.resources, f"{track}_max"))
    result.consequences.append(labels["track_gain"].format(track=track, n=gained))


def _suffer_strong_hit(game: GameState, params: dict[str, Any], blocked: bool, result: OutcomeResult) -> None:
    if _can_recover(game, params, blocked):
        _recover(game, params, params["strong_hit_exchange_cost"], result)
        return
    _e = eng()
    gain = _e.momentum.suffer_recovery.strong_hit_gain
    game.resources.adjust_momentum(gain, floor=_e.momentum.floor, ceiling=_e.momentum.max)
    result.consequences.append(_e.ai_text.consequence_labels["momentum_change"].format(value=f"+{gain}"))


def _suffer_weak_hit(game: GameState, params: dict[str, Any], blocked: bool, result: OutcomeResult) -> None:
    if _can_recover(game, params, blocked):
        _recover(game, params, eng().momentum.suffer_recovery.weak_hit_exchange_cost, result)


def apply_suffer_handler(game: GameState, roll_result: str, params: dict[str, Any]) -> OutcomeResult:
    result = OutcomeResult()
    _e = eng()
    _labels = _e.ai_text.consequence_labels
    res = game.resources
    track = params["track"]
    miss_extra_track = params["miss_extra_track"]
    miss_extra_momentum = params["miss_extra_momentum"]

    has_blocking_impact = bool(blocks_recovery(game, track))

    if roll_result == "STRONG_HIT":
        _suffer_strong_hit(game, params, has_blocking_impact, result)
    elif roll_result == "WEAK_HIT" and params["weak_hit_exchange"]:
        _suffer_weak_hit(game, params, has_blocking_impact, result)
    elif roll_result == "WEAK_HIT":
        pass
    else:
        if track in ("health", "spirit", "supply"):
            lost = res.damage(track, abs(miss_extra_track))
            if lost:
                result.consequences.append(_labels["track_loss"].format(track=track, n=lost))
            else:
                res.adjust_momentum(miss_extra_momentum, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(_labels["momentum_change"].format(value=str(miss_extra_momentum)))
        else:
            res.adjust_momentum(miss_extra_momentum, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append(_labels["momentum_change"].format(value=str(miss_extra_momentum)))

        track_value = getattr(res, track, None) if track in ("health", "spirit", "supply") else None
        if track_value is not None and track_value <= 0:
            impact_pair = params["impact_pair"]
            if impact_pair:
                chosen = impact_pair[0] if impact_pair[0] not in game.impacts else impact_pair[1]
                if apply_impact(game, chosen):
                    result.consequences.append(_labels["mark_impact"].format(impact=chosen))

    return result


def apply_threshold_handler(game: GameState, roll_result: str, params: dict[str, Any]) -> OutcomeResult:
    result = OutcomeResult()
    _labels = eng().ai_text.consequence_labels

    if roll_result == "STRONG_HIT":
        result.narrative_only = True

    elif roll_result == "WEAK_HIT":
        impact = params["impact"]
        if impact and apply_impact(game, impact):
            result.consequences.append(_labels["mark_impact"].format(impact=impact))
        result.consequences.append(_labels["threshold_vow"])

    else:
        game.game_over = True
        result.consequences.append(params["game_over_text"])

    return result


def apply_recovery_handler(game: GameState, roll_result: str, params: dict[str, Any]) -> OutcomeResult:
    result = OutcomeResult()
    _e = eng()
    _labels = _e.ai_text.consequence_labels
    res = game.resources
    track = params["track"]
    full_amount = params["full_amount"]
    impact_amount = params["impact_amount"]
    blocking_impact = params["blocking_impact"]
    weak_cost_type = params["weak_hit_cost_type"]
    weak_cost = params["weak_hit_cost"]

    has_impact = bool(blocking_impact) and blocking_impact in game.impacts

    if roll_result in ("STRONG_HIT", "WEAK_HIT"):
        amount = impact_amount if has_impact else full_amount
        if has_impact and clear_impact(game, blocking_impact):
            result.consequences.append(_labels["clear_impact"].format(impact=blocking_impact))

        if track in ("health", "spirit", "supply"):
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, amount, cap=cap)
            if gained:
                result.consequences.append(_labels["track_gain"].format(track=track, n=gained))

        if roll_result == "WEAK_HIT":
            if weak_cost_type == "momentum":
                res.adjust_momentum(weak_cost, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(_labels["momentum_change"].format(value=str(weak_cost)))
            elif weak_cost_type == "supply":
                lost = res.damage("supply", abs(weak_cost))
                if lost:
                    result.consequences.append(_labels["track_loss"].format(track="supply", n=lost))

    else:
        result.pay_the_price = True
        result.consequences.append(_roll_pay_the_price(game))

    return result
