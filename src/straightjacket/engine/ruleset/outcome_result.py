from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.config_types import SufferParams
from straightjacket.engine.ruleset.datasworn import load_ruleset

if TYPE_CHECKING:
    from straightjacket.engine.models import Consequence, GameState
    from straightjacket.engine.ruleset.config_types import MoveOutcomeConfig


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


def move_outcome_config(game: GameState, move_key: str) -> MoveOutcomeConfig:
    overrides = rules().move_outcome_overrides
    ruleset = load_ruleset(game.setting_id).id
    if ruleset in overrides and move_key in overrides[ruleset]:
        return overrides[ruleset][move_key]
    outcomes = rules().move_outcomes
    if move_key not in outcomes:
        msg = f"No outcome config for {move_key}. Add it to ruleset/move_outcomes.yaml."
        raise ValueError(msg)
    return outcomes[move_key]


def suffer_params(game: GameState, move_key: str) -> SufferParams:
    params = move_outcome_config(game, move_key).params
    if not isinstance(params, SufferParams):
        msg = f"{move_key} has no suffer handler in ruleset/move_outcomes.yaml."
        raise TypeError(msg)
    return params
