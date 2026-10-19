from __future__ import annotations

from typing import Any

from ..engine_loader import eng
from ..gamemaster.npc.lifecycle import absorb_npc
from ..gamemaster.npc.matching import find_npc, next_npc_id
from ..gamemaster.npc.naming import roll_oracle_name
from ..gamemaster.world import clear_facts, locations_match
from ..logging_util import log
from ..models import GameState, NpcData


def _skip(op_dict: dict[str, Any], reason: str) -> None:
    log(f"[Correction] {op_dict['op']} skipped: {reason}", level="warning")


def _op_npc_edit(game: GameState, op_dict: dict[str, Any]) -> None:
    npc = find_npc(game, op_dict["npc_id"])
    if npc is None or not op_dict["fields"]:
        _skip(op_dict, "no NPC or no fields named")
        return
    edits = {k: v for k, v in op_dict["fields"].items() if v is not None}
    if "name" in edits and not edits["name"].strip():
        log(f"[Correction] npc_edit: {npc.name} keeps its name, the analysis gave an empty one", level="warning")
        edits.pop("name")

    old_name = npc.name
    is_rename = "name" in edits and edits["name"] != old_name
    if is_rename:
        edits.pop("aliases", None)

    for k, v in edits.items():
        setattr(npc, k, v)

    if is_rename:
        if old_name not in npc.aliases:
            npc.aliases.append(old_name)
        new_lower = edits["name"].lower()
        npc.aliases = [a for a in npc.aliases if a.lower() != new_lower]

    if edits:
        log(f"[Correction] npc_edit: {npc.name} fields={list(edits.keys())}{' (RENAME)' if is_rename else ''}")


def _op_npc_split(game: GameState, op_dict: dict[str, Any]) -> None:
    existing = find_npc(game, op_dict["npc_id"])
    if existing is None:
        _skip(op_dict, "no NPC named")
        return
    new_name = op_dict["split_name"] or roll_oracle_name(game)
    new_npc = NpcData(
        id=next_npc_id(game),
        name=new_name,
        description=op_dict["split_description"] or "",
        disposition=existing.disposition,
        status=existing.status,
        name_rolled=not op_dict["split_name"],
        last_location=existing.last_location,
        introduced=True,
    )
    game.npcs.append(new_npc)
    log(f"[Correction] npc_split: '{existing.name}' → also '{new_name}' ({new_npc.id})")


def _op_npc_merge(game: GameState, op_dict: dict[str, Any]) -> None:
    target = find_npc(game, op_dict["npc_id"])
    source = find_npc(game, op_dict["merge_source_id"])
    if target is None or source is None or target is source:
        _skip(op_dict, "it needs two different NPCs")
        return
    absorb_npc(game, target, source)


def _op_location_edit(game: GameState, op_dict: dict[str, Any]) -> None:
    if not op_dict["value"]:
        _skip(op_dict, "no location named")
        return
    if not locations_match(op_dict["value"], game.world.current_location):
        clear_facts(game)
    game.world.current_location = op_dict["value"]
    log(f"[Correction] location → {game.world.current_location}")


def _op_scene_context(game: GameState, op_dict: dict[str, Any]) -> None:
    if not op_dict["value"]:
        _skip(op_dict, "no scene context given")
        return
    game.world.current_scene_context = op_dict["value"]
    log("[Correction] scene_context updated")


def _op_time_edit(game: GameState, op_dict: dict[str, Any]) -> None:
    if op_dict["value"] not in eng().enums.time_phases:
        _skip(op_dict, f"{op_dict['value']!r} is no time of day")
        return
    game.world.time_of_day = op_dict["value"]
    log(f"[Correction] time_of_day → {game.world.time_of_day}")


def _op_backstory_append(game: GameState, op_dict: dict[str, Any]) -> None:
    if not op_dict["value"]:
        _skip(op_dict, "no backstory given")
        return
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


def apply_correction_ops(game: GameState, ops: list[Any]) -> None:
    for op_dict in ops:
        _OP_HANDLERS[op_dict["op"]](game, op_dict)
