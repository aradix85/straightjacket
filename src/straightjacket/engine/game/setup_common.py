from collections.abc import Sequence
from typing import Any

from ..engine_loader import eng
from ..gamemaster.npc.lifecycle import new_npc
from ..gamemaster.npc.matching import apply_name_sanitization, fuzzy_match_existing_npc, next_npc_id
from ..gamemaster.npc.memory import score_importance
from ..gamemaster.world import update_location
from ..logging_util import log
from ..models import GameState, MemoryEntry, NpcData


def _find_npc_by_name(npcs: list[NpcData], npc_name: str) -> NpcData | None:
    name_lower = npc_name.lower().strip()
    min_part = eng().setup_common.part_name_min_length
    for n in npcs:
        if n.name.lower().strip() == name_lower:
            return n
        for part in npc_name.split():
            if len(part) >= min_part and part.lower() in n.name.lower():
                return n
    return None


def register_extracted_npcs(
    game: GameState,
    npc_dicts: list[dict[str, Any]],
    *,
    skip_names: set[str],
    reserved_ids: set[str],
) -> None:
    player_lower = game.player_name.lower().strip()
    skip = set(skip_names)
    skip.add(player_lower)

    for nd in npc_dicts:
        name = nd["name"].lower().strip()
        if not name or name in skip:
            continue
        known, _match_type = fuzzy_match_existing_npc(game, nd["name"])
        if known is not None:
            log(f"[NPC] Extracted '{nd['name']}' is the known '{known.name}', not a new NPC")
            continue
        npc = new_npc(
            id=next_npc_id(game, reserved_ids),
            name=nd["name"],
            disposition=nd["disposition"],
            status="active",
            name_rolled=False,
            description=nd["description"],
            agenda=nd["agenda"],
            instinct=nd["instinct"],
            secrets=list(nd["secrets"]),
            aliases=[],
            last_location=game.world.current_location,
            introduced=False,
        )
        apply_name_sanitization(npc)
        game.npcs.append(npc)

    game.npcs = [n for n in game.npcs if n.name.lower().strip() != player_lower]


def seed_opening_memories(game: GameState, memory_updates: list[dict[str, Any]]) -> None:
    for mu in memory_updates:
        target = _find_npc_by_name(game.npcs, mu["npc_name"])
        if not target:
            continue
        event = mu["event"]
        emotional = mu["emotional_weight"]
        imp = score_importance(emotional, event)
        target.memory.append(
            MemoryEntry(
                scene=game.narrative.scene_count,
                event=event,
                emotional_weight=emotional,
                importance=imp,
                type="observation",
                tone="",
                tone_key="",
                about_npc=None,
            )
        )
        target.importance_accumulator = target.importance_accumulator + imp


def apply_opening_setup(
    game: GameState,
    data: dict[str, Any],
    *,
    returning_npcs: Sequence[NpcData] = (),
    label: str,
) -> None:
    skip_names: set[str] = {n.name.lower().strip() for n in returning_npcs}

    if data["npcs"]:
        register_extracted_npcs(
            game,
            data["npcs"],
            skip_names=skip_names,
            reserved_ids={n.id for n in returning_npcs},
        )
        if returning_npcs:
            returning_ids = {r.id for r in returning_npcs}
            new_names = [n.name for n in game.npcs if n.id not in returning_ids]
            log(f"[{label}] Registered {len(new_names)} new NPCs: {new_names}")
        else:
            log(f"[{label}] Registered {len(game.npcs)} NPCs: {[n.name for n in game.npcs]}")

    seed_opening_memories(game, data["memory_updates"])

    if data["location"]:
        update_location(game, data["location"])

    if data["scene_context"]:
        game.world.current_scene_context = data["scene_context"]
