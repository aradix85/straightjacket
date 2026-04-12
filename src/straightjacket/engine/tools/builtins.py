#!/usr/bin/env python3
"""Built-in tools for Brain and Director roles.

Query tools are read-only: they inspect GameState and database but never mutate.
Results are returned as dicts; the engine decides what to do with them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..db.queries import query_clocks, query_memories, query_npcs, query_threads
from ..models import GameState
from ..npc import get_npc_bond
from .registry import register

if TYPE_CHECKING:
    from ..datasworn.moves import Move


@register("director")
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


def query_npc_list(game: GameState, status: str = "active") -> dict:
    """List NPCs filtered by status. Lightweight: names and dispositions only.

    status: filter by status ('active', 'background', 'deceased', 'lore')
    """
    npcs = query_npcs(status=status)
    return {
        "npcs": [
            {"id": n.id, "name": n.name, "disposition": n.disposition, "bond": get_npc_bond(game, n.id)} for n in npcs
        ]
    }


def fate_question(game: GameState, question: str, context_hint: str = "") -> dict:
    """Ask a yes/no question about the fiction. Returns probabilistic answer.

    question: the yes/no question to ask (e.g. 'Is the door locked?')
    context_hint: situational context for odds (e.g. 'hostile NPC', 'safe area')
    """
    from ..mechanics.fate import resolve_fate, resolve_likelihood

    odds = resolve_likelihood(game, context_hint)
    result = resolve_fate(
        game,
        odds=odds,
        chaos_factor=game.world.chaos_factor,
        question=question,
    )
    response: dict = {
        "answer": result.answer,
        "odds": result.odds,
        "chaos_factor": result.chaos_factor,
        "roll": result.roll,
        "random_event_triggered": result.random_event_triggered,
        "question": question,
    }
    if result.random_event is not None:
        ev = result.random_event
        response["random_event"] = {
            "focus": ev.focus,
            "target": ev.target,
            "meaning": f"{ev.meaning_action} / {ev.meaning_subject}",
        }
    return response


def list_tracks(game: GameState, track_type: str = "") -> dict:
    """List active progress tracks. Call before progress moves to see available targets.

    track_type: filter by type ('vow', 'connection', 'combat', 'expedition'), empty for all
    """
    tracks = [t for t in game.progress_tracks if t.status == "active"]
    if track_type:
        tracks = [t for t in tracks if t.track_type == track_type]
    return {
        "tracks": [
            {
                "id": t.id,
                "name": t.name,
                "type": t.track_type,
                "rank": t.rank,
                "filled_boxes": t.filled_boxes,
                "ticks": t.ticks,
                "max_ticks": t.max_ticks,
            }
            for t in tracks
        ]
    }


def available_moves(game: GameState) -> dict:
    """Get the list of moves available in the current game state. Call this to see what moves the player can make."""
    from ..datasworn.moves import get_moves

    if not game.setting_id:
        return {"error": "No setting loaded"}

    ds_moves = get_moves(game.setting_id)
    combat_pos = game.world.combat_position
    in_combat = combat_pos in ("in_control", "bad_spot")
    has_vow = any(t.track_type == "vow" for t in game.progress_tracks)
    has_expedition = any(t.track_type == "expedition" for t in game.progress_tracks)
    has_scene_challenge = any(t.track_type == "scene_challenge" for t in game.progress_tracks)
    has_combat_track = any(t.track_type == "combat" for t in game.progress_tracks)
    has_connection = any(t.track_type == "connection" for t in game.progress_tracks)

    result: list[dict] = []

    for key, move in ds_moves.items():
        if move.roll_type in ("no_roll", "special_track"):
            continue
        if not _is_move_available(
            key,
            move,
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

    # Engine-specific moves (always available)
    result.append({"move": "dialog", "name": "Dialog", "stats": [], "roll_type": "none"})
    result.append({"move": "ask_the_oracle", "name": "Ask the Oracle", "stats": [], "roll_type": "none"})
    result.append(
        {
            "move": "world_shaping",
            "name": "World Shaping",
            "stats": ["wits", "heart", "shadow"],
            "roll_type": "action_roll",
        }
    )

    return {"moves": result, "combat_position": combat_pos}


def _is_move_available(
    key: str,
    move: Move,
    in_combat: bool,
    combat_pos: str,
    has_vow: bool,
    has_expedition: bool,
    has_scene_challenge: bool,
    has_combat_track: bool,
    has_connection: bool,
) -> bool:
    """Determine if a move is available in the current game state."""
    cat = key.split("/")[0]

    # Adventure and recovery moves: always available
    if cat in ("adventure", "recover"):
        return True

    # Combat moves: only in combat, position-dependent
    if cat == "combat":
        if key == "combat/enter_the_fray":
            return not in_combat  # start combat
        if key == "combat/battle":
            return not in_combat  # abstract combat (skip detailed combat)
        if not in_combat:
            return False
        if key == "combat/take_decisive_action":
            return has_combat_track  # need a combat track to roll against
        if combat_pos == "in_control":
            return key in ("combat/strike", "combat/gain_ground")
        if combat_pos == "bad_spot":
            return key in ("combat/clash", "combat/react_under_fire")
        return False

    # Connection moves: always available (NPC targeting handled by Brain)
    if cat == "connection":
        if key == "connection/forge_a_bond":
            return has_connection
        return True

    # Exploration moves: expedition-dependent
    if cat == "exploration":
        if key == "exploration/set_a_course":
            return True  # travel without expedition
        if key == "exploration/undertake_an_expedition":
            return True  # start or continue expedition
        if key in ("exploration/explore_a_waypoint", "exploration/finish_an_expedition"):
            return has_expedition
        return True

    # Quest moves
    if cat == "quest":
        if key == "quest/swear_an_iron_vow":
            return True
        if key == "quest/fulfill_your_vow":
            return has_vow
        return True

    # Scene challenge moves
    if cat == "scene_challenge":
        if key == "scene_challenge/finish_the_scene":
            return has_scene_challenge
        return has_scene_challenge

    # Suffer moves: reactive, not player-initiated
    if cat == "suffer":
        return False

    # Threshold moves: reactive, not player-initiated
    if cat == "threshold":
        return False

    # Delve moves
    if cat == "delve":
        return True  # availability depends on active site (step 15)

    return True
