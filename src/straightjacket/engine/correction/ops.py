"""Atomic state operations for corrections: npc edit/split/merge, location, time, backstory."""

from __future__ import annotations

import re
import uuid

from ..engine_loader import eng
from ..logging_util import log
from ..models import NPC_STATUSES, GameState, NpcData
from ..npc import consolidate_memory, find_npc
from ..npc.lifecycle import sanitize_aliases


def _op_npc_edit(game: GameState, op_dict: dict) -> None:
    """Edit whitelisted fields on an existing NPC. Engine owns alias bookkeeping on rename."""
    npc = find_npc(game, op_dict.get("npc_id", ""))
    if not npc or not op_dict.get("fields"):
        return
    _allowed = set(eng().get_raw("correction")["npc_edit_allowed_fields"])
    edits = {k: v for k, v in op_dict["fields"].items() if k in _allowed and v is not None}

    # Rename detection: pop aliases so the model can't overwrite the engine-maintained list.
    old_name = npc.name
    is_rename = "name" in edits and edits["name"] != old_name
    if is_rename:
        edits.pop("aliases", None)

    if "status" in edits and edits["status"] not in NPC_STATUSES:
        edits.pop("status")

    for k, v in edits.items():
        setattr(npc, k, v)

    if is_rename and old_name:
        if old_name not in npc.aliases:
            npc.aliases.append(old_name)
        new_lower = edits["name"].lower()
        npc.aliases = [a for a in npc.aliases if a.lower() != new_lower]

    if edits.get("status") == "deceased" and npc.description:
        npc.description = re.sub(
            r"\s*\[?(VERSTORBEN|DECEASED|TOT|DEAD)\]?\s*", "", npc.description, flags=re.IGNORECASE
        ).strip()

    if edits:
        log(f"[Correction] npc_edit: {npc.name} fields={list(edits.keys())}{' (RENAME)' if is_rename else ''}")


def _op_npc_split(game: GameState, op_dict: dict) -> None:
    """Split a conflated NPC into two. The new sibling inherits disposition and status —
    the split is a clarification, not a stance change. introduced=True because the split
    is happening *because* both appeared on screen in the same scene.
    """
    existing = find_npc(game, op_dict.get("npc_id", ""))
    if not existing:
        return
    new_name = op_dict.get("split_name") or eng().ai_text.narrator_defaults["split_default_name"]
    new_desc = op_dict.get("split_description") or ""
    new_id = f"npc_{uuid.uuid4().hex[:8]}"
    new_npc = NpcData(
        id=new_id,
        name=new_name,
        description=new_desc,
        disposition=existing.disposition,
        status=existing.status,
        introduced=True,
    )
    game.npcs.append(new_npc)
    log(f"[Correction] npc_split: '{existing.name}' → also '{new_name}' ({new_id})")


def _op_npc_merge(game: GameState, op_dict: dict) -> None:
    """Absorb source NPC into target. Memories and aliases merge; source name becomes alias."""
    target = find_npc(game, op_dict.get("npc_id", ""))
    source = find_npc(game, op_dict.get("merge_source_id", ""))
    if not target or not source or target is source:
        return
    target.memory.extend(source.memory)
    for alias in source.aliases:
        if alias not in target.aliases:
            target.aliases.append(alias)
    if source.name not in target.aliases:
        target.aliases.append(source.name)
    game.npcs = [n for n in game.npcs if n.id != source.id]
    sanitize_aliases(target)
    consolidate_memory(target)
    log(f"[Correction] npc_merge: '{source.name}' absorbed into '{target.name}'")


def _op_location_edit(game: GameState, op_dict: dict) -> None:
    if op_dict.get("value"):
        game.world.current_location = op_dict["value"]
        log(f"[Correction] location → {game.world.current_location}")


def _op_scene_context(game: GameState, op_dict: dict) -> None:
    if op_dict.get("value"):
        game.world.current_scene_context = op_dict["value"]
        log("[Correction] scene_context updated")


def _op_time_edit(game: GameState, op_dict: dict) -> None:
    if op_dict.get("value"):
        game.world.time_of_day = op_dict["value"]
        log(f"[Correction] time_of_day → {game.world.time_of_day}")


def _op_backstory_append(game: GameState, op_dict: dict) -> None:
    if op_dict.get("value"):
        sep = "\n" if game.backstory else ""
        game.backstory += sep + op_dict["value"]
        log("[Correction] backstory appended")


_OP_HANDLERS = {
    "npc_edit": _op_npc_edit,
    "npc_split": _op_npc_split,
    "npc_merge": _op_npc_merge,
    "location_edit": _op_location_edit,
    "scene_context": _op_scene_context,
    "time_edit": _op_time_edit,
    "backstory_append": _op_backstory_append,
}


def _apply_correction_ops(game: GameState, ops: list) -> None:
    """Apply the atomic state_ops returned by call_correction_brain. Dispatches
    each op to its handler; unknown ops are silently ignored (the brain may
    emit op types we don't implement yet).
    """
    for op_dict in ops:
        handler = _OP_HANDLERS.get(op_dict.get("op", ""))
        if handler:
            handler(game, op_dict)
