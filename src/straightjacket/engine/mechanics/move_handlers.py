from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..datasworn.moves import get_moves
from ..datasworn.settings import load_package
from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState
from .consequences import roll_action
from .impacts import apply_impact, blocks_recovery, clear_impact
from .move_effects import apply_effects, parse_effects, pay_the_price, strip_datasworn_links
from .outcome_result import OutcomeResult, move_outcome_config
from .roll_sources import best_roll_option
from .suffer import start_dying_clock, suffer
from .tracks import forsake_vow, roll_oracle_answer, start_bound_vow


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

        if track in ("health", "spirit", "supply") and getattr(res, track) <= 0 and params["impact_pair"]:
            free = [impact for impact in params["impact_pair"] if impact not in game.impacts]
            if free:
                apply_impact(game, free[0])
                result.consequences.append(_labels["mark_impact"].format(impact=free[0]))
            else:
                _roll_endure_table(game, params, result)

    return result


def _roll_endure_table(game: GameState, params: dict[str, Any], result: OutcomeResult) -> None:
    row = strip_datasworn_links(load_package(game.setting_id).oracle_table(params["table"]).roll().value)
    log(f"[Suffer] {params['table']}: {row}")
    result.consequences.append(row)
    rule = next((r for r in eng().suffer.table_rows if row.startswith(r.prefix)), None)
    if rule is not None:
        _TABLE_TRIGGERS[rule.trigger](game, params, result)


def _face_the_threshold(game: GameState, params: dict[str, Any], result: OutcomeResult) -> None:
    result.follow_up_moves.append(params["threshold_move"])


def _face_the_threshold_in_a_fight(game: GameState, params: dict[str, Any], result: OutcomeResult) -> None:
    if any(t.track_type == "combat" and t.status == "active" for t in game.progress_tracks):
        _face_the_threshold(game, params, result)


def _start_dying(game: GameState, params: dict[str, Any], result: OutcomeResult) -> None:
    start_dying_clock(game)


def _forsake_the_newest_vow(game: GameState, params: dict[str, Any], result: OutcomeResult) -> None:
    vows = [t for t in game.progress_tracks if t.track_type == "vow" and t.status == "active"]
    if vows:
        forsake_vow(game, vows[-1], result)


_TABLE_TRIGGERS: dict[str, Callable[[GameState, dict[str, Any], OutcomeResult], None]] = {
    "threshold": _face_the_threshold,
    "threshold_in_a_fight": _face_the_threshold_in_a_fight,
    "dying": _start_dying,
    "forsake_vow": _forsake_the_newest_vow,
}


def _die(game: GameState, params: dict[str, Any], result: OutcomeResult) -> None:
    game.end_reason = params["end_reason"]
    result.consequences.append(params["game_over_text"])


def _return_with_a_vow(game: GameState, params: dict[str, Any], result: OutcomeResult) -> None:
    _e = eng()
    labels = _e.ai_text.consequence_labels
    swear_key = _e.suffer.swear_move
    swear_move = get_moves(game.setting_id)[swear_key]
    stat, value = best_roll_option(game, swear_move)
    roll = roll_action(stat, value, swear_key, game.resources.momentum, 0)
    log(f"[Suffer] {swear_key} ({stat}={value}): {roll.action_score} vs [{roll.c1},{roll.c2}] → {roll.result}")
    result.consequences.append(labels["chained_move"].format(move=swear_move.name, result=roll.result))
    sworn = apply_effects(game, parse_effects(move_outcome_config(game, swear_key)[roll.result.lower()]))
    result.consequences.extend(sworn.consequences)
    if roll.result == "MISS" and params["swear_miss_is_death"]:
        _die(game, params, result)
        return
    vow = start_bound_vow(game, params["vow_name"], params["vow_rank"], params["impact"])
    result.consequences.append(
        labels["threshold_vow"].format(vow=vow.name, rank=vow.rank, oracle=roll_oracle_answer(game))
    )
    if apply_impact(game, params["impact"]):
        result.consequences.append(labels["mark_impact"].format(impact=params["impact"]))


def apply_threshold_handler(game: GameState, roll_result: str, params: dict[str, Any]) -> OutcomeResult:
    result = OutcomeResult()
    if roll_result == "WEAK_HIT":
        _return_with_a_vow(game, params, result)
    elif roll_result == "MISS":
        _die(game, params, result)
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

    if roll_result in eng().dice.hit_results:
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
                suffer(game, "supply", abs(weak_cost), result)

    else:
        pay_the_price(game, result)

    return result
