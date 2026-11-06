from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.config_types import (
    ActiveTrackCondition,
    BondedTrackCondition,
    NoActiveTrackCondition,
)
from straightjacket.engine.ruleset.moves import get_moves

if TYPE_CHECKING:
    from straightjacket.engine.models import GameState
    from straightjacket.engine.ruleset.config_types import (
        MoveAvailabilityCondition,
        MoveAvailabilityRule,
    )
    from straightjacket.engine.ruleset.moves import Move


def available_moves(game: GameState) -> dict[str, Move]:
    track_states = {(t.track_type, t.status) for t in game.progress_tracks}
    combat_pos = game.world.combat_position
    return {
        key: move
        for key, move in get_moves(game.setting_id).items()
        if (move.roll_type not in rules().unoffered_roll_types or key in rules().offered_without_roll)
        and _is_move_available(rules().move_availability[key], track_states, combat_pos)
    }


def _is_move_available(rule: MoveAvailabilityRule, track_states: set[tuple[str, str]], combat_pos: str) -> bool:
    return not rule.never and all(_condition_holds(cond, track_states, combat_pos) for cond in rule.available)


def _condition_holds(cond: MoveAvailabilityCondition, track_states: set[tuple[str, str]], combat_pos: str) -> bool:
    if isinstance(cond, ActiveTrackCondition):
        return (cond.active_track, "active") in track_states
    if isinstance(cond, NoActiveTrackCondition):
        return (cond.no_active_track, "active") not in track_states
    if isinstance(cond, BondedTrackCondition):
        return (cond.bonded_track, "bonded") in track_states
    return combat_pos in cond.combat_pos_in
