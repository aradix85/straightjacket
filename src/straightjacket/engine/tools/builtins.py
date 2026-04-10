#!/usr/bin/env python3
"""Built-in tools for Brain and Director roles.

Query tools are read-only: they inspect GameState and database but never mutate.
Results are returned as dicts; the engine decides what to do with them.
"""

from __future__ import annotations

from ..db.queries import query_clocks, query_memories, query_npcs, query_threads
from ..models import GameState
from .registry import register


@register("brain", "director")
def query_npc(game: GameState, npc_id: str) -> dict:
    """Query an NPC's current state: disposition, bond, recent memories, agenda.

    npc_id: NPC identifier (e.g. 'npc_1')
    """
    from ..npc import find_npc

    npc = find_npc(game, npc_id)
    if not npc:
        return {"error": f"NPC not found: {npc_id}"}

    recent_mems = query_memories(npc_id=npc.id, limit=5)
    return {
        "id": npc.id,
        "name": npc.name,
        "disposition": npc.disposition,
        "bond": npc.bond,
        "bond_max": npc.bond_max,
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
    """List story threads with their types and weights.

    active_only: if true, return only active threads
    """
    threads = query_threads(active=True if active_only else None)
    return {
        "threads": [
            {"id": t.id, "name": t.name, "type": t.thread_type, "weight": t.weight, "active": t.active} for t in threads
        ]
    }


@register("director")
def query_active_clocks(game: GameState, clock_type: str = "", unfired_only: bool = True) -> dict:
    """List clocks filtered by type or status.

    clock_type: filter by type ('threat', 'scheme', 'progress'), empty for all
    unfired_only: if true, return only unfired clocks
    """
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


@register("brain")
def roll_oracle(game: GameState, table_path: str) -> dict:
    """Roll on a Datasworn oracle table. Returns the rolled value and table info.

    table_path: oracle table path (e.g. 'core/action', 'characters/name/given')
    """
    from ..datasworn.loader import load_setting

    if not game.setting_id:
        return {"error": "No setting loaded"}

    try:
        setting = load_setting(game.setting_id)
    except (KeyError, FileNotFoundError) as e:
        return {"error": str(e)}

    table = setting.oracle(table_path)
    if table is None:
        return {"error": f"Oracle table not found: {table_path}", "setting": game.setting_id}

    result = table.roll()
    return {
        "value": result.value,
        "roll": result.roll,
        "table_path": result.table_path,
        "table_title": result.table_title,
        "setting": game.setting_id,
    }


@register("brain")
def query_npc_list(game: GameState, status: str = "active") -> dict:
    """List NPCs filtered by status. Lightweight: names and dispositions only.

    status: filter by status ('active', 'background', 'deceased', 'lore')
    """
    npcs = query_npcs(status=status)
    return {"npcs": [{"id": n.id, "name": n.name, "disposition": n.disposition, "bond": n.bond} for n in npcs]}
