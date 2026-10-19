from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ..ai.metadata import apply_narrator_metadata
from ..ai.narrator import call_narrator, call_narrator_metadata
from ..ai.provider_base import AIProvider, NarrationSink
from ..engine_loader import eng
from ..gamemaster.clock_ticks import tick_threat_clock
from ..gamemaster.engine_memories import generate_engine_memories, generate_scene_context
from ..gamemaster.npc.matching import named_in
from ..gamemaster.npc.memory import consolidate_memory
from ..gamemaster.questions import answers
from ..logging_util import log
from ..models import (
    BrainResult,
    ClockEvent,
    ClockFillResult,
    Consequence,
    GameState,
    MemoryEntry,
    NpcData,
    ProgressTrack,
    RollResult,
    consequence,
    labels_of,
)
from ..parser import parse_narrator_response
from ..ruleset.boasts import apply_boasts
from ..ruleset.bond import connection_track
from ..ruleset.legacy import mark_legacy, mark_legacy_ticks, shifted_rank
from ..ruleset.move_effects import apply_effects, parse_effects
from ..ruleset.move_outcome import resolve_move_outcome
from ..ruleset.moves import Move, get_moves
from ..ruleset.outcome_result import OutcomeResult, move_outcome_config
from ..ruleset.roll_sources import best_roll_option, roll_source_without_stat
from ..ruleset.rolls import roll_action
from ..ruleset.tracks import find_progress_track
from ..setting.loader import OracleTable
from ..setting.oracle_rolls import plain_text, roll_rows


@dataclass
class ActionOutcome:
    consequences: list[Consequence]
    clock_events: list[ClockEvent]
    clock_fill_results: list[ClockFillResult]
    outcome: OutcomeResult


def _chained_roll_value(game: GameState, brain: BrainResult, move: Move) -> tuple[str, int] | None:
    if move.valid_stats:
        return best_roll_option(game, move)
    return roll_source_without_stat(game, move, brain.target_npc)


def _roll_chained_table(table: OracleTable, reroll_prefixes: list[str]) -> str:
    while True:
        rolled = roll_rows(table)
        rows = [plain_text(row.text) for row in rolled.rows]
        if not any(row.startswith(tuple(reroll_prefixes)) for row in rows):
            text = "; ".join(rows)
            return eng().ai_text.consequence_labels["oracle_worse"].format(result=text) if rolled.worse else text


def _chain_oracle_move(game: GameState, move: Move, cfg: dict[str, Any], outcome: OutcomeResult) -> None:
    table = move.tables[cfg["table"]]
    results = [_roll_chained_table(table, cfg["reroll_prefixes"]) for _ in range(cfg["rolls"])]
    outcome.consequences.append(consequence("chained_move", move=move.name, result="; ".join(results)))
    if cfg["legacy_track"]:
        mark_legacy_ticks(game, cfg["legacy_track"], cfg["ticks_per_roll"] * cfg["rolls"])
    log(f"[Chain] {move.name}: {'; '.join(results)}")


def _chain_without_bond(game: GameState, brain: BrainResult, outcome: OutcomeResult) -> bool:
    cfg = move_outcome_config(game, outcome.chained_move)
    track = connection_track(game, brain.target_npc) if brain.target_npc is not None else None
    if "without_bond" not in cfg or track is None or track.status == "bonded":
        return False
    marked = apply_effects(game, parse_effects(cfg["without_bond"]), target_npc_id=brain.target_npc)
    outcome.consequences.extend(marked.consequences)
    log(f"[Chain] {outcome.chained_move}: no bond with {track.name} yet, so progress is marked without a roll")
    return True


def _chain_move(game: GameState, brain: BrainResult, outcome: OutcomeResult) -> None:
    move = get_moves(game.setting_id)[outcome.chained_move]
    oracle_moves = eng().get_raw("oracle_moves")
    if move.roll_type == "no_roll" and outcome.chained_move in oracle_moves:
        _chain_oracle_move(game, move, oracle_moves[outcome.chained_move], outcome)
        return
    if _chain_without_bond(game, brain, outcome):
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
    outcome.consequences.append(consequence("chained_move", move=move.name, result=roll.result))
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
