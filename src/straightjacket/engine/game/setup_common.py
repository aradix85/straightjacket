import re

from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import time_phases, update_location
from ..models import ClockData, GameState, MemoryEntry, NpcData
from ..npc import apply_name_sanitization, normalize_npc_dispositions, score_importance


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
    npc_dicts: list[dict],
    *,
    skip_names: set[str] | None = None,
    start_id: int = 0,
) -> int:
    player_lower = game.player_name.lower().strip()
    skip = skip_names or set()
    skip.add(player_lower)

    max_num = start_id
    if max_num == 0:
        for n in game.npcs:
            m = re.match(r"npc_(\d+)", n.id)
            if m:
                max_num = max(max_num, int(m.group(1)))

    for nd in npc_dicts:
        name = nd.get("name", "").lower().strip()
        if not name or name in skip:
            continue
        max_num += 1
        nd["id"] = f"npc_{max_num}"
        nd.setdefault("introduced", False)
        nd.setdefault("last_location", game.world.current_location or "")

        nd["status"] = "active"

        nd.pop("bond", None)
        nd.pop("bond_max", None)
        npc = NpcData.from_dict(nd)
        apply_name_sanitization(npc)
        game.npcs.append(npc)

    game.npcs = [n for n in game.npcs if n.name.lower().strip() != player_lower]
    normalize_npc_dispositions(game.npcs)
    return max_num


def seed_opening_memories(
    game: GameState,
    memory_updates: list[dict],
    label: str = "opening_setup",
) -> None:
    for mu in memory_updates:
        npc_name = mu.get("npc_name", "")
        if not npc_name:
            continue
        target = _find_npc_by_name(game.npcs, npc_name)
        if not target:
            continue
        event = mu.get("event", "")
        if "emotional_weight" not in mu:
            raise KeyError(f"Memory update from {label} missing required 'emotional_weight' for npc='{npc_name}'")
        emotional = mu["emotional_weight"]
        imp, dbg = score_importance(emotional, event, debug=True)
        target.memory.append(
            MemoryEntry(
                scene=game.narrative.scene_count,
                event=event,
                emotional_weight=emotional,
                importance=imp,
                type="observation",
                tone="",
                tone_key="",
                _score_debug=f"{label} | {dbg}",
            )
        )
        target.importance_accumulator = target.importance_accumulator + imp


def apply_world_setup(game: GameState, data: dict, *, clocks_mode: str = "replace") -> None:
    if data.get("clocks"):
        clocks = [ClockData.from_dict(c) for c in data["clocks"]]
        if clocks_mode == "replace":
            game.world.clocks = clocks
        else:
            game.world.clocks.extend(clocks)
        log(f"[Setup] Created {len(clocks)} clocks")

    if data.get("location"):
        update_location(game, data["location"])

    if data.get("scene_context"):
        game.world.current_scene_context = data["scene_context"]

    tod = data.get("time_of_day", "")
    if tod and tod.replace(" ", "_") in time_phases():
        game.world.time_of_day = tod.replace(" ", "_")


def apply_opening_setup(
    game: GameState,
    data: dict,
    *,
    returning_npcs: list[NpcData] | None = None,
    clocks_mode: str = "replace",
    label: str = "OpeningSetup",
) -> None:
    skip_names: set[str] | None = None
    start_id = 0

    if returning_npcs:
        skip_names = {n.name.lower().strip() for n in returning_npcs}
        for n in game.npcs + returning_npcs:
            m = re.match(r"npc_(\d+)", str(n.id))
            if m:
                start_id = max(start_id, int(m.group(1)))

    if data.get("npcs"):
        register_extracted_npcs(
            game,
            data["npcs"],
            skip_names=skip_names,
            start_id=start_id,
        )
        if returning_npcs:
            returning_ids = {r.id for r in returning_npcs}
            new_names = [n.name for n in game.npcs if n.id not in returning_ids]
            log(f"[{label}] Registered {len(new_names)} new NPCs: {new_names}")
        else:
            log(f"[{label}] Registered {len(game.npcs)} NPCs: {[n.name for n in game.npcs]}")

    if data.get("memory_updates"):
        seed_opening_memories(game, data["memory_updates"], label=label.lower().replace("setup", "setup"))

    apply_world_setup(game, data, clocks_mode=clocks_mode)
