from __future__ import annotations

import dataclasses
import random

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState, RollResult
from .outcome_result import move_outcome_config


def _roll_challenge_dice() -> tuple[int, int]:
    die = eng().dice.challenge_die
    return random.randint(1, die), random.randint(1, die)


def roll_action(stat_name: str, stat_value: int, move: str, momentum: int, adds: int) -> RollResult:
    d1 = random.randint(1, eng().dice.action_die)
    c1, c2 = _roll_challenge_dice()
    return score_action_roll(d1, c1, c2, stat_name, stat_value, move, momentum, adds)


def keep_action_dice(
    earlier: RollResult, stat_name: str, stat_value: int, move: str, momentum: int, adds: int
) -> RollResult:
    d1 = earlier.d1 if earlier.d1 else random.randint(1, eng().dice.action_die)
    return score_action_roll(d1, earlier.c1, earlier.c2, stat_name, stat_value, move, momentum, adds)


def score_action_roll(
    d1: int, c1: int, c2: int, stat_name: str, stat_value: int, move: str, momentum: int, adds: int
) -> RollResult:
    action_die = 0 if momentum < 0 and -momentum == d1 else d1
    score = min(action_die + stat_value + adds, eng().dice.action_score_max)
    if score > c1 and score > c2:
        result = "STRONG_HIT"
    elif score > c1 or score > c2:
        result = "WEAK_HIT"
    else:
        result = "MISS"
    return RollResult(d1, c1, c2, stat_name, stat_value, score, result, move, match=(c1 == c2))


def downgrade_in_position(game: GameState, roll: RollResult) -> RollResult:
    cfg = move_outcome_config(game, roll.move)
    if "downgrade_in" not in cfg or game.world.combat_position != cfg["downgrade_in"]:
        return roll
    if roll.result == "WEAK_HIT":
        lower = "MISS"
    elif roll.result == "STRONG_HIT" and not roll.match:
        lower = "WEAK_HIT"
    else:
        return roll
    log(f"[Roll] {roll.move} in {game.world.combat_position}: {roll.result} counts as {lower}")
    return dataclasses.replace(roll, result=lower)


def roll_progress(track_name: str, filled_boxes: int, move: str) -> RollResult:
    c1, c2 = _roll_challenge_dice()
    return score_progress_roll(c1, c2, track_name, filled_boxes, move)


def keep_progress_dice(earlier: RollResult, track_name: str, filled_boxes: int, move: str) -> RollResult:
    return score_progress_roll(earlier.c1, earlier.c2, track_name, filled_boxes, move)


def score_progress_roll(c1: int, c2: int, track_name: str, filled_boxes: int, move: str) -> RollResult:
    score = min(filled_boxes, eng().progress.boxes)
    if score > c1 and score > c2:
        result = "STRONG_HIT"
    elif score > c1 or score > c2:
        result = "WEAK_HIT"
    else:
        result = "MISS"
    return RollResult(
        d1=0,
        c1=c1,
        c2=c2,
        stat_name=track_name,
        stat_value=filled_boxes,
        action_score=score,
        result=result,
        move=move,
        match=(c1 == c2),
    )


def can_burn_momentum(game: GameState, roll: RollResult) -> str | None:
    mom = game.resources.momentum
    if mom <= 0:
        return None
    if roll.result == "MISS" and mom > roll.c1 and mom > roll.c2:
        return "STRONG_HIT"
    if roll.result == "MISS" and (mom > roll.c1 or mom > roll.c2):
        return "WEAK_HIT"
    if roll.result == "WEAK_HIT" and mom > roll.c1 and mom > roll.c2:
        return "STRONG_HIT"
    return None
