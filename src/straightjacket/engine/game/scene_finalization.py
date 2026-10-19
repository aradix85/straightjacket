from collections.abc import Sequence
from typing import Any

from ..ai.brain import call_revelation_check
from ..director import should_call_director
from ..engine_loader import eng
from ..gamemaster.clock_ticks import tick_autonomous_clocks
from ..gamemaster.npc.matching import find_npc
from ..gamemaster.questions import outcome_of
from ..gamemaster.random_events import (
    add_character_weight,
    add_thread_weight,
    consolidate_characters,
    consolidate_threads,
)
from ..gamemaster.world import record_scene_intensity, update_chaos_factor
from ..logging_util import log
from ..models import (
    BrainResult,
    CharacterListEntry,
    ClockEvent,
    Consequence,
    GameState,
    NarrationEntry,
    RandomEvent,
    RollResult,
    SceneLogEntry,
    ThreatEvent,
)
from ..ruleset.threats import tick_autonomous_threats
from ..ruleset.tracks import vow_acted_on
from ..story_state import check_act_transition, check_story_completion, mark_revelation_used
from .finalization import apply_post_narration
from .turn_types import DirectorCall, SceneContext


def _update_characters_list(game: GameState, metadata: dict[str, Any], scene_present_ids: set[Any]) -> None:
    for npc in game.npcs:
        if npc.id in scene_present_ids:
            for c in game.narrative.characters_list:
                if c.id == npc.id or c.name == npc.name:
                    add_character_weight(game, c.id)
                    break

    for new_npc in metadata["new_npcs"]:
        if not new_npc["name"]:
            continue
        npc_obj = find_npc(game, new_npc["name"])
        name = npc_obj.name if npc_obj else new_npc["name"]
        entry_id = npc_obj.id if npc_obj else f"char_{len(game.narrative.characters_list) + 1}"
        existing = any(c.name == name or c.id == entry_id for c in game.narrative.characters_list)
        if not existing:
            game.narrative.characters_list.append(
                CharacterListEntry(id=entry_id, name=name, entry_type="npc", weight=1, active=True)
            )


def invoked_threads(
    game: GameState,
    brain: BrainResult,
    roll: RollResult | None,
    events: Sequence[RandomEvent],
    threat_events: Sequence[ThreatEvent],
) -> list[str]:
    vow = vow_acted_on(game, brain.move, brain.target_track) if roll is not None else None
    vow_ids: set[str] = {vow.id} if vow is not None else set()
    threats = {t.id: t for t in game.threats}
    threat_ids = {e.threat_id for e in threat_events} | {e.target_id for e in events if e.target_id in threats}
    vow_ids |= {vow_id for i in threat_ids if (vow_id := threats[i].linked_vow_id) is not None}
    event_targets = {e.target_id for e in events}
    return [
        t.id
        for t in game.narrative.threads
        if t.active and (t.id in event_targets or (t.linked_track_id is not None and t.linked_track_id in vow_ids))
    ]


def finalize_scene(
    ctx: SceneContext,
    narration: str,
    log_entry: dict[str, Any],
    prompt_summary: str,
    roll_result_str: str,
    roll: RollResult | None = None,
    *,
    consequences: Sequence[Consequence],
    agency_clock_events: Sequence[ClockEvent],
    threat_events: Sequence[ThreatEvent],
) -> tuple[bool, DirectorCall | None]:
    game = ctx.game
    brain = ctx.brain
    scene_present_ids = ctx.scene_present_ids

    metadata = apply_post_narration(
        ctx.provider,
        game,
        narration,
        brain,
        roll,
        scene_present_ids,
        consequences=consequences,
    )

    revelation_confirmed = False
    if ctx.pending_revs:
        revelation_confirmed = call_revelation_check(ctx.provider, narration, ctx.pending_revs[0])
        if revelation_confirmed:
            mark_revelation_used(game, ctx.pending_revs[0].id)

    scene_type = ctx.scene_setup.scene_type if ctx.scene_setup.scene_type != "expected" else log_entry["_pacing_type"]
    record_scene_intensity(game, scene_type)

    nar = game.narrative
    nar.narration_history.append(
        NarrationEntry(
            scene=nar.scene_count,
            prompt_summary=prompt_summary,
            narration=narration,
        )
    )
    if len(nar.narration_history) > eng().pacing.max_narration_history:
        nar.narration_history = nar.narration_history[-eng().pacing.max_narration_history :]

    log_entry.pop("_pacing_type")
    nar.session_log.append(SceneLogEntry(**log_entry))
    if len(nar.session_log) > eng().pacing.max_session_log:
        nar.session_log = nar.session_log[-eng().pacing.max_session_log :]

    auto_clock_events = tick_autonomous_clocks(game)
    nar.session_log[-1].clock_events.extend(agency_clock_events)
    nar.session_log[-1].clock_events.extend(auto_clock_events)

    tick_autonomous_threats(game)

    check_act_transition(game)
    check_story_completion(game)

    update_chaos_factor(game, outcome_of(roll_result_str), target_npc_id=brain.target_npc)

    _update_characters_list(game, metadata, scene_present_ids)
    scene_events = [*ctx.pending_random_events, *filter(None, [ctx.scene_setup.interrupt_event])]
    for thread_id in invoked_threads(game, brain, roll, scene_events, threat_events):
        add_thread_weight(game, thread_id)
    consolidate_threads(game)
    consolidate_characters(game)

    director_ctx: DirectorCall | None = None
    director_reason = should_call_director(
        game,
        roll_result=roll_result_str,
        chaos_used=ctx.scene_setup.scene_type != "expected",
        new_npcs_found=bool(metadata["new_npcs"]),
        revelation_used=revelation_confirmed,
    )
    if director_reason:
        director_ctx = DirectorCall(narration=narration)
        log(f"[Director] Queued (reason: {director_reason})")
    else:
        log(f"[Director] Skipped (no trigger at scene {nar.scene_count})")

    return revelation_confirmed, director_ctx
