from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.npc.lifecycle import absorb_npc, new_npc
from straightjacket.engine.gamemaster.npc.matching import find_npc, next_npc_id
from straightjacket.engine.gamemaster.npc.naming import roll_oracle_name
from straightjacket.engine.gamemaster.world import clear_facts, locations_match
from straightjacket.engine.logging_util import log

if TYPE_CHECKING:
    from straightjacket.engine.models import CorrectionOp, GameState


def _skip(op: CorrectionOp, reason: str) -> None:
    log(f"[Correction] {op.op} skipped: {reason}", level="warning")


def _op_npc_edit(game: GameState, op: CorrectionOp) -> None:
    npc = find_npc(game, op.npc_id)
    edit = op.fields
    edits = {} if edit is None else {key: value for key, value in edit.to_dict().items() if value is not None}
    if npc is None or edit is None or not edits:
        _skip(op, "no NPC or no fields named")
        return
    if edit.name is not None and not edit.name.strip():
        log(f"[Correction] npc_edit: {npc.name} keeps its name, the analysis gave an empty one", level="warning")
        del edits["name"]

    old_name = npc.name
    is_rename = "name" in edits and edit.name != old_name
    if is_rename:
        edits.pop("aliases", None)

    for k, v in edits.items():
        setattr(npc, k, v)

    if is_rename:
        if old_name not in npc.aliases:
            npc.aliases.append(old_name)
        new_lower = npc.name.lower()
        npc.aliases = [a for a in npc.aliases if a.lower() != new_lower]

    if edits:
        log(f"[Correction] npc_edit: {npc.name} fields={list(edits.keys())}{' (RENAME)' if is_rename else ''}")


def _op_npc_split(game: GameState, op: CorrectionOp) -> None:
    existing = find_npc(game, op.npc_id)
    if existing is None:
        _skip(op, "no NPC named")
        return
    new_name = op.split_name or roll_oracle_name(game)
    split = new_npc(
        npc_id=next_npc_id(game),
        name=new_name,
        disposition=existing.disposition,
        status=existing.status,
        name_rolled=not op.split_name,
        description=op.split_description or "",
        agenda="",
        instinct="",
        secrets=[],
        aliases=[],
        last_location=existing.last_location,
        introduced=True,
    )
    game.npcs.append(split)
    log(f"[Correction] npc_split: '{existing.name}' → also '{new_name}' ({split.id})")


def _op_npc_merge(game: GameState, op: CorrectionOp) -> None:
    target = find_npc(game, op.npc_id)
    source = find_npc(game, op.merge_source_id)
    if target is None or source is None or target is source:
        _skip(op, "it needs two different NPCs")
        return
    absorb_npc(game, target, source)


def _op_location_edit(game: GameState, op: CorrectionOp) -> None:
    if not op.value:
        _skip(op, "no location named")
        return
    if not locations_match(op.value, game.world.current_location):
        clear_facts(game)
    game.world.current_location = op.value
    log(f"[Correction] location → {game.world.current_location}")


def _op_scene_context(game: GameState, op: CorrectionOp) -> None:
    if not op.value:
        _skip(op, "no scene context given")
        return
    game.world.current_scene_context = op.value
    log("[Correction] scene_context updated")


def _op_time_edit(game: GameState, op: CorrectionOp) -> None:
    if op.value is None or op.value not in gm().enums.time_phases:
        _skip(op, f"{op.value!r} is no time of day")
        return
    game.world.time_of_day = op.value
    log(f"[Correction] time_of_day → {game.world.time_of_day}")


def _op_backstory_append(game: GameState, op: CorrectionOp) -> None:
    if not op.value:
        _skip(op, "no backstory given")
        return
    sep = "\n" if game.backstory else ""
    game.backstory += sep + op.value
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


def apply_correction_ops(game: GameState, ops: list[CorrectionOp]) -> None:
    for op in ops:
        _OP_HANDLERS[op.op](game, op)
