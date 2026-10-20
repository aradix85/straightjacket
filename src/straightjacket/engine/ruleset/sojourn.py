from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..logging_util import log
from ..models import GameState, consequence
from .config import rules
from .impacts import clear_impact, impact_consequence
from .meters import adjust_momentum, condition_meters, gain, is_momentum, max_momentum, momentum
from .move_effects import complication_replaces_price, pay_the_price, roll_story_complication
from .outcome_result import OutcomeResult, new_outcome
from .rolls import roll_action


@dataclass(frozen=True)
class _Pick:
    action: str
    meter: str
    condition: str
    gain: int


def apply_sojourn_handler(
    game: GameState, move_key: str, roll_result: str, params: dict[str, Any], match: bool, aided_by: str | None
) -> OutcomeResult:
    result = new_outcome()
    if roll_result not in rules().dice.hit_results:
        if complication_replaces_price(game, match):
            roll_story_complication(game, result)
        else:
            pay_the_price(game, result)
        return result
    count = params["picks"][roll_result.lower()] + (params["bond_picks"] if aided_by else 0)
    candidates = _candidates(game, params)
    if not candidates:
        return result
    first, *rest = candidates
    extra = _focus(game, move_key, params, first, aided_by, result)
    if extra is None:
        rest = [pick for pick in rest if pick.condition or not first.condition or pick.meter != first.meter]
    else:
        _take(game, first, extra, result)
    for pick in rest[: count - 1]:
        _take(game, pick, 0, result)
    return result


def _candidates(game: GameState, params: dict[str, Any]) -> list[_Pick]:
    clears: dict[str, dict[str, str]] = params["clear_a_condition"]
    picks = [
        _Pick(action=clears[key]["action"], meter=clears[key]["meter"], condition=key, gain=params["clear_gain"])
        for key in game.impacts
        if key in clears
    ]
    meters = game.resources.meters
    limits = condition_meters(game.setting_id)
    recover: dict[str, str] = params["recover"]
    lowest = sorted(
        (m for m in recover if not is_momentum(m) and meters[m] < limits[m].max),
        key=lambda m: meters[m],
    )
    if momentum(game) < max_momentum(game):
        lowest += [m for m in recover if is_momentum(m)]
    picks += [_Pick(action=recover[m], meter=m, condition="", gain=params["recover_gain"]) for m in lowest]
    return picks


def _focus(
    game: GameState,
    move_key: str,
    params: dict[str, Any],
    pick: _Pick,
    aided_by: str | None,
    result: OutcomeResult,
) -> int | None:
    stat = params["focus_stat"]
    adds = params["focus_bond_add"] if aided_by else 0
    roll = roll_action(stat, game.stats[stat], move_key, momentum(game), adds)
    log(f"[Sojourn] focus on {pick.action}: {roll.action_score} vs [{roll.c1},{roll.c2}] → {roll.result}")
    result.consequences.append(consequence("focus_roll", action=pick.action, result=roll.result))
    if roll.result not in rules().dice.hit_results:
        result.consequences.append(consequence("focus_lost", action=pick.action))
        return None
    extra: int = params["focus_gain"][roll.result.lower()]
    return extra


def _take(game: GameState, pick: _Pick, extra: int, result: OutcomeResult) -> None:
    if pick.condition:
        clear_impact(game, pick.condition)
        result.consequences.append(impact_consequence(game, "clear_impact", pick.condition))
    amount = pick.gain + extra
    if is_momentum(pick.meter):
        before = momentum(game)
        adjust_momentum(game, amount)
        if momentum(game) != before:
            result.consequences.append(consequence("momentum_change", n=momentum(game) - before))
        return
    gained = gain(game, pick.meter, amount)
    if gained:
        result.consequences.append(consequence("track_gain", track=pick.meter, n=gained))
