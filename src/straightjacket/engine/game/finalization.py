from __future__ import annotations

from typing import Any
from collections.abc import Sequence
from dataclasses import dataclass

from ..ai.metadata import apply_narrator_metadata
from ..ai.narrator import call_narrator, call_narrator_metadata
from ..ai.provider_base import AIProvider, NarrationSink
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    apply_boasts,
    ClockFillResult,
    generate_engine_memories,
    generate_scene_context,
)
from ..mechanics.consequences import tick_threat_clock
from ..mechanics.legacy import mark_legacy, mark_legacy_ticks, shifted_rank
from ..datasworn.oracle_rolls import roll_rows, plain_text
from ..mechanics.move_outcome import resolve_move_outcome
from ..mechanics.outcome_result import OutcomeResult
from ..mechanics.roll_sources import roll_source_without_stat
from ..models import BrainResult, ClockEvent, GameState, MemoryEntry, NpcData, ProgressTrack, RollResult
from ..npc import named_in
from ..npc.memory import consolidate_memory
from ..parser import parse_narrator_response

from ..mechanics import find_progress_track
from ..datasworn.moves import Move, get_moves
from ..datasworn.settings import load_package
from ..mechanics.consequences import roll_action


@dataclass
class ActionOutcome:
    consequences: list[str]
    clock_events: list[ClockEvent]
    clock_fill_results: list[ClockFillResult]
    outcome: OutcomeResult


def _chained_roll_value(game: GameState, brain: BrainResult, move: Move) -> tuple[str, int] | None:
    if move.valid_stats:
        best = max(move.valid_stats, key=game.stats.__getitem__)
        return best, game.stats[best]
    return roll_source_without_stat(game, move, brain.target_npc)


def _chain_oracle_move(game: GameState, move: Move, cfg: dict[str, Any], outcome: OutcomeResult) -> None:
    table = load_package(game.setting_id).oracle_table(cfg["oracle"])
    results = [plain_text(row.text) for _ in range(cfg["rolls"]) for row in roll_rows(table).rows]
    outcome.consequences.append(
        eng().ai_text.consequence_labels["chained_move"].format(move=move.name, result="; ".join(results))
    )
    mark_legacy_ticks(game, cfg["legacy_track"], cfg["ticks_per_roll"] * cfg["rolls"])
    log(f"[Chain] {move.name}: {'; '.join(results)}")


def _chain_move(game: GameState, brain: BrainResult, outcome: OutcomeResult) -> None:
    move = get_moves(game.setting_id)[outcome.chained_move]
    oracle_moves = eng().get_raw("oracle_moves")
    if move.roll_type == "no_roll" and outcome.chained_move in oracle_moves:
        _chain_oracle_move(game, move, oracle_moves[outcome.chained_move], outcome)
        return
    value = _chained_roll_value(game, brain, move)
    if value is None:
        log(f"[Chain] {outcome.chained_move}: nothing to roll with, follow-up skipped", level="warning")
        return
    label, stat_value = value
    adds = game.resources.next_move_bonus
    roll = roll_action(label, stat_value, outcome.chained_move, game.resources.momentum, adds)
    game.resources.next_move_bonus = 0
    chained = resolve_move_outcome(
        game, outcome.chained_move, roll.result, target_npc_id=brain.target_npc, match=roll.match
    )
    log(
        f"[Chain] {outcome.chained_move} ({label}={stat_value}, +{adds}): score {roll.action_score} vs [{roll.c1},{roll.c2}] → {roll.result}"
    )
    outcome.consequences.append(
        eng().ai_text.consequence_labels["chained_move"].format(move=move.name, result=roll.result)
    )
    outcome.consequences.extend(chained.consequences)
    outcome.follow_up_moves.extend(chained.follow_up_moves)
    if chained.legacy_track and not outcome.legacy_track:
        outcome.legacy_track = chained.legacy_track
        outcome.legacy_rank_shift = chained.legacy_rank_shift
        outcome.legacy_fixed_ticks = chained.legacy_fixed_ticks


def resolve_action_consequences(
    game: GameState,
    brain: BrainResult,
    roll: RollResult,
    position: str,
) -> ActionOutcome:
    outcome = resolve_move_outcome(game, brain.move, roll.result, target_npc_id=brain.target_npc, match=roll.match)
    if outcome.chained_move:
        _chain_move(game, brain, outcome)
    if outcome.boast_slots:
        apply_boasts(game, brain.boasts, outcome)

    if outcome.combat_position:
        game.world.combat_position = outcome.combat_position

    clock_events: list[ClockEvent] = []
    fill_results: list[ClockFillResult] = []
    if roll.result == "MISS":
        clock_ticks = eng().clocks.miss_ticks_by_position[position]
        if clock_ticks > 0:
            tick_threat_clock(game, clock_ticks, clock_events, fill_results)

    return ActionOutcome(
        consequences=outcome.consequences,
        clock_events=clock_events,
        clock_fill_results=fill_results,
        outcome=outcome,
    )


def apply_progress_and_legacy(
    game: GameState,
    outcome: OutcomeResult,
    brain: BrainResult,
    rolled_track: ProgressTrack | None,
) -> None:
    if outcome.progress_marks > 0:
        track_category = eng().get_raw("progress_mark_categories")[brain.move]
        track = find_progress_track(game, track_category, brain.target_track)
        for _ in range(outcome.progress_marks):
            added = track.mark_progress()
            if added:
                log(f"[Track] {track.name}: +{added} ticks ({track.filled_boxes}/{eng().progress.boxes} boxes)")

    if outcome.legacy_track and outcome.legacy_fixed_ticks:
        mark_legacy_ticks(game, outcome.legacy_track, outcome.legacy_fixed_ticks)
    elif outcome.legacy_track:
        if rolled_track is None:
            raise ValueError(f"{brain.move}: a legacy reward by rank needs the progress track that was rolled")
        rank = shifted_rank(rolled_track.rank, outcome.legacy_rank_shift)
        if rank is not None:
            mark_legacy(game, outcome.legacy_track, source_rank=rank)

    if outcome.experience_rank_shift is not None:
        if rolled_track is None:
            raise ValueError(f"{brain.move}: experience by rank needs the progress track that was rolled")
        rank = shifted_rank(rolled_track.rank, outcome.experience_rank_shift)
        gained = eng().legacy.experience_by_rank[rank] if rank is not None else 0
        game.campaign.xp += gained
        log(f"[Legacy] Experience +{gained} for a {rolled_track.rank} vow (total {game.campaign.xp})")


def update_crisis(game: GameState) -> None:
    game.crisis_mode = game.resources.health <= 0 or game.resources.spirit <= 0


def apply_engine_memories(game: GameState, memories: list[tuple[NpcData, MemoryEntry]], narration: str) -> None:
    _e = eng()
    for npc, entry in memories:
        npc.memory.append(entry)
        npc.importance_accumulator += entry.importance
        if game.world.current_location and named_in(npc, narration):
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
    consequences: Sequence[str],
    world_addition: str = "",
) -> dict[str, Any]:
    cons_list = list(consequences)
    ctx = generate_scene_context(game, brain, roll, activated_npc_names)
    game.world.current_scene_context = ctx

    apply_engine_memories(
        game, generate_engine_memories(game, brain, roll, scene_present_ids, consequences=cons_list), narration
    )

    metadata = call_narrator_metadata(provider, narration, game, brain=brain, consequences=cons_list)
    apply_narrator_metadata(game, metadata, scene_present_ids=scene_present_ids, world_addition=world_addition)

    return metadata


def narrate_scene(
    provider: AIProvider,
    game: GameState,
    prompt: str,
    stream: NarrationSink | None = None,
) -> str:
    return parse_narrator_response(game, call_narrator(provider, prompt, game, stream=stream))
