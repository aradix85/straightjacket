from __future__ import annotations

from typing import Any

from ..gamemaster.config import gm
from ..gamemaster.npc.memory import recent_observations
from ..models import GameState, NpcData
from ..ruleset.bond import get_npc_bond
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
