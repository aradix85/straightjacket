from __future__ import annotations

import itertools
import random
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest import mock

from straightjacket.engine.ruleset import rolls
from straightjacket.engine.ruleset.config import rules

if TYPE_CHECKING:
    from collections.abc import Generator

    from straightjacket.engine.models import RollResult


def check_results(results: list[str]) -> None:
    known = rules().dice.results_by_dice_beaten
    unknown = [r for r in results if r not in known]
    if unknown:
        msg = f"The scenario fixes results the ruleset does not roll: {unknown} (known: {known})"
        raise ValueError(msg)


def _pick(result: str, candidates: list[RollResult], rolled: str) -> RollResult:
    fitting = [r for r in candidates if r.result == result]
    if not fitting:
        msg = f"The scenario fixes {result}, which no dice give for {rolled}"
        raise ValueError(msg)
    without_match = [r for r in fitting if not r.match]
    return random.choice(without_match or fitting)


@contextmanager
def fixed_result(result: str) -> Generator[None]:
    check_results([result])
    score_action = rolls.score_action_roll
    score_progress = rolls.score_progress_roll
    action_faces = range(1, rules().dice.action_die + 1)
    challenge_faces = range(1, rules().dice.challenge_die + 1)

    def action(
        _d1: int, _c1: int, _c2: int, *, stat_name: str, stat_value: int, move: str, held_momentum: int, adds: int
    ) -> RollResult:
        candidates = [
            score_action(
                a, x, y, stat_name=stat_name, stat_value=stat_value, move=move, held_momentum=held_momentum, adds=adds
            )
            for a, x, y in itertools.product(action_faces, challenge_faces, challenge_faces)
        ]
        return _pick(result, candidates, f"{move} with {stat_name} {stat_value}")

    def progress(_c1: int, _c2: int, track_name: str, filled_boxes: int, move: str) -> RollResult:
        candidates = [
            score_progress(x, y, track_name, filled_boxes, move)
            for x, y in itertools.product(challenge_faces, challenge_faces)
        ]
        return _pick(result, candidates, f"{move} on {filled_boxes} boxes")

    with (
        mock.patch.object(rolls, "score_action_roll", action),
        mock.patch.object(rolls, "score_progress_roll", progress),
    ):
        yield
