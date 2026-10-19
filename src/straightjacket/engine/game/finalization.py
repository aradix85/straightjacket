from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..ai.metadata import apply_narrator_metadata
from ..ai.narrator import call_narrator, call_narrator_metadata
from ..ai.provider_base import AIProvider, NarrationSink
from ..gamemaster.clocks import tick_threat_clock
from ..gamemaster.config import gm
from ..gamemaster.engine_memories import generate_engine_memories
from ..gamemaster.npc.matching import named_in
from ..gamemaster.npc.memory import consolidate_memory
from ..gamemaster.questions import answers
from ..gamemaster.scene_context import generate_scene_context
from ..models import (
    BrainResult,
    ClockEvent,
    ClockFillResult,
    Consequence,
    GameState,
    MemoryEntry,
    NpcData,
    RollResult,
    labels_of,
)
from ..parser import parse_narrator_response
from ..ruleset.make_move import resolve_move
from ..ruleset.meters import in_crisis
from ..ruleset.outcome_result import OutcomeResult


@dataclass
class ActionOutcome:
    consequences: list[Consequence]
    clock_events: list[ClockEvent]
    clock_fill_results: list[ClockFillResult]
    outcome: OutcomeResult


def resolve_action_consequences(
    game: GameState,
    brain: BrainResult,
    roll: RollResult,
    position: str,
) -> ActionOutcome:
    outcome = resolve_move(game, brain, roll)

    clock_events: list[ClockEvent] = []
    fill_results: list[ClockFillResult] = []
    if answers().outcome(roll.result) == "failure":
        clock_ticks = gm().clocks.miss_ticks_by_position[position]
        if clock_ticks > 0:
            tick_threat_clock(game, clock_ticks, clock_events, fill_results)

    return ActionOutcome(
        consequences=outcome.consequences,
        clock_events=clock_events,
        clock_fill_results=fill_results,
        outcome=outcome,
    )


def update_crisis(game: GameState) -> None:
    game.crisis_mode = in_crisis(game)


def apply_engine_memories(game: GameState, memories: list[tuple[NpcData, MemoryEntry]], narration: str) -> None:
    for npc, entry in memories:
        npc.memory.append(entry)
        npc.importance_accumulator += entry.importance
        if game.world.current_location and named_in(npc, narration):
            npc.last_location = game.world.current_location
        if npc.importance_accumulator >= gm().npc.reflection_threshold:
            npc.needs_reflection = True
        consolidate_memory(npc)


def apply_post_narration(
    provider: AIProvider,
    game: GameState,
    narration: str,
    brain: BrainResult,
    roll: RollResult | None,
    scene_present_ids: set[str],
    consequences: Sequence[Consequence],
) -> dict[str, Any]:
    cons_list = labels_of(list(consequences))
    present_names = [n.name for n in game.npcs if n.id in scene_present_ids]
    outcome = answers().outcome(roll.result) if roll is not None else None
    game.world.current_scene_context = generate_scene_context(game, brain, outcome, present_names)

    apply_engine_memories(
        game, generate_engine_memories(game, brain, outcome, scene_present_ids, consequences=cons_list), narration
    )

    metadata = call_narrator_metadata(provider, narration, game, brain=brain, consequences=cons_list)
    apply_narrator_metadata(
        game, metadata, scene_present_ids=scene_present_ids, world_addition=brain.world_addition or ""
    )

    return metadata


def narrate_scene(
    provider: AIProvider,
    game: GameState,
    prompt: str,
    stream: NarrationSink | None = None,
) -> str:
    return parse_narrator_response(game, call_narrator(provider, prompt, game, stream=stream))
