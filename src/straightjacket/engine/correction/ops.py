"""Atomic state operations for corrections: npc edit/split/merge, location, time, backstory."""

from __future__ import annotations

import re
import uuid

from ..engine_loader import eng
from ..logging_util import log
from ..models import NPC_STATUSES, GameState, NpcData
from ..npc import consolidate_memory, find_npc
from ..npc.lifecycle import sanitize_aliases


def _apply_correction_ops(game: GameState, ops: list) -> None:
    """Apply the atomic state_ops returned by call_correction_brain."""
    for op_dict in ops:
        op = op_dict.get("op")

        if op == "npc_edit":
            npc = find_npc(game, op_dict.get("npc_id", ""))
            if npc and op_dict.get("fields"):
                allowed = {"name", "description", "disposition", "agenda", "instinct", "aliases", "status"}
                edits = {k: v for k, v in op_dict["fields"].items() if k in allowed and v is not None}

                # Rename detection: if name is changing, engine owns alias bookkeeping.
                # Pop aliases from edits so the model can't overwrite our list.
                old_name = npc.name
                is_rename = "name" in edits and edits["name"] != old_name
                if is_rename:
                    edits.pop("aliases", None)

                # Status validation
                if "status" in edits and edits["status"] not in NPC_STATUSES:
                    edits.pop("status")

                for k, v in edits.items():
                    setattr(npc, k, v)

                # After rename: move old name to aliases, strip new name from aliases
                if is_rename and old_name:
                    if old_name not in npc.aliases:
                        npc.aliases.append(old_name)
                    new_lower = edits["name"].lower()
                    npc.aliases = [a for a in npc.aliases if a.lower() != new_lower]

                # Clean up death annotation if status set to deceased
                if edits.get("status") == "deceased" and npc.description:
                    npc.description = re.sub(
                        r"\s*\[?(VERSTORBEN|DECEASED|TOT|DEAD)\]?\s*", "", npc.description, flags=re.IGNORECASE
                    ).strip()

                if edits:
                    log(
                        f"[Correction] npc_edit: {npc.name} fields={list(edits.keys())}"
                        f"{' (RENAME)' if is_rename else ''}"
                    )

        elif op == "npc_split":
            existing = find_npc(game, op_dict.get("npc_id", ""))
            if existing:
                new_name = op_dict.get("split_name") or eng().ai_text.narrator_defaults["split_default_name"]
                new_desc = op_dict.get("split_description") or ""
                new_id = f"npc_{uuid.uuid4().hex[:8]}"
                # Split creates a sibling NPC mid-correction. disposition/status default
                # to the existing NPC's values — the split is a clarification that two
                # characters were conflated, so the second one inherits the same stance
                # until further narration distinguishes them. introduced=True because the
                # split is happening *because* both appeared on screen in the same scene.
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

        elif op == "npc_merge":
            target = find_npc(game, op_dict.get("npc_id", ""))
            source = find_npc(game, op_dict.get("merge_source_id", ""))
            if target and source and target is not source:
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

        elif op == "location_edit":
            if op_dict.get("value"):
                game.world.current_location = op_dict["value"]
                log(f"[Correction] location → {game.world.current_location}")

        elif op == "scene_context":
            if op_dict.get("value"):
                game.world.current_scene_context = op_dict["value"]
                log("[Correction] scene_context updated")

        elif op == "time_edit":
            if op_dict.get("value"):
                game.world.time_of_day = op_dict["value"]
                log(f"[Correction] time_of_day → {game.world.time_of_day}")

        elif op == "backstory_append":
            if op_dict.get("value"):
                sep = "\n" if game.backstory else ""
                game.backstory += sep + op_dict["value"]
                log("[Correction] backstory appended")
