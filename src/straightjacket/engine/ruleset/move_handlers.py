from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..gamemaster.moves import roll_oracle_answer
from ..logging_util import log
from ..models import GameState, consequence
from .config import rules
from .impacts import apply_impact, blocks_recovery, clear_impact, impact_consequence
from .meters import adjust_momentum, condition_meters, gain, is_condition_meter, is_momentum, lose, momentum
from .move_effects import (
    apply_effects,
    complication_replaces_price,
    parse_effects,
    pay_the_price,
    roll_oracle_result,
    roll_story_complication,
)
from .moves import get_moves
from .outcome_result import OutcomeResult, move_outcome_config, new_outcome
from .roll_sources import best_roll_option
from .rolls import roll_action
from .suffer import start_dying_clock, suffer
from .tracks import forsake_vow, start_bound_vow


def _can_recover(game: GameState, params: dict[str, Any], blocked: bool) -> bool:
    track = params["track"]
    if not is_condition_meter(game, track) or blocked:
        return False
    value = game.resources.meters[track]
    if value <= 0 and not params["recover_from_zero"]:
        return False
    return value < condition_meters(game.setting_id)[track].max


def _recover(game: GameState, params: dict[str, Any], cost: int, result: OutcomeResult) -> None:
    track = params["track"]
    if cost:
        adjust_momentum(game, -cost)
        result.consequences.append(consequence("momentum_change", n=-cost))
    gained = gain(game, track, params["recovery"])
    result.consequences.append(consequence("track_gain", track=track, n=gained))


def _suffer_strong_hit(game: GameState, params: dict[str, Any], blocked: bool, result: OutcomeResult) -> None:
    if _can_recover(game, params, blocked):
        _recover(game, params, params["strong_hit_exchange_cost"], result)
        return
    recovered = rules().momentum.suffer_recovery.strong_hit_gain
    adjust_momentum(game, recovered)
    result.consequences.append(consequence("momentum_change", n=recovered))


def _suffer_weak_hit(game: GameState, params: dict[str, Any], blocked: bool, result: OutcomeResult) -> None:
    if _can_recover(game, params, blocked):
        _recover(game, params, rules().momentum.suffer_recovery.weak_hit_exchange_cost, result)


def apply_suffer_handler(
    game: GameState, move_key: str, roll_result: str, params: dict[str, Any], match: bool
) -> OutcomeResult:
    result = new_outcome()
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
        condition_meter = is_condition_meter(game, track)
        lost = lose(game, track, abs(miss_extra_track)) if condition_meter else 0
        if lost:
            result.consequences.append(consequence("track_loss", track=track, n=lost))
        else:
            adjust_momentum(game, miss_extra_momentum)
            result.consequences.append(consequence("momentum_change", n=miss_extra_momentum))

        if condition_meter and game.resources.meters[track] <= 0 and params["impact_pair"]:
            free = [impact for impact in params["impact_pair"] if impact not in game.impacts]
            if free:
                apply_impact(game, free[0])
                result.consequences.append(impact_consequence(game, "mark_impact", free[0]))
            else:
                _roll_endure_table(game, move_key, params, result)

    return result


def _roll_endure_table(game: GameState, move_key: str, params: dict[str, Any], result: OutcomeResult) -> None:
    rows, told = roll_oracle_result(get_moves(game.setting_id)[move_key].tables[params["table"]])
    log(f"[Suffer] {told.label}")
    result.consequences.append(told)
    rule = next((r for r in rules().suffer.table_rows for row in rows if row.startswith(r.prefix)), None)
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
    result.consequences.append(consequence("told", text=params["game_over_text"]))


def _return_with_a_vow(game: GameState, params: dict[str, Any], result: OutcomeResult) -> None:
    swear_key = rules().suffer.swear_move
    swear_move = get_moves(game.setting_id)[swear_key]
    stat, value = best_roll_option(game, swear_move)
    roll = roll_action(stat, value, swear_key, momentum(game), 0)
    log(f"[Suffer] {swear_key} ({stat}={value}): {roll.action_score} vs [{roll.c1},{roll.c2}] → {roll.result}")
    result.consequences.append(consequence("chained_move", move=swear_move.name, result=roll.result))
    sworn = apply_effects(game, parse_effects(move_outcome_config(game, swear_key)[roll.result.lower()]))
    result.consequences.extend(sworn.consequences)
    if roll.result == "MISS" and params["swear_miss_is_death"]:
        _die(game, params, result)
        return
    vow = start_bound_vow(game, params["vow_name"], params["vow_rank"], params["impact"])
    result.consequences.append(
        consequence("threshold_vow", vow=vow.name, rank=vow.rank, oracle=roll_oracle_answer(game))
    )
    if apply_impact(game, params["impact"]):
        result.consequences.append(impact_consequence(game, "mark_impact", params["impact"]))


def apply_threshold_handler(
    game: GameState, move_key: str, roll_result: str, params: dict[str, Any], match: bool
) -> OutcomeResult:
    result = new_outcome()
    if roll_result == "WEAK_HIT":
        _return_with_a_vow(game, params, result)
    elif roll_result == "MISS":
        _die(game, params, result)
    return result


def apply_recovery_handler(
    game: GameState, move_key: str, roll_result: str, params: dict[str, Any], match: bool
) -> OutcomeResult:
    result = new_outcome()
    track = params["track"]
    full_amount = params["full_amount"]
    impact_amount = params["impact_amount"]
    weak_cost_type = params["weak_hit_cost_type"]
    weak_cost = params["weak_hit_cost"]

    blocking_impact = blocks_recovery(game, track)
    has_impact = bool(blocking_impact)

    if roll_result in rules().dice.hit_results:
        amount = impact_amount if has_impact else full_amount
        if has_impact and clear_impact(game, blocking_impact):
            result.consequences.append(impact_consequence(game, "clear_impact", blocking_impact))

        if is_condition_meter(game, track):
            gained = gain(game, track, amount)
            if gained:
                result.consequences.append(consequence("track_gain", track=track, n=gained))

        if roll_result == "WEAK_HIT":
            if is_momentum(weak_cost_type):
                adjust_momentum(game, weak_cost)
                result.consequences.append(consequence("momentum_change", n=weak_cost))
            else:
                suffer(game, weak_cost_type, abs(weak_cost), result)

    elif complication_replaces_price(game, match):
        roll_story_complication(game, result)
    else:
        pay_the_price(game, result)

    return result
