from __future__ import annotations

from typing import Any
from collections.abc import Sequence
from dataclasses import dataclass, field

from ..ai.metadata import apply_narrator_metadata
from ..ai.narrator import call_narrator, call_narrator_metadata
from ..ai.provider_base import AIProvider, NarrationSink
from ..engine_loader import damage, eng
from ..logging_util import log
from ..mechanics import (
    ClockFillResult,
    generate_engine_memories,
    generate_scene_context,
)
from ..mechanics.consequences import tick_threat_clock
from ..mechanics.legacy import mark_legacy, mark_legacy_ticks, shifted_rank
from ..mechanics.move_effects import OutcomeResult, strip_datasworn_links
from ..mechanics.move_outcome import resolve_move_outcome
from ..models import BrainResult, ClockEvent, EngineConfig, GameState, MemoryEntry, RollResult
from ..npc import find_npc
from ..npc.memory import consolidate_memory
from ..parser import parse_narrator_response

from ..mechanics import find_progress_track
from ..datasworn.moves import Move, get_moves
from ..datasworn.settings import load_package
from ..mechanics.consequences import roll_action


@dataclass
class ActionOutcome:
    consequences: list[str] = field(default_factory=list)
    clock_events: list[ClockEvent] = field(default_factory=list)
    clock_fill_results: list[ClockFillResult] = field(default_factory=list)
    outcome: OutcomeResult | None = None
    position: str = "risky"
    effect: str = "standard"


def _chained_roll_value(game: GameState, brain: BrainResult, move: Move) -> tuple[str, int] | None:
    options = [option for condition in move.conditions for option in condition.roll_options]
    stats = [option.stat for option in options if option.using == "stat" and option.stat]
    if stats:
        best = max(stats, key=game.get_stat)
        return best, game.get_stat(best)
    track = next(
        (
            t
            for t in game.progress_tracks
            if t.track_type == "connection" and t.id == f"connection_{brain.target_npc}" and t.status == "active"
        ),
        None,
    )
    ranked = {option.label: option.value for option in options if option.using == "custom" and option.value is not None}
    if track is None or track.rank not in ranked:
        return None
    return track.rank, int(ranked[track.rank])


def _chain_oracle_move(game: GameState, move: Move, cfg: dict[str, Any], outcome: OutcomeResult) -> None:
    path = cfg["oracle"]
    data = load_package(game.setting_id).oracle_data_for(path)
    table = data.oracle(path) if data is not None else None
    if table is None:
        raise KeyError(f"Oracle '{path}' for chained move {move.name} missing in setting {game.setting_id!r}")
    results = [strip_datasworn_links(str(table.roll().value)) for _ in range(cfg["rolls"])]
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
    outcome.pay_the_price = outcome.pay_the_price or chained.pay_the_price
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

    if outcome.combat_position:
        game.world.combat_position = outcome.combat_position

    clock_events: list[ClockEvent] = []
    fill_results: list[ClockFillResult] = []
    if roll.result == "MISS":
        clock_ticks = damage("damage.miss.clock_ticks", position)
        if clock_ticks > 0:
            tick_threat_clock(game, clock_ticks, clock_events, fill_results)

    _update_crisis(game)

    return ActionOutcome(
        consequences=outcome.consequences,
        clock_events=clock_events,
        clock_fill_results=fill_results,
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

    if outcome.legacy_track and outcome.legacy_fixed_ticks:
        mark_legacy_ticks(game, outcome.legacy_track, outcome.legacy_fixed_ticks)
    elif outcome.legacy_track:
        rank = shifted_rank(source_track_rank, outcome.legacy_rank_shift)
        if rank is not None:
            mark_legacy(game, outcome.legacy_track, source_rank=rank)


def _update_crisis(game: GameState) -> None:
    res = game.resources
    if res.health <= 0 and res.spirit <= 0:
        game.game_over = True
        game.crisis_mode = True
    elif res.health <= 0 or res.spirit <= 0:
        game.crisis_mode = True
    else:
        game.crisis_mode = False


def apply_engine_memories(game: GameState, memories: list[dict[str, Any]]) -> None:
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
    consequences: Sequence[str] = (),
    world_addition: str = "",
) -> dict[str, Any]:
    cons_list = list(consequences)
    ctx = generate_scene_context(game, brain, roll, activated_npc_names)
    game.world.current_scene_context = ctx

    engine_mems = generate_engine_memories(game, brain, roll, scene_present_ids, consequences=cons_list)
    if engine_mems:
        apply_engine_memories(game, engine_mems)

    metadata = call_narrator_metadata(provider, narration, game, config, brain=brain, consequences=cons_list)
    apply_narrator_metadata(game, metadata, scene_present_ids=scene_present_ids, world_addition=world_addition)

    return metadata


def narrate_scene(
    provider: AIProvider,
    game: GameState,
    prompt: str,
    config: EngineConfig | None = None,
    stream: NarrationSink | None = None,
) -> str:
    raw = call_narrator(provider, prompt, game, config, stream=stream)
    return parse_narrator_response(game, raw)
