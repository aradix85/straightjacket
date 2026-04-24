"""Complex move handlers: suffer, threshold, recovery.

Handler-based moves use engine.yaml params instead of effect lists. They
encode patterns that don't fit the simple effect vocabulary:

    handler: suffer         Suffer pattern (endure_harm, endure_stress,
                            withstand_damage, companion_takes_a_hit)
    handler: threshold      Threshold pattern (face_death, face_desolation)
    handler: recovery       Recovery with conditional impact clear
                            (heal, hearten, resupply)

Each handler reads a `params` block from engine.yaml move_outcomes and
returns an OutcomeResult. Dispatch happens in move_outcome.resolve_move_outcome.
"""

from __future__ import annotations

from ..engine_loader import eng
from ..models import GameState
from .impacts import apply_impact, blocks_recovery, clear_impact
from .move_effects import OutcomeResult, _roll_pay_the_price


def apply_suffer_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
    """Handle suffer moves: endure_harm, endure_stress, withstand_damage, companion_takes_a_hit.

    Shared pattern:
      strong_hit: choose recovery (+1 track) or momentum (+1). Engine picks track if no impact.
      weak_hit: may exchange momentum -1 for +1 track (if no blocking impact).
      miss: extra -1 track or momentum -2. If track=0: mark impact or roll table.

    Params from engine.yaml:
      track: health / spirit / integrity / companion_health
      recovery: amount to recover on strong/weak hit (default 1)
      miss_extra_track: extra track loss on miss (default -1)
      miss_extra_momentum: alternative momentum loss on miss (default -2)
      impact_pair: [impact_name, worse_impact_name] for miss at zero
      blocking_impact: impact that blocks track recovery on strong/weak hit
    """
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
                # Track already at max, take momentum instead
                res.adjust_momentum(strong_gain, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(_labels["momentum_change"].format(value=f"+{strong_gain}"))
        else:
            # Blocking impact or non-standard track: take momentum
            res.adjust_momentum(strong_gain, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append(_labels["momentum_change"].format(value=f"+{strong_gain}"))

    elif roll_result == "WEAK_HIT":
        if track in ("health", "spirit", "supply") and not has_blocking_impact:
            # Exchange: momentum -weak_exchange for track +recovery
            res.adjust_momentum(-weak_exchange, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            cap = getattr(_e.resources, f"{track}_max")
            gained = res.heal(track, recovery, cap=cap)
            result.consequences.append(_labels["momentum_change"].format(value=f"-{weak_exchange}"))
            if gained:
                result.consequences.append(_labels["track_gain"].format(track=track, n=gained))

    else:  # MISS
        # Extra track damage or momentum loss — engine picks track damage
        if track in ("health", "spirit", "supply"):
            lost = res.damage(track, abs(miss_extra_track))
            if lost:
                result.consequences.append(_labels["track_loss"].format(track=track, n=lost))
            else:
                # Track already at 0, take momentum instead
                res.adjust_momentum(miss_extra_momentum, floor=_e.momentum.floor, ceiling=_e.momentum.max)
                result.consequences.append(_labels["momentum_change"].format(value=str(miss_extra_momentum)))
        else:
            res.adjust_momentum(miss_extra_momentum, floor=_e.momentum.floor, ceiling=_e.momentum.max)
            result.consequences.append(_labels["momentum_change"].format(value=str(miss_extra_momentum)))

        # Track at zero → mark impact. Engine picks first of impact_pair.
        track_value = getattr(res, track, None) if track in ("health", "spirit", "supply") else None
        if track_value is not None and track_value <= 0:
            impact_pair = params["impact_pair"]
            if impact_pair:
                # First impact if not yet active, otherwise the worse one
                chosen = impact_pair[0] if impact_pair[0] not in game.impacts else impact_pair[1]
                if apply_impact(game, chosen):
                    result.consequences.append(_labels["mark_impact"].format(impact=chosen))

    return result


def apply_threshold_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
    """Handle threshold moves: face_death, face_desolation.

    strong_hit: survive, no mechanical effect.
    weak_hit: survive with cost (mark impact or swear a vow). Engine marks impact.
    miss: dead or lost. Game over.

    Params:
      impact: impact to mark on weak hit (doomed, tormented)
      game_over_text: narrative for miss
    """
    result = OutcomeResult()
    _labels = eng().ai_text.consequence_labels

    if roll_result == "STRONG_HIT":
        result.narrative_only = True

    elif roll_result == "WEAK_HIT":
        impact = params["impact"]
        if impact and apply_impact(game, impact):
            result.consequences.append(_labels["mark_impact"].format(impact=impact))
        result.consequences.append(_labels["threshold_vow"])

    else:  # MISS
        game.game_over = True
        result.consequences.append(params["game_over_text"])

    return result


def apply_recovery_handler(game: GameState, roll_result: str, params: dict) -> OutcomeResult:
    """Handle recovery moves with conditional impact clearing: heal, hearten, resupply.

    strong_hit: if blocking impact, clear it and take reduced amount. Otherwise full amount.
    weak_hit: same as strong_hit but with additional cost (momentum or supply loss).
    miss: pay the price.

    Params:
      track: health / spirit / supply
      full_amount: recovery without impact
      impact_amount: recovery when clearing impact
      blocking_impact: impact name (wounded, shaken, unprepared)
      weak_hit_cost_type: momentum / supply
      weak_hit_cost: amount
    """
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

    else:  # MISS
        result.pay_the_price = True
        result.consequences.append(_roll_pay_the_price(game))

    return result
