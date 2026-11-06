from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.ruleset.bond import get_npc_bond as closeness
from straightjacket.engine.ruleset.bond import merge_connections as merge_npcs
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.threats import add_threat as add_danger
from straightjacket.engine.ruleset.threats import threats_as_dangers as dangers
from straightjacket.engine.ruleset.tracks import complete_track_of_clock as clock_filled

if TYPE_CHECKING:
    from straightjacket.engine.models import GameState

__all__ = [
    "action_kind",
    "action_phrase",
    "add_danger",
    "clock_filled",
    "closeness",
    "dangers",
    "effect_bonus",
    "gained_advantage",
    "gathers_information",
    "merge_npcs",
    "outcome",
    "results_by_outcome",
    "strain",
    "time_taken",
]


def outcome(result: str) -> str:
    outcomes: dict[str, str] = rules().get_raw("result_outcomes")
    return outcomes[result]


def results_by_outcome() -> dict[str, str]:
    outcomes: dict[str, str] = rules().get_raw("result_outcomes")
    return {kind: result for result, kind in outcomes.items()}


def action_kind(move: str) -> str:
    categories = rules().get_raw("move_categories")
    kind: str
    for kind in categories:
        if move in categories[kind]:
            return kind
    return "other"


def action_phrase(move: str) -> str:
    phrases: dict[str, str] = rules().get_raw("action_phrases")
    return phrases[move] if move in phrases else phrases["_catchall"]


def time_taken(move: str) -> str:
    steps: dict[str, str] = rules().get_raw("time_progression_map")
    return steps[move] if move in steps else steps["_catchall"]


def effect_bonus(move: str) -> int:
    bonuses: dict[str, int] = rules().get_raw("effect_bonus_moves")
    return bonuses[move] if move in bonuses else bonuses["other"]


def strain(game: GameState) -> list[str]:
    cfg = rules().strain
    levels: list[str] = []
    for meter in cfg.meters:
        value = game.resources.meters[meter]
        levels.append(next((level for level, below in cfg.below.items() if value < below), cfg.otherwise))
    return levels


def gathers_information(move: str) -> bool:
    return move in rules().information_moves


def gained_advantage(game: GameState) -> bool:
    log = game.narrative.session_log
    return bool(log) and log[-1].move in rules().advantage_moves and log[-1].result in rules().dice.hit_results
