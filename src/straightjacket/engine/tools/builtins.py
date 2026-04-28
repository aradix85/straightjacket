from __future__ import annotations

from ..datasworn.moves import get_moves
from ..db.queries import query_clocks, query_memories, query_threads
from ..engine_config import CombatPosCondition, FlagCondition, NotFlagCondition
from ..engine_loader import eng
from ..models import GameState
from ..npc import find_npc, get_npc_bond
from .registry import register


@register("director")
def query_npc(game: GameState, npc_id: str) -> dict:
    npc = find_npc(game, npc_id)
    if not npc:
        return {"error": f"NPC not found: {npc_id}"}

    recent_mems = query_memories(npc_id=npc.id, limit=eng().npc.reflection_observation_window)
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
            {"scene": m.scene, "event": m.event, "emotional_weight": m.emotional_weight, "type": m.type}
            for m in recent_mems
        ],
    }


@register("director")
def query_active_threads(game: GameState, active_only: bool = True) -> dict:
    threads = query_threads(active=True if active_only else None)
    return {
        "threads": [
            {"id": t.id, "name": t.name, "type": t.thread_type, "weight": t.weight, "active": t.active} for t in threads
        ]
    }


@register("director")
def query_active_clocks(game: GameState, clock_type: str = "", unfired_only: bool = True) -> dict:
    clocks = query_clocks(
        clock_type=clock_type if clock_type else None,
        fired=False if unfired_only else None,
    )
    return {
        "clocks": [
            {
                "name": c.name,
                "type": c.clock_type,
                "filled": c.filled,
                "segments": c.segments,
                "owner": c.owner,
                "fired": c.fired,
            }
            for c in clocks
        ]
    }


def available_moves(game: GameState) -> dict:
    if not game.setting_id:
        raise ValueError("No setting loaded")

    ds_moves = get_moves(game.setting_id)
    combat_pos = game.world.combat_position
    in_combat = combat_pos in ("in_control", "bad_spot")
    active_tracks = [t for t in game.progress_tracks if t.status == "active"]
    has_vow = any(t.track_type == "vow" for t in active_tracks)
    has_expedition = any(t.track_type == "expedition" for t in active_tracks)
    has_scene_challenge = any(t.track_type == "scene_challenge" for t in active_tracks)
    has_combat_track = any(t.track_type == "combat" for t in active_tracks)
    has_connection = any(t.track_type == "connection" for t in active_tracks)

    result: list[dict] = []

    for key, move in ds_moves.items():
        if move.roll_type in ("no_roll", "special_track"):
            continue
        if not _is_move_available(
            key,
            in_combat,
            combat_pos,
            has_vow,
            has_expedition,
            has_scene_challenge,
            has_combat_track,
            has_connection,
        ):
            continue
        stats = move.valid_stats
        result.append(
            {
                "move": key,
                "name": move.name,
                "stats": stats if stats else [],
                "roll_type": move.roll_type,
            }
        )

    for key, em in eng().engine_moves.items():
        result.append(
            {
                "move": key,
                "name": em.name,
                "stats": list(em.stats),
                "roll_type": em.roll_type,
            }
        )

    return {"moves": result, "combat_position": combat_pos}


def _is_move_available(
    key: str,
    in_combat: bool,
    combat_pos: str,
    has_vow: bool,
    has_expedition: bool,
    has_scene_challenge: bool,
    has_combat_track: bool,
    has_connection: bool,
) -> bool:
    rule = eng().move_availability[key]
    if rule.never:
        return False

    flags = {
        "in_combat": in_combat,
        "has_vow": has_vow,
        "has_expedition": has_expedition,
        "has_scene_challenge": has_scene_challenge,
        "has_combat_track": has_combat_track,
        "has_connection": has_connection,
    }
    for cond in rule.available:
        if isinstance(cond, FlagCondition) and not flags[cond.flag]:
            return False
        if isinstance(cond, NotFlagCondition) and flags[cond.not_flag]:
            return False
        if isinstance(cond, CombatPosCondition) and combat_pos not in cond.combat_pos_in:
            return False
    return True
