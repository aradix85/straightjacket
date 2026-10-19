from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import Consequence, GameState
from .config import rules
from .datasworn import load_ruleset


@dataclass(kw_only=True)
class OutcomeResult:
    consequences: list[Consequence] = field(default_factory=list)
    combat_position: str
    progress_marks: int
    clock_fills: int
    legacy_track: str
    legacy_rank_shift: int
    legacy_fixed_ticks: int
    experience_rank_shift: int | None
    boast_slots: int
    chained_move: str
    follow_up_moves: list[str] = field(default_factory=list)


def new_outcome() -> OutcomeResult:
    return OutcomeResult(
        combat_position="",
        progress_marks=0,
        clock_fills=0,
        legacy_track="",
        legacy_rank_shift=0,
        legacy_fixed_ticks=0,
        experience_rank_shift=None,
        boast_slots=0,
        chained_move="",
    )


def move_outcome_config(game: GameState, move_key: str) -> dict[str, Any]:
    overrides = rules().get_raw("move_outcome_overrides")
    ruleset = load_ruleset(game.setting_id).id
    if ruleset in overrides and move_key in overrides[ruleset]:
        cfg: dict[str, Any] = overrides[ruleset][move_key]
        return cfg
    outcomes = rules().get_raw("move_outcomes")
    if move_key not in outcomes:
        raise ValueError(f"No outcome config for {move_key}. Add it to ruleset/move_outcomes.yaml.")
    default: dict[str, Any] = outcomes[move_key]
    return default
