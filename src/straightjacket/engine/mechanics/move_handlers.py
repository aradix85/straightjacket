from __future__ import annotations

from ..engine_loader import eng
from ..models import GameState
from .impacts import apply_impact, blocks_recovery, clear_impact
from .move_effects import OutcomeResult, _roll_pay_the_price


def apply_suffer_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
    result = OutcomeResult()
    _e = eng()
    _labels = _e.ai_text.consequence_labels
    res = game.resources
    track = params["track"]
    recovery = params["recovery"]
    miss_extra_track = params["miss_extra_track"]
    miss_extra_momentum = params["miss_extra_momentum"]

    has_blocking_impact = bool(blocks_recovery(game, track))
    strong_gain = _e.momentum.suffer_recovery.strong_hit_gain
    weak_exchange = _e.momentum.suffer_recovery.weak_hit_exchange_cost

    if roll_result == "STRONG_HIT":
        if track in ("health", "spirit", "supply") and not has_blocking_impact:
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, recovery, cap=cap)
            if gained:
                result.consequences.append(_labels["track_gain"].format(track=track, n=gained))
            else:
                res.adjust_momentum(strong_gain, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(_labels["momentum_change"].format(value=f"+{strong_gain}"))
        else:
            res.adjust_momentum(strong_gain, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append(_labels["momentum_change"].format(value=f"+{strong_gain}"))

    elif roll_result == "WEAK_HIT":
        if track in ("health", "spirit", "supply") and not has_blocking_impact:
            res.adjust_momentum(-weak_exchange, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, recovery, cap=cap)
            result.consequences.append(_labels["momentum_change"].format(value=f"-{weak_exchange}"))
            if gained:
                result.consequences.append(_labels["track_gain"].format(track=track, n=gained))

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


def apply_threshold_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
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


def apply_recovery_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
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
