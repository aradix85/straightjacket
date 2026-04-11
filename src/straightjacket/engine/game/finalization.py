#!/usr/bin/env python3
"""Shared post-narration finalization: engine memories, metadata, scene context.

Used by turn processing, correction, and momentum burn. Each caller handles
history/log updates differently, but the engine-side state mutations are identical.
"""

from ..ai.metadata import apply_narrator_metadata
from ..ai.narrator import call_narrator_metadata
from ..ai.provider_base import AIProvider
from ..engine_loader import eng
from ..mechanics import (
    generate_engine_memories,
    generate_scene_context,
)
from ..models import BrainResult, EngineConfig, GameState, MemoryEntry, RollResult
from ..npc import find_npc
from ..npc.memory import consolidate_memory


def apply_engine_memories(game: GameState, memories: list[dict]) -> None:
    """Apply engine-generated memories to NPCs.

    Adds observation memories, updates importance accumulators, sets location,
    triggers reflection flags, and consolidates. Shared by all post-narration paths.
    """
    _e = eng()
    for mem in memories:
        npc = find_npc(game, mem["npc_id"])
        if not npc:
            continue
        npc.memory.append(
            MemoryEntry(
                scene=game.narrative.scene_count,
                event=mem["event"],
                emotional_weight=mem["emotional_weight"],
                importance=mem["importance"],
                type="observation",
                about_npc=mem.get("about_npc"),
                _score_debug=mem.get("_score_debug", "engine-generated"),
            )
        )
        npc.importance_accumulator += mem["importance"]
        if game.world.current_location:
            npc.last_location = game.world.current_location
        if npc.importance_accumulator >= _e.npc.reflection_threshold:
            npc.needs_reflection = True
        consolidate_memory(npc)


def apply_post_narration(
    provider: AIProvider,
    game: GameState,
    narration: str,
    brain: BrainResult,
    roll: RollResult | None,
    scene_present_ids: set[str],
    activated_npc_names: list[str],
    config: EngineConfig | None = None,
    consequences: list[str] | None = None,
    world_addition: str = "",
) -> dict:
    """Shared post-narration state mutations: scene context, engine memories, AI metadata.

    Returns the metadata dict from the AI extractor (callers may need it for
    director decisions or new_npcs detection).
    """
    # 1. Engine-generated scene context
    ctx = generate_scene_context(game, brain, roll, activated_npc_names)
    game.world.current_scene_context = ctx

    # 2. Engine-generated memories for activated NPCs
    engine_mems = generate_engine_memories(game, brain, roll, scene_present_ids, consequences=consequences)
    if engine_mems:
        apply_engine_memories(game, engine_mems)

    # 3. AI metadata: NPC detection (new_npcs, renames, details, deaths, lore)
    metadata = call_narrator_metadata(provider, narration, game, config, brain=brain, consequences=consequences or [])
    apply_narrator_metadata(game, metadata, scene_present_ids=scene_present_ids, world_addition=world_addition)

    return metadata
