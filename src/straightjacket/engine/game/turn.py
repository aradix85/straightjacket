"""Turn processing: the core gameplay loop."""

from dataclasses import dataclass, field

import random

from ..ai.brain import call_brain, call_revelation_check
from ..ai.provider_base import AIProvider, drain_token_log
from ..datasworn.moves import Move, get_moves
from ..datasworn.settings import active_package
from ..db import sync as _db_sync
from ..director import should_call_director
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    apply_brain_location_time,
    can_burn_momentum,
    check_npc_agency,
    generate_consequence_sentences,
    purge_old_fired_clocks,
    record_scene_intensity,
    resolve_effect,
    resolve_position,
    roll_action,
    roll_progress,
    tick_autonomous_clocks,
    update_chaos_factor,
)
from ..mechanics.consequences import tick_threat_clock
from ..mechanics.fate import resolve_fate, resolve_likelihood
from ..mechanics.random_events import (
    add_character_weight,
    add_thread_weight,
    consolidate_characters,
    consolidate_threads,
    drain_pending_events,
)
from ..mechanics.scene import SceneSetup, check_scene
from ..mechanics.threats import (
    advance_menace_on_miss,
    advance_threat_by_id,
    resolve_full_menace,
    tick_autonomous_threats,
)
from ..models import (
    BrainResult,
    CharacterListEntry,
    ClockEvent,
    EngineConfig,
    GameState,
    NarrationEntry,
    NpcData,
    ProgressTrack,
    RandomEvent,
    RollResult,
    SceneLogEntry,
    ThreadEntry,
    ThreatEvent,
)
from ..npc import activate_npcs_for_prompt, find_npc, reactivate_npc
from ..prompt_builders import build_action_prompt, build_dialog_prompt
from ..story_state import check_story_completion, get_pending_revelations, mark_revelation_used

from .finalization import (
    apply_post_narration,
    apply_progress_and_legacy,
    narrate_scene,
    resolve_action_consequences,
)
from .tracks import complete_track, find_progress_track, roll_oracle_answer, sync_combat_tracks


@dataclass
class SceneContext:
    """Shared context built once per turn, passed to both dialog and action paths."""

    provider: AIProvider
    game: GameState
    brain: BrainResult
    config: EngineConfig | None
    player_message: str
    scene_setup: SceneSetup
    scene_present_ids: set[str]
    pending_revs: list
    npc_activation_debug: dict
    activated_npcs: list[NpcData] = field(default_factory=list)
    mentioned_npcs: list[NpcData] = field(default_factory=list)
    pending_random_events: list[RandomEvent] = field(default_factory=list)


@dataclass
class RollOutcome:
    """Result of the roll phase: roll plus the move/track context it came from."""

    roll: RollResult
    ds_move: Move | None
    track: ProgressTrack | None
    is_progress_roll: bool


@dataclass
class ActionResolution:
    """Everything produced by the consequences phase of an action turn."""

    position: str
    effect: str
    consequences: list[str]
    clock_events: list[ClockEvent]
    npc_agency: list[str]
    agency_clock_events: list[ClockEvent]
    threat_events: list[ThreatEvent]


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


# POST-NARRATION: shared logic for both dialog and action paths


def _finalize_scene(
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


# MAIN TURN ENTRY POINT


def process_turn(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None = None
) -> tuple[GameState, str, RollResult | None, dict | None, dict | None]:
    """Main turn pipeline. Orchestrates ten phases, delegating each to a helper."""
    # Phase 1: bookkeeping (log, drain accumulators, snapshot)
    _begin_turn(game, player_message)

    # Phase 2: scene test (Mythic 2e chaos vs d10) — before any AI call
    scene_setup = check_scene(game)

    # Phase 3: brain call + resolve anything brain requested (fate, oracle, random events)
    brain = _run_brain_phase(provider, game, player_message, config)
    pending_random_events = _resolve_brain_requests(game, brain)

    # Phase 4: state mutations from brain output, then build shared scene context
    _apply_brain_state_mutations(game, brain)
    ctx = _build_scene_context(provider, game, brain, config, player_message, scene_setup, pending_random_events)

    # Phase 5: dialog or oracle turns take an early-return path
    if brain.dialog_only or brain.move == "dialog" or brain.move == "ask_the_oracle":
        narration, director_ctx = _process_dialog_turn(ctx)
        return game, narration, None, None, director_ctx

    # Action turn from here on. Increment scene count.
    game.narrative.scene_count += 1

    # Phase 6: track creation (step 8.5) — happens before the roll
    _maybe_create_track(game, brain)

    # Phase 7: the roll itself — action dice or progress dice
    roll_outcome = _execute_roll(game, brain)
    roll = roll_outcome.roll

    # Phase 8: check if momentum burn could upgrade this roll (before consequences reduce it)
    burn_info = _check_burn_possibility(game, brain, roll_outcome, player_message, scene_setup)

    # Phase 9: resolve all mechanical consequences
    action_res = _resolve_action_phase(game, brain, roll_outcome)

    # Phase 10: narrator prompt + narrate + post-narration finalize
    narration, director_ctx = _narrate_action_and_finalize(ctx, roll_outcome, action_res, player_message)

    return game, narration, roll, burn_info, director_ctx


def _begin_turn(game: GameState, player_message: str) -> None:
    """Phase 1: log, drain stale accumulators, purge fired clocks, snapshot state."""
    log(f"[Turn] Scene {game.narrative.scene_count + 1} | Player: {player_message[: eng().truncations.log_long]}")
    drain_pending_events()
    drain_token_log()
    purge_old_fired_clocks(game)
    game.last_turn_snapshot = game.snapshot()
    game.last_turn_snapshot.player_input = player_message


def _run_brain_phase(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None
) -> BrainResult:
    """Phase 3a: call Brain to classify the player input, store result in snapshot."""
    brain = call_brain(provider, game, player_message, config)
    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.brain = brain
    return brain


def _resolve_brain_requests(game: GameState, brain: BrainResult) -> list[RandomEvent]:
    """Phase 3b: resolve fate question, oracle roll, and any random events
    generated by those resolutions. Advances menace on threats targeted by
    the random events. Returns the pending random events for the prompt.
    """
    if brain.fate_question:
        odds = resolve_likelihood(game, brain.fate_question)
        fate_result = resolve_fate(game, odds=odds, chaos_factor=game.world.chaos_factor, question=brain.fate_question)
        log(f"[Brain] Fate question resolved: '{brain.fate_question}' → {fate_result.answer}")

    if brain.oracle_table:
        pkg = active_package(game)
        if pkg:
            try:
                oracle_result = pkg.data.roll_oracle(brain.oracle_table)
                log(f"[Brain] Oracle rolled: {brain.oracle_table} → {oracle_result}")
            except KeyError:
                log(f"[Brain] Oracle table not found: {brain.oracle_table}", level="warning")

    pending_random_events = drain_pending_events()

    # Random events targeting threats → advance menace (step 11a)
    for event in pending_random_events:
        if event.target_id and any(t.id == event.target_id for t in game.threats):
            advance_threat_by_id(game, event.target_id, marks=1, source="random_event")

    return pending_random_events


def _apply_brain_state_mutations(game: GameState, brain: BrainResult) -> None:
    """Phase 4a: reactivate background target NPC, then apply brain's
    location/time updates to world state.
    """
    tid = brain.target_npc
    if tid:
        target = find_npc(game, tid)
        if target and target.status == "background":
            reactivate_npc(target, reason=f"targeted by player in scene {game.narrative.scene_count + 1}")
    apply_brain_location_time(game, brain)


def _build_scene_context(
    provider: AIProvider,
    game: GameState,
    brain: BrainResult,
    config: EngineConfig | None,
    player_message: str,
    scene_setup: SceneSetup,
    pending_random_events: list[RandomEvent],
) -> SceneContext:
    """Phase 4b: activate NPCs for the prompt and bundle everything into SceneContext."""
    activated_npcs, mentioned_npcs, npc_activation_debug = activate_npcs_for_prompt(game, brain, player_message)
    scene_present_ids = {n.id for n in activated_npcs} | {n.id for n in mentioned_npcs}
    pending_revs = get_pending_revelations(game)

    return SceneContext(
        provider=provider,
        game=game,
        brain=brain,
        config=config,
        player_message=player_message,
        scene_setup=scene_setup,
        scene_present_ids=scene_present_ids,
        pending_revs=pending_revs,
        npc_activation_debug=npc_activation_debug,
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
        pending_random_events=pending_random_events,
    )


def _process_dialog_turn(ctx: SceneContext) -> tuple[str, dict | None]:
    """Phase 5: dialog and oracle scenes — no roll, no consequences, just narrate."""
    game = ctx.game
    brain = ctx.brain
    is_oracle = brain.move == "ask_the_oracle"
    game.narrative.scene_count += 1

    oracle_answer = roll_oracle_answer(game) if is_oracle else ""
    prompt = build_dialog_prompt(
        game,
        brain,
        player_words=ctx.player_message,
        scene_setup=ctx.scene_setup,
        activated_npcs=ctx.activated_npcs,
        mentioned_npcs=ctx.mentioned_npcs,
        oracle_answer=oracle_answer,
        random_events=ctx.pending_random_events,
    )
    narration, val_report = narrate_scene(
        ctx.provider,
        game,
        prompt,
        config=ctx.config,
        validate_result_type="dialog",
        player_words=ctx.player_message,
    )

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.narration = narration

    result_label = "oracle" if is_oracle else "dialog"
    log_entry: dict = {
        "scene": game.narrative.scene_count,
        "summary": (brain.player_intent or ctx.player_message),
        "move": brain.move,
        "result": result_label,
        "consequences": [],
        "clock_events": [],
        "scene_type": ctx.scene_setup.scene_type,
        "npc_activation": ctx.npc_activation_debug,
        "validator": val_report,
        "_pacing_type": "breather",
    }
    if is_oracle:
        log_entry["oracle_answer"] = oracle_answer

    _, director_ctx = _finalize_scene(
        ctx,
        narration,
        log_entry=log_entry,
        prompt_summary=f"{result_label.capitalize()}: {(brain.player_intent or ctx.player_message)[: eng().truncations.log_medium]}",
        roll_result_str=result_label,
    )
    return narration, director_ctx


def _maybe_create_track(game: GameState, brain: BrainResult) -> None:
    """Phase 6: if the brain's move is a track-creating move, create the track
    (and, for vows, a linked thread entry). Fallback values for name/rank come
    from engine.yaml creation.* keys.
    """
    track_creating = eng().get_raw("track_creating_moves")
    track_category = track_creating.get(brain.move)
    if not track_category:
        return

    if not brain.track_name:
        _cr = eng().creation
        brain.track_name = (
            brain.player_intent[: _cr.brain_track_name_max_length].strip()
            or eng().ai_text.narrator_defaults["unnamed_track"]
        )
        log(f"[Track] Brain omitted track_name, generated: {brain.track_name}", level="warning")
    if not brain.track_rank:
        brain.track_rank = eng().creation.brain_track_rank_fallback
        log(f"[Track] Brain omitted track_rank, defaulting to {brain.track_rank}", level="warning")

    slug = brain.track_name.lower().replace(" ", "_")
    track_id = f"{track_category}_{slug}"
    new_track = ProgressTrack.new(
        id=track_id,
        name=brain.track_name,
        track_type=track_category,
        rank=brain.track_rank,
    )
    game.progress_tracks.append(new_track)
    log(f"[Track] Created {track_category} track: {brain.track_name} ({brain.track_rank}), id={track_id}")

    if track_category == "vow":
        game.narrative.threads.append(
            ThreadEntry(
                id=f"thread_{slug}",
                name=brain.track_name,
                thread_type="vow",
                weight=2,
                source="vow",
                linked_track_id=track_id,
            )
        )
        log(f"[Track] Created linked thread for vow: {brain.track_name}")


def _execute_roll(game: GameState, brain: BrainResult) -> RollOutcome:
    """Phase 7: execute either a progress roll or an action roll, log the
    result, store it in the snapshot. Returns the roll plus the move/track
    context downstream phases need.
    """
    ds_moves = get_moves(game.setting_id) if game.setting_id else {}
    ds_move = ds_moves.get(brain.move)
    is_progress_roll = ds_move is not None and ds_move.roll_type == "progress_roll"
    track: ProgressTrack | None = None

    if is_progress_roll:
        assert ds_move is not None  # guaranteed by is_progress_roll
        track = find_progress_track(game, ds_move.track_category, target_track=brain.target_track)
        filled = track.filled_boxes if track else 0
        track_name = track.name if track else ds_move.track_category
        roll = roll_progress(track_name, filled, brain.move)
        log(
            f"[Roll] {roll.move} (progress: {track_name}={filled} boxes): "
            f"{roll.action_score} vs [{roll.c1},{roll.c2}] "
            f"→ {roll.result}{' MATCH!' if roll.match else ''}"
        )
    else:
        stat_name = brain.stat
        roll = roll_action(stat_name, game.get_stat(stat_name), brain.move)
        _raw = roll.d1 + roll.d2 + roll.stat_value
        _score_str = f"{_raw}→{roll.action_score}(cap)" if _raw > roll.action_score else str(roll.action_score)
        log(
            f"[Roll] {roll.move} ({roll.stat_name}={roll.stat_value}): "
            f"{roll.d1}+{roll.d2}+{roll.stat_value}={_score_str} vs [{roll.c1},{roll.c2}] "
            f"→ {roll.result}{' MATCH!' if roll.match else ''}"
        )

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.roll = roll

    return RollOutcome(roll=roll, ds_move=ds_move, track=track, is_progress_roll=is_progress_roll)


def _check_burn_possibility(
    game: GameState,
    brain: BrainResult,
    roll_outcome: RollOutcome,
    player_message: str,
    scene_setup: SceneSetup,
) -> dict | None:
    """Phase 8: detect whether this roll could be upgraded by burning momentum.
    Must run before the consequences phase, because consequences can reduce
    momentum. Progress rolls cannot be burned (no action dice). Returns a dict
    with the data needed to re-narrate the upgraded result, or None.
    """
    roll = roll_outcome.roll
    if roll_outcome.is_progress_roll or roll.result not in ("MISS", "WEAK_HIT") or game.resources.momentum <= 0:
        return None
    potential_burn = can_burn_momentum(game, roll)
    if not potential_burn:
        return None
    return {
        "roll": roll,
        "new_result": potential_burn,
        "cost": game.resources.momentum,
        "brain": brain,
        "player_words": player_message,
        "scene_setup": scene_setup,
        "pre_snapshot": game.last_turn_snapshot,
    }


def _apply_track_completion(game: GameState, roll: RollResult, track: ProgressTrack) -> None:
    """Complete or fail the progress track based on the progress-roll result."""
    if roll.result == "STRONG_HIT":
        complete_track(game, track.id, "completed")
    elif roll.result == "MISS":
        complete_track(game, track.id, "failed")


def _maybe_mark_scene_challenge(game: GameState, brain: BrainResult, roll: RollResult) -> None:
    """Step 10.2: if the move is in scene_challenge_progress_moves and the roll
    hit, tick the active scene_challenge progress track.
    """
    sc_progress_moves = eng().get_raw("scene_challenge_progress_moves")
    if brain.move not in sc_progress_moves or roll.result not in ("STRONG_HIT", "WEAK_HIT"):
        return
    sc_track = find_progress_track(game, "scene_challenge")
    if not sc_track:
        return
    added = sc_track.mark_progress()
    if added:
        log(f"[Track] Scene challenge '{sc_track.name}': +{added} ticks ({sc_track.filled_boxes}/10 boxes)")


def _maybe_tick_weak_hit_clock(
    game: GameState, roll: RollResult, position: str, clock_events: list[ClockEvent]
) -> None:
    """WEAK_HIT clock tick — turn-only (correction/burn re-narration skips this).
    Always ticks on desperate; otherwise rolls weak_hit_clock_tick_chance.
    """
    if roll.result != "WEAK_HIT" or position == "controlled":
        return
    should_tick = (position == "desperate") or (random.random() < eng().pacing.weak_hit_clock_tick_chance)
    if should_tick:
        tick_threat_clock(game, 1, clock_events)


def _collect_threat_events(game: GameState, roll: RollResult) -> list[ThreatEvent]:
    """Assemble the threat events for the prompt: menace-on-miss + Forsake Your Vow
    + overcome-under-pressure acknowledgments.
    """
    events: list[ThreatEvent] = advance_menace_on_miss(game) if roll.result == "MISS" else []
    events.extend(resolve_full_menace(game))

    high_threshold = eng().threats.menace_high_threshold
    for threat in game.threats:
        if threat.status == "overcome" and threat.menace_filled_boxes / 10 >= high_threshold:
            events.append(
                ThreatEvent(
                    threat_id=threat.id,
                    threat_name=threat.name,
                    ticks_added=0,
                    menace_full=False,
                    source="overcome_under_pressure",
                )
            )
    return events


def _track_gather_information_success(game: GameState, brain: BrainResult, roll: RollResult) -> None:
    """Increment gather_count on a successful gather_information move.
    Feeds into the information-gating subsystem (step 6).
    """
    if brain.move != "adventure/gather_information" or roll.result not in ("STRONG_HIT", "WEAK_HIT"):
        return
    if not brain.target_npc:
        return
    target = find_npc(game, brain.target_npc)
    if target:
        target.gather_count += 1


def _resolve_action_phase(game: GameState, brain: BrainResult, roll_outcome: RollOutcome) -> ActionResolution:
    """Phase 9: resolve every mechanical consequence of the roll. Sub-steps:
    position/effect, move outcome + clocks + crisis, progress marks and legacy,
    track completion, scene challenge routing, WEAK_HIT clocks, NPC agency,
    threat events, gather_information tracking.
    """
    roll = roll_outcome.roll
    ds_move = roll_outcome.ds_move
    track = roll_outcome.track
    is_progress_roll = roll_outcome.is_progress_roll

    # Position and effect (deterministic from game state)
    position = resolve_position(game, brain)
    effect = resolve_effect(game, brain, position)

    # Move outcome + MISS clocks + crisis (shared with correction/burn)
    action = resolve_action_consequences(game, brain, roll, position)
    consequences = action.consequences
    clock_events = action.clock_events

    # Progress marks and legacy tracks (shared with correction/burn)
    if action.outcome:
        source_category = ds_move.track_category if ds_move else "vow"
        source_rank = track.rank if is_progress_roll and track else "dangerous"
        apply_progress_and_legacy(game, action.outcome, brain, source_category, source_rank)

    if is_progress_roll and track:
        _apply_track_completion(game, roll, track)

    _maybe_mark_scene_challenge(game, brain, roll)
    _maybe_tick_weak_hit_clock(game, roll, position, clock_events)

    npc_agency, agency_clock_events = check_npc_agency(game)

    threat_events = _collect_threat_events(game, roll)

    _track_gather_information_success(game, brain, roll)

    return ActionResolution(
        position=position,
        effect=effect,
        consequences=consequences,
        clock_events=clock_events,
        npc_agency=npc_agency,
        agency_clock_events=agency_clock_events,
        threat_events=threat_events,
    )


def _narrate_action_and_finalize(
    ctx: SceneContext,
    roll_outcome: RollOutcome,
    action_res: ActionResolution,
    player_message: str,
) -> tuple[str, dict | None]:
    """Phase 10: build the action prompt, call the narrator, finalize the scene."""
    game = ctx.game
    brain = ctx.brain
    roll = roll_outcome.roll

    consequence_sentences = generate_consequence_sentences(
        action_res.consequences, action_res.clock_events, game, brain
    )

    prompt = build_action_prompt(
        game,
        brain,
        roll,
        action_res.consequences,
        action_res.clock_events,
        action_res.npc_agency,
        player_words=player_message,
        scene_setup=ctx.scene_setup,
        activated_npcs=ctx.activated_npcs,
        mentioned_npcs=ctx.mentioned_npcs,
        position=action_res.position,
        effect=action_res.effect,
        consequence_sentences=consequence_sentences,
        random_events=ctx.pending_random_events,
        threat_events=action_res.threat_events,
    )
    narration, val_report = narrate_scene(
        ctx.provider,
        game,
        prompt,
        config=ctx.config,
        validate_result_type=roll.result,
        player_words=player_message,
        consequences=action_res.consequences,
        consequence_sentences=consequence_sentences,
    )

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.narration = narration

    _, director_ctx = _finalize_scene(
        ctx,
        narration,
        log_entry={
            "scene": game.narrative.scene_count,
            "summary": (brain.player_intent or player_message),
            "move": brain.move,
            "result": roll.result,
            "consequences": action_res.consequences,
            "clock_events": action_res.clock_events,
            "position": action_res.position,
            "effect": action_res.effect,
            "scene_type": ctx.scene_setup.scene_type,
            "npc_activation": ctx.npc_activation_debug,
            "validator": val_report,
            "_pacing_type": "action",
        },
        prompt_summary=f"Action ({roll.result}): {(brain.player_intent or player_message)[: eng().truncations.log_medium]}",
        roll_result_str=roll.result,
        roll=roll,
        consequences=action_res.consequences,
        agency_clock_events=action_res.agency_clock_events,
    )
    return narration, director_ctx
