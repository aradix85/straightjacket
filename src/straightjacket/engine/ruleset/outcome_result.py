from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import Consequence, GameState
from ..setting.packages import load_package
from .config import rules


@dataclass
class OutcomeResult:
    consequences: list[Consequence] = field(default_factory=list)
    combat_position: str = ""
    progress_marks: int = 0
    clock_fills: int = 0
    legacy_track: str = ""
    legacy_rank_shift: int = 0
    legacy_fixed_ticks: int = 0
    experience_rank_shift: int | None = None
    boast_slots: int = 0
    chained_move: str = ""
    follow_up_moves: list[str] = field(default_factory=list)


def move_outcome_config(game: GameState, move_key: str) -> dict[str, Any]:
    overrides = rules().get_raw("move_outcome_overrides")
    for pkg in load_package(game.setting_id).chain():
        if pkg.id in overrides and move_key in overrides[pkg.id]:
            cfg: dict[str, Any] = overrides[pkg.id][move_key]
            return cfg
    outcomes = rules().get_raw("move_outcomes")
    if move_key not in outcomes:
        raise ValueError(f"No outcome config for {move_key}. Add it to ruleset/move_outcomes.yaml.")
    default: dict[str, Any] = outcomes[move_key]
    return default
