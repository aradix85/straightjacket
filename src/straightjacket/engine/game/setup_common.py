#!/usr/bin/env python3
"""Shared setup logic for opening scenes (new game and new chapter)."""

import re

from ..logging_util import log
from ..mechanics import time_phases, update_location
from ..models import ClockData, GameState, MemoryEntry, NpcData
from ..npc import apply_name_sanitization, normalize_npc_dispositions, score_importance


def _find_npc_by_name(npcs: list[NpcData], npc_name: str) -> NpcData | None:
    """Find an NPC by name or partial name match. Used for memory seeding."""
    name_lower = npc_name.lower().strip()
    for n in npcs:
        if n.name.lower().strip() == name_lower:
            return n
        for part in npc_name.split():
            if len(part) >= 4 and part.lower() in n.name.lower():
                return n
    return None


def register_extracted_npcs(
    game: GameState,
    npc_dicts: list[dict],
    *,
    skip_names: set[str] | None = None,
    start_id: int = 0,
    label: str = "OpeningSetup",
) -> int:
    """Register NPCs from extraction data into game state.

    Args:
        game: Game state to modify.
        npc_dicts: Raw NPC dicts from the extractor.
        skip_names: Lowercased names to skip (player character, returning NPCs).
        start_id: Starting NPC ID counter. 0 means auto-detect from game.npcs.
        label: Log label for context.

    Returns:
        The highest NPC ID number assigned (for further ID generation).
    """
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
        # Remove bond/bond_max from AI output — bond lives in connection tracks
        nd.pop("bond", None)
        nd.pop("bond_max", None)
        npc = NpcData.from_dict(nd)
        apply_name_sanitization(npc)
        game.npcs.append(npc)

    # Remove any player character that slipped through
    game.npcs = [n for n in game.npcs if n.name.lower().strip() != player_lower]
    normalize_npc_dispositions(game.npcs)
    return max_num


def seed_opening_memories(
    game: GameState,
    memory_updates: list[dict],
    label: str = "opening_setup",
) -> None:
    """Apply initial memory entries from extraction data."""
    for mu in memory_updates:
        npc_name = mu.get("npc_name", "")
        if not npc_name:
            continue
        target = _find_npc_by_name(game.npcs, npc_name)
        if not target:
            continue
        event = mu.get("event", "")
        emotional = mu.get("emotional_weight", "neutral")
        imp, dbg = score_importance(emotional, event, debug=True)
        target.memory.append(
            MemoryEntry(
                scene=game.narrative.scene_count,
                event=event,
                emotional_weight=emotional,
                importance=imp,
                type="observation",
                _score_debug=f"{label} | {dbg}",
            )
        )
        target.importance_accumulator = target.importance_accumulator + imp


def apply_world_setup(game: GameState, data: dict, *, clocks_mode: str = "replace") -> None:
    """Apply clocks, location, scene_context, time_of_day from extraction data.

    clocks_mode: "replace" (new game) or "extend" (new chapter).
    """
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
