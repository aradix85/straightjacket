from __future__ import annotations

from typing import Any

from ..gamemaster.config import gm
from ..gamemaster.npc.memory import recent_observations
from ..models import GameState, NpcData
from ..ruleset.bond import get_npc_bond
from ..ruleset.config import rules
from ..ruleset.config_types import (
    ActiveTrackCondition,
    BondedTrackCondition,
    EngineMove,
    MoveAvailabilityCondition,
    MoveAvailabilityRule,
    NoActiveTrackCondition,
)
from ..ruleset.moves import Move, get_moves
from .registry import register


def _npc_state(game: GameState, npc: NpcData) -> dict[str, Any]:
    return {
        "id": npc.id,
        "name": npc.name,
        "disposition": npc.disposition,
        "bond": get_npc_bond(game, npc.id),
        "status": npc.status,
        "agenda": npc.agenda,
        "instinct": npc.instinct,
        "arc": npc.arc,
        "description": npc.description,
        "last_location": npc.last_location,
        "recent_memories": [
            {"scene": m.scene, "event": m.event, "emotional_weight": m.emotional_weight}
            for m in recent_observations(npc)
        ],
    }


@register
def query_game_state(game: GameState) -> dict[str, Any]:
    return {
        "threads": [
            {"id": t.id, "name": t.name, "type": t.thread_type, "weight": t.weight}
            for t in game.narrative.threads
            if t.active
        ],
        "clocks": [
            {
                "name": c.name,
                "type": c.clock_type,
                "filled": c.filled,
                "segments": c.segments,
                "owner_kind": c.owner_kind,
                "owner_id": c.owner_id,
            }
            for c in game.world.clocks
            if not c.fired
        ],
        "npcs": [_npc_state(game, npc) for npc in game.npcs if npc.status in gm().npc_status_groups.in_play],
    }


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
