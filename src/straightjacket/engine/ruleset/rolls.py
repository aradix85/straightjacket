from __future__ import annotations

import dataclasses
import random

from ..logging_util import log
from ..models import GameState, RollResult
from .config import rules
from .meters import momentum
from .outcome_result import move_outcome_config


def _roll_challenge_dice() -> tuple[int, int]:
    die = rules().dice.challenge_die
    return random.randint(1, die), random.randint(1, die)


def _result(score: int, c1: int, c2: int) -> str:
    return rules().dice.results_by_dice_beaten[(score > c1) + (score > c2)]


def _rank(result: str) -> int:
    return rules().dice.results_by_dice_beaten.index(result)


def roll_action(stat_name: str, stat_value: int, move: str, held_momentum: int, adds: int) -> RollResult:
    d1 = random.randint(1, rules().dice.action_die)
    c1, c2 = _roll_challenge_dice()
    return score_action_roll(d1, c1, c2, stat_name, stat_value, move, held_momentum, adds)


def keep_action_dice(
    earlier: RollResult, stat_name: str, stat_value: int, move: str, held_momentum: int, adds: int
) -> RollResult:
    d1 = earlier.d1 if earlier.d1 else random.randint(1, rules().dice.action_die)
    return score_action_roll(d1, earlier.c1, earlier.c2, stat_name, stat_value, move, held_momentum, adds)


def score_action_roll(
    d1: int, c1: int, c2: int, stat_name: str, stat_value: int, move: str, held_momentum: int, adds: int
) -> RollResult:
    action_die = 0 if held_momentum < 0 and -held_momentum == d1 else d1
    score = min(action_die + stat_value + adds, rules().dice.action_score_max)
    return RollResult(d1, c1, c2, stat_name, stat_value, score, _result(score, c1, c2), move, match=(c1 == c2))


def downgrade_in_position(game: GameState, roll: RollResult) -> RollResult:
    cfg = move_outcome_config(game, roll.move)
    if "downgrade_in" not in cfg or game.world.combat_position != cfg["downgrade_in"]:
        return roll
    rank = _rank(roll.result)
    if rank == 0 or (rank == len(rules().dice.results_by_dice_beaten) - 1 and roll.match):
        return roll
    lower = rules().dice.results_by_dice_beaten[rank - 1]
    log(f"[Roll] {roll.move} in {game.world.combat_position}: {roll.result} counts as {lower}")
    return dataclasses.replace(roll, result=lower)


def roll_progress(track_name: str, filled_boxes: int, move: str) -> RollResult:
    c1, c2 = _roll_challenge_dice()
    return score_progress_roll(c1, c2, track_name, filled_boxes, move)


def keep_progress_dice(earlier: RollResult, track_name: str, filled_boxes: int, move: str) -> RollResult:
    return score_progress_roll(earlier.c1, earlier.c2, track_name, filled_boxes, move)


def score_progress_roll(c1: int, c2: int, track_name: str, filled_boxes: int, move: str) -> RollResult:
    score = min(filled_boxes, rules().progress.boxes)
    return RollResult(
        d1=0,
        c1=c1,
        c2=c2,
        stat_name=track_name,
        stat_value=filled_boxes,
        action_score=score,
        result=_result(score, c1, c2),
        move=move,
        match=(c1 == c2),
    )


def can_burn_momentum(game: GameState, roll: RollResult) -> str | None:
    burned = _result(momentum(game), roll.c1, roll.c2)
    return burned if _rank(burned) > _rank(roll.result) else None
