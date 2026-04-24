"""Post-narration scene finalization.

Shared pipeline for dialog and action paths after the narrator returns prose:

  - apply post-narration state mutations (engine memories, scene context,
    NPC metadata extraction)
  - combat-track / combat_position sync
  - optional revelation confirmation check
  - record scene intensity for pacing
  - append narration and session log entries (with trimming)
  - autonomous clock ticks and threat menace ticks
  - story completion check
  - scene-end bookkeeping: chaos adjustment, list maintenance, consolidation
  - director trigger detection and phase marking
  - database sync

Returns (revelation_confirmed, director_ctx) so the caller can feed the
director_ctx to the deferred director call.
"""

from ..ai.brain import call_revelation_check
from ..db import sync as _db_sync
from ..director import should_call_director
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    record_scene_intensity,
    tick_autonomous_clocks,
    update_chaos_factor,
)
from ..mechanics.random_events import (
    add_character_weight,
    add_thread_weight,
    consolidate_characters,
    consolidate_threads,
)
from ..mechanics.threats import resolve_full_menace, tick_autonomous_threats
from ..models import (
    BrainResult,
    CharacterListEntry,
    ClockEvent,
    GameState,
    NarrationEntry,
    RollResult,
    SceneLogEntry,
)
from ..story_state import check_story_completion, mark_revelation_used
from .finalization import apply_post_narration
from .tracks import sync_combat_tracks
from .turn_types import SceneContext


def _update_scene_lists(game: GameState, brain: BrainResult, metadata: dict, scene_present_ids: set) -> None:
    """Update Mythic thread/character lists after a scene.

    - NPCs present in the scene get weight bumped in characters list.
    - New NPCs from metadata get added to characters list.
    - Target NPC's thread (if any) gets weight bumped.
    """
    # Weight bump for present NPCs
    for npc in game.npcs:
        if npc.id in scene_present_ids:
            for c in game.narrative.characters_list:
                if c.id == npc.id or c.name == npc.name:
                    add_character_weight(game, c.id)
                    break

    # Add new NPCs to characters list
    new_npcs = metadata.get("new_npcs", [])
    for new_npc in new_npcs:
        name = new_npc.get("name", "")
        if not name:
            continue
        npc_obj = next((n for n in game.npcs if n.name == name), None)
        entry_id = npc_obj.id if npc_obj else f"char_{len(game.narrative.characters_list) + 1}"
        existing = any(c.name == name or c.id == entry_id for c in game.narrative.characters_list)
        if not existing:
            game.narrative.characters_list.append(
                CharacterListEntry(id=entry_id, name=name, entry_type="npc", weight=1, active=True)
            )

    # Weight bump for target NPC's linked thread
    if brain.target_npc:
        for t in game.narrative.threads:
            if brain.target_npc in t.id or brain.target_npc in t.name.lower():
                add_thread_weight(game, t.id)
                break


def finalize_scene(
    ctx: SceneContext,
    narration: str,
    log_entry: dict,
    prompt_summary: str,
    roll_result_str: str,
    roll: RollResult | None = None,
    consequences: list[str] | None = None,
    agency_clock_events: list[ClockEvent] | None = None,
) -> tuple[bool, dict | None]:
    """Shared post-narration processing for dialog and action scenes."""
    game = ctx.game
    brain = ctx.brain
    scene_present_ids = ctx.scene_present_ids
    activated_npc_names = [n.name for n in game.npcs if n.id in scene_present_ids]

    metadata = apply_post_narration(
        ctx.provider,
        game,
        narration,
        brain,
        roll,
        scene_present_ids,
        activated_npc_names,
        config=ctx.config,
        consequences=consequences,
        world_addition=brain.world_addition or "",
    )

    # Combat track ↔ combat_position sync (step 10.1)
    sync_combat_tracks(game)

    revelation_confirmed = False
    if ctx.pending_revs:
        revelation_confirmed = call_revelation_check(ctx.provider, narration, ctx.pending_revs[0], ctx.config)
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

    log_entry.pop("_pacing_type", None)
    nar.session_log.append(SceneLogEntry(**log_entry))
    if len(nar.session_log) > eng().pacing.max_session_log:
        nar.session_log = nar.session_log[-eng().pacing.max_session_log :]

    # Log revelation check result (only when a revelation was pending)
    if ctx.pending_revs and nar.session_log:
        nar.session_log[-1].revelation_check = {
            "id": ctx.pending_revs[0].id,
            "confirmed": revelation_confirmed,
        }

    auto_clock_events = tick_autonomous_clocks(game)
    if agency_clock_events and nar.session_log:
        nar.session_log[-1].clock_events.extend(agency_clock_events)
    if auto_clock_events and nar.session_log:
        nar.session_log[-1].clock_events.extend(auto_clock_events)

    # Autonomous threat menace ticks (step 11a)
    tick_autonomous_threats(game)
    resolve_full_menace(game)

    check_story_completion(game)

    # Scene-end bookkeeping (step 4.6)
    # 1. Chaos adjustment — applies to all scene types
    update_chaos_factor(game, roll_result_str, target_npc_id=brain.target_npc)

    # 2. List maintenance — invoked NPCs/threads get weight bump
    _update_scene_lists(game, brain, metadata, scene_present_ids)
    consolidate_threads(game)
    consolidate_characters(game)

    director_ctx = None
    director_reason = should_call_director(
        game,
        roll_result=roll_result_str,
        chaos_used=ctx.scene_setup.scene_type != "expected",
        new_npcs_found=bool(metadata.get("new_npcs")),
        revelation_used=revelation_confirmed,
    )
    if director_reason:
        director_ctx = {"narration": narration, "config": ctx.config}
        if nar.session_log:
            nar.session_log[-1].director_trigger = director_reason
        # Mark phase trigger used so it doesn't re-fire every subsequent turn
        bp = game.narrative.story_blueprint
        if director_reason.startswith("phase:") and bp is not None:
            bp.triggered_director_phases.append(director_reason[len("phase:") :])
    else:
        log(f"[Director] Skipped (no trigger at scene {nar.scene_count})")

    # Sync game state to database for query access
    _db_sync(game)

    return revelation_confirmed, director_ctx
