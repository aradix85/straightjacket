from __future__ import annotations

from dataclasses import dataclass, field

from ..ai.metadata import apply_narrator_metadata
from ..ai.narrator import call_narrator, call_narrator_metadata
from ..ai.provider_base import AIProvider
from ..ai.validator import validate_and_retry
from ..engine_loader import damage, eng
from ..logging_util import log
from ..mechanics import (
    generate_engine_memories,
    generate_scene_context,
)
from ..mechanics.consequences import tick_threat_clock
from ..mechanics.legacy import mark_legacy
from ..mechanics.move_effects import OutcomeResult
from ..mechanics.move_outcome import resolve_move_outcome
from ..models import BrainResult, ClockEvent, EngineConfig, GameState, MemoryEntry, RollResult
from ..npc import find_npc
from ..npc.memory import consolidate_memory
from ..parser import parse_narrator_response

from ..game.tracks import find_progress_track


@dataclass
class ActionOutcome:
    consequences: list[str] = field(default_factory=list)
    clock_events: list[ClockEvent] = field(default_factory=list)
    outcome: OutcomeResult | None = None
    position: str = "risky"
    effect: str = "standard"


def resolve_action_consequences(
    game: GameState,
    brain: BrainResult,
    roll: RollResult,
    position: str,
) -> ActionOutcome:
    outcome = resolve_move_outcome(game, brain.move, roll.result, target_npc_id=brain.target_npc)

    if outcome.combat_position:
        game.world.combat_position = outcome.combat_position

    clock_events: list[ClockEvent] = []
    if roll.result == "MISS":
        clock_ticks = damage("damage.miss.clock_ticks", position)
        if clock_ticks > 0:
            tick_threat_clock(game, clock_ticks, clock_events)

    _update_crisis(game)

    return ActionOutcome(
        consequences=outcome.consequences,
        clock_events=clock_events,
        outcome=outcome,
        position=position,
    )


def apply_progress_and_legacy(
    game: GameState,
    outcome: OutcomeResult,
    brain: BrainResult,
    source_track_category: str = "vow",
    source_track_rank: str = "dangerous",
) -> None:
    if outcome.progress_marks > 0:
        track = find_progress_track(game, source_track_category, target_track=brain.target_track)
        if track:
            for _ in range(outcome.progress_marks):
                added = track.mark_progress()
                if added:
                    log(f"[Track] {track.name}: +{added} ticks ({track.filled_boxes}/10 boxes)")

    if outcome.legacy_track:
        mark_legacy(game, outcome.legacy_track, source_rank=source_track_rank)


def _update_crisis(game: GameState) -> None:
    res = game.resources
    if res.health <= 0 and res.spirit <= 0:
        game.game_over = True
        game.crisis_mode = True
    elif res.health <= 0 or res.spirit <= 0:
        game.crisis_mode = True
    else:
        game.crisis_mode = False


def apply_engine_memories(game: GameState, memories: list[dict]) -> None:
    _e = eng()
    for mem in memories:
        npc = find_npc(game, mem["npc_id"])
        if not npc:
            continue
        entry = MemoryEntry(
            scene=game.narrative.scene_count,
            event=mem["event"],
            emotional_weight=mem["emotional_weight"],
            importance=mem["importance"],
            type="observation",
            tone=mem.get("tone", ""),
            tone_key=mem.get("tone_key", ""),
            about_npc=mem.get("about_npc"),
        )
        entry._score_debug = mem["_score_debug"] if "_score_debug" in mem else "engine-generated"
        npc.memory.append(entry)
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
    ctx = generate_scene_context(game, brain, roll, activated_npc_names)
    game.world.current_scene_context = ctx

    engine_mems = generate_engine_memories(game, brain, roll, scene_present_ids, consequences=consequences)
    if engine_mems:
        apply_engine_memories(game, engine_mems)

    metadata = call_narrator_metadata(provider, narration, game, config, brain=brain, consequences=consequences or [])
    apply_narrator_metadata(game, metadata, scene_present_ids=scene_present_ids, world_addition=world_addition)

    return metadata


def narrate_scene(
    provider: AIProvider,
    game: GameState,
    prompt: str,
    config: EngineConfig | None = None,
    validate_result_type: str = "",
    player_words: str = "",
    consequences: list[str] | None = None,
    consequence_sentences: list[str] | None = None,
) -> tuple[str, dict]:
    raw = call_narrator(provider, prompt, game, config)
    narration = parse_narrator_response(game, raw)

    val_report: dict = {}
    if validate_result_type:
        narration, val_report = validate_and_retry(
            provider,
            narration,
            prompt,
            validate_result_type,
            game,
            player_words=player_words,
            consequences=consequences,
            config=config,
            consequence_sentences=consequence_sentences,
        )

    return narration, val_report
