"""Built-in tools for Brain and Director roles.

Query tools are read-only: they inspect GameState and database but never mutate.
Results are returned as dicts; the engine decides what to do with them.
"""

from __future__ import annotations

from ..datasworn.moves import get_moves
from ..datasworn.settings import load_package
from ..db.queries import query_clocks, query_memories, query_npcs, query_threads
from ..engine_config import CombatPosCondition, FlagCondition, NotFlagCondition
from ..engine_loader import eng
from ..mechanics.fate import resolve_fate, resolve_likelihood
from ..models import GameState
from ..npc import find_npc, get_npc_bond
from .registry import register


@register("director")
def query_npc(game: GameState, npc_id: str) -> dict:
    """Query an NPC's current state: disposition, bond, recent memories, agenda.

    npc_id: NPC identifier (e.g. 'npc_1')
    """

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

    Errors are returned as structured dicts so the caller (AI tool invoker) can
    handle them in-band rather than via exception propagation — this is the
    tool contract for all built-ins.
    """

    if not game.setting_id:
        return {"error": "No setting loaded"}

    try:
        pkg = load_package(game.setting_id)
    except (KeyError, FileNotFoundError) as e:
        return {"error": str(e)}

    table = pkg.data.oracle(table_path)
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

    if not game.setting_id:
        return {"error": "No setting loaded"}

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

    # Engine-specific moves (always available) — defined in engine.yaml
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
    """Determine if a move is available in the current game state.

    Yaml-authoritative: reads engine.yaml `move_availability`. Unknown move
    keys raise KeyError — every rollable move across supported settings must
    be listed there.
    """

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
