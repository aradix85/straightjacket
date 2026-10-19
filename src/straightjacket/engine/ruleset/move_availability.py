from __future__ import annotations

from ..models import GameState
from .config import rules
from .config_types import (
    ActiveTrackCondition,
    BondedTrackCondition,
    EngineMove,
    MoveAvailabilityCondition,
    MoveAvailabilityRule,
    NoActiveTrackCondition,
)
from .moves import Move, get_moves


def available_moves(game: GameState) -> dict[str, Move | EngineMove]:
    track_states = {(t.track_type, t.status) for t in game.progress_tracks}
    combat_pos = game.world.combat_position
    moves: dict[str, Move | EngineMove] = {
        key: move
        for key, move in get_moves(game.setting_id).items()
        if move.roll_type not in rules().unoffered_roll_types
        and _is_move_available(rules().move_availability[key], track_states, combat_pos)
    }
    moves.update(rules().engine_moves)
    return moves


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
