#!/usr/bin/env python3
"""Turn processing: the core gameplay loop."""

from ..ai.brain import call_brain, call_revelation_check
from ..ai.narrator import call_narrator
from ..ai.provider_base import AIProvider
from ..director import should_call_director
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    apply_brain_location_time,
    apply_consequences,
    can_burn_momentum,
    check_npc_agency,
    purge_old_fired_clocks,
    record_scene_intensity,
    resolve_effect,
    resolve_position,
    roll_action,
    tick_autonomous_clocks,
    update_chaos_factor,
)
from ..mechanics.random_events import drain_pending_events
from ..mechanics.scene import SceneSetup, check_scene
from ..models import BrainResult, EngineConfig, GameState, NarrationEntry, RollResult, SceneLogEntry
from ..npc import activate_npcs_for_prompt, find_npc, reactivate_npc
from ..parser import parse_narrator_response
from ..prompt_builders import build_action_prompt, build_dialog_prompt
from ..story_state import default_scene_range, get_pending_revelations, mark_revelation_used

from .finalization import apply_post_narration


def _roll_oracle_answer(game: GameState) -> str:
    """Roll an oracle answer for ask_the_oracle moves. Returns a meaning pair string."""
    from ..datasworn.settings import active_package

    pkg = active_package(game)
    if not pkg:
        return ""
    action, theme = pkg.roll_action_theme()
    if action and theme:
        return f"{action} / {theme}"
    return ""


# ── Scene-end list maintenance (step 4.6 / 6.5) ──────────────


def _update_scene_lists(game: GameState, brain: BrainResult, metadata: dict, scene_present_ids: set) -> None:
    """Update Mythic thread/character lists after a scene.

    - NPCs present in the scene get weight bumped in characters list.
    - New NPCs from metadata get added to characters list.
    - Target NPC's thread (if any) gets weight bumped.
    """
    from ..mechanics.random_events import add_character_weight, add_thread_weight
    from ..models import CharacterListEntry

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
        existing = any(c.name == name for c in game.narrative.characters_list)
        if not existing:
            # Find the NPC id from game.npcs (process_new_npcs already added it)
            npc_obj = next((n for n in game.npcs if n.name == name), None)
            entry_id = npc_obj.id if npc_obj else f"char_{len(game.narrative.characters_list) + 1}"
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
    provider: AIProvider,
    game: GameState,
    narration: str,
    brain: BrainResult,
    player_message: str,
    scene_present_ids: set,
    pending_revs: list,
    scene_setup: SceneSetup,
    npc_activation_debug: dict,
    log_entry: dict,
    prompt_summary: str,
    roll_result_str: str,
    config: EngineConfig | None,
    agency_clock_events: list | None = None,
    roll: RollResult | None = None,
    consequences: list[str] | None = None,
    position: str = "risky",
    effect: str = "standard",
) -> tuple[bool, dict | None]:
    """Shared post-narration processing for dialog and action scenes."""
    activated_npc_names = [n.name for n in game.npcs if n.id in scene_present_ids]

    # Engine-side state mutations (step 3.1): scene context, memories, metadata
    metadata = apply_post_narration(
        provider,
        game,
        narration,
        brain,
        roll,
        scene_present_ids,
        activated_npc_names,
        config=config,
        consequences=consequences,
        world_addition=brain.world_addition or "",
    )

    revelation_confirmed = False
    if pending_revs:
        revelation_confirmed = call_revelation_check(provider, narration, pending_revs[0], config)
        if revelation_confirmed:
            mark_revelation_used(game, pending_revs[0].id)

    scene_type = (
        scene_setup.scene_type if scene_setup.scene_type != "expected" else log_entry.get("_pacing_type", "action")
    )
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
    if pending_revs and nar.session_log:
        nar.session_log[-1].revelation_check = {
            "id": pending_revs[0].id,
            "confirmed": revelation_confirmed,
        }

    auto_clock_events = tick_autonomous_clocks(game)
    if agency_clock_events and nar.session_log:
        nar.session_log[-1].clock_events.extend(agency_clock_events)
    if auto_clock_events and nar.session_log:
        nar.session_log[-1].clock_events.extend(auto_clock_events)

    _check_story_completion(game)

    # Scene-end bookkeeping (step 4.6)
    # 1. Chaos adjustment — applies to all scene types
    update_chaos_factor(game, roll_result_str, target_npc_id=brain.target_npc)

    # 2. List maintenance — invoked NPCs/threads get weight bump
    from ..mechanics.random_events import consolidate_characters, consolidate_threads

    _update_scene_lists(game, brain, metadata, scene_present_ids)
    consolidate_threads(game)
    consolidate_characters(game)

    director_ctx = None
    director_reason = should_call_director(
        game,
        roll_result=roll_result_str,
        chaos_used=scene_setup.scene_type != "expected",
        new_npcs_found=bool(metadata.get("new_npcs")),
        revelation_used=revelation_confirmed,
    )
    if director_reason:
        director_ctx = {"narration": narration, "config": config}
        if nar.session_log:
            nar.session_log[-1].director_trigger = director_reason
        # Mark phase trigger used so it doesn't re-fire every subsequent turn
        bp = game.narrative.story_blueprint
        if director_reason.startswith("phase:") and bp is not None:
            bp.triggered_director_phases.append(director_reason[len("phase:") :])
    else:
        log(f"[Director] Skipped (no trigger at scene {nar.scene_count})")

    # Sync game state to database for query access
    from ..db import sync as _db_sync

    _db_sync(game)

    return revelation_confirmed, director_ctx


# MAIN TURN ENTRY POINT


def process_turn(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None = None
) -> tuple[GameState, str, RollResult | None, dict | None, dict | None]:
    nar = game.narrative
    log(f"[Turn] Scene {nar.scene_count + 1} | Player: {player_message[:100]}")

    purge_old_fired_clocks(game)

    # Snapshot BEFORE any mutation
    game.last_turn_snapshot = game.snapshot()
    game.last_turn_snapshot.player_input = player_message

    # Scene test BEFORE brain call (Mythic 2e scene structure)
    scene_setup = check_scene(game)

    brain = call_brain(provider, game, player_message, config)
    game.last_turn_snapshot.brain = brain

    # Drain any random events generated by fate_question tool calls during Brain phase
    pending_random_events = drain_pending_events()

    # Reactivate background NPC if Brain targets one
    tid = brain.target_npc
    if tid:
        target = find_npc(game, tid)
        if target and target.status == "background":
            reactivate_npc(target, reason=f"targeted by player in scene {nar.scene_count + 1}")

    apply_brain_location_time(game, brain)

    activated_npcs, mentioned_npcs, npc_activation_debug = activate_npcs_for_prompt(game, brain, player_message)
    _scene_present_ids = {n.id for n in activated_npcs} | {n.id for n in mentioned_npcs}

    pending_revs = get_pending_revelations(game)

    # ── Dialog path ───────────────────────────────────────────
    if brain.dialog_only or brain.move == "dialog":
        nar.scene_count += 1
        prompt = build_dialog_prompt(
            game,
            brain,
            player_words=player_message,
            scene_setup=scene_setup,
            activated_npcs=activated_npcs,
            mentioned_npcs=mentioned_npcs,
            config=config,
            random_events=pending_random_events,
        )
        raw = call_narrator(provider, prompt, game, config)
        narration = parse_narrator_response(game, raw)

        from ..ai.validator import validate_and_retry

        narration, val_report = validate_and_retry(
            provider, narration, prompt, "dialog", game, player_words=player_message, config=config
        )

        if game.last_turn_snapshot is not None:
            game.last_turn_snapshot.narration = narration

        _, director_ctx = _finalize_scene(
            provider,
            game,
            narration,
            brain,
            player_message,
            _scene_present_ids,
            pending_revs,
            scene_setup,
            npc_activation_debug,
            log_entry={
                "scene": nar.scene_count,
                "summary": (brain.player_intent or player_message),
                "move": brain.move,
                "result": "dialog",
                "consequences": [],
                "clock_events": [],
                "scene_type": scene_setup.scene_type,
                "npc_activation": npc_activation_debug,
                "validator": val_report,
                "_pacing_type": "breather",
            },
            prompt_summary=f"Dialog: {(brain.player_intent or player_message)[:80]}",
            roll_result_str="dialog",
            config=config,
            roll=None,
            consequences=[],
        )
        return game, narration, None, None, director_ctx

    # ── Oracle path ───────────────────────────────────────────
    if brain.move == "ask_the_oracle":
        nar.scene_count += 1
        oracle_answer = _roll_oracle_answer(game)
        prompt = build_dialog_prompt(
            game,
            brain,
            player_words=player_message,
            scene_setup=scene_setup,
            activated_npcs=activated_npcs,
            mentioned_npcs=mentioned_npcs,
            config=config,
            oracle_answer=oracle_answer,
            random_events=pending_random_events,
        )
        raw = call_narrator(provider, prompt, game, config)
        narration = parse_narrator_response(game, raw)

        from ..ai.validator import validate_and_retry

        narration, val_report = validate_and_retry(
            provider, narration, prompt, "dialog", game, player_words=player_message, config=config
        )

        if game.last_turn_snapshot is not None:
            game.last_turn_snapshot.narration = narration

        _, director_ctx = _finalize_scene(
            provider,
            game,
            narration,
            brain,
            player_message,
            _scene_present_ids,
            pending_revs,
            scene_setup,
            npc_activation_debug,
            log_entry={
                "scene": nar.scene_count,
                "summary": (brain.player_intent or player_message),
                "move": "ask_the_oracle",
                "result": "oracle",
                "consequences": [],
                "clock_events": [],
                "scene_type": scene_setup.scene_type,
                "npc_activation": npc_activation_debug,
                "validator": val_report,
                "_pacing_type": "breather",
                "oracle_answer": oracle_answer,
            },
            prompt_summary=f"Oracle: {(brain.player_intent or player_message)[:80]}",
            roll_result_str="oracle",
            config=config,
            roll=None,
            consequences=[],
        )
        return game, narration, None, None, director_ctx

    # ── Action path ───────────────────────────────────────────
    nar.scene_count += 1
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

    # Check burn possibility BEFORE consequences reduce momentum
    burn_info = None
    if roll.result in ("MISS", "WEAK_HIT") and game.resources.momentum > 0:
        potential_burn = can_burn_momentum(game, roll)
        if potential_burn:
            burn_info = {
                "roll": roll,
                "new_result": potential_burn,
                "cost": game.resources.momentum,
                "brain": brain,
                "player_words": player_message,
                "scene_setup": scene_setup,
                "pre_snapshot": game.last_turn_snapshot,
            }

    # Engine resolves position and effect (step 2) — deterministic from game state
    position = resolve_position(game, brain)
    effect = resolve_effect(game, brain, position)

    consequences, clock_events = apply_consequences(game, roll, brain, position, effect)
    npc_agency, agency_clock_events = check_npc_agency(game)

    # Track gather_information successes for information gating (step 6)
    if brain.move == "gather_information" and roll.result in ("STRONG_HIT", "WEAK_HIT") and brain.target_npc:
        gather_target = find_npc(game, brain.target_npc)
        if gather_target:
            gather_target.gather_count += 1

    from ..mechanics import generate_consequence_sentences

    consequence_sentences = generate_consequence_sentences(consequences, clock_events, game, brain)

    prompt = build_action_prompt(
        game,
        brain,
        roll,
        consequences,
        clock_events,
        npc_agency,
        player_words=player_message,
        scene_setup=scene_setup,
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
        config=config,
        position=position,
        effect=effect,
        consequence_sentences=consequence_sentences,
        random_events=pending_random_events,
    )
    raw = call_narrator(provider, prompt, game, config)
    narration = parse_narrator_response(game, raw)

    from ..ai.validator import validate_and_retry

    narration, val_report = validate_and_retry(
        provider,
        narration,
        prompt,
        roll.result,
        game,
        player_words=player_message,
        consequences=consequences,
        config=config,
        consequence_sentences=consequence_sentences,
    )

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.narration = narration

    _, director_ctx = _finalize_scene(
        provider,
        game,
        narration,
        brain,
        player_message,
        _scene_present_ids,
        pending_revs,
        scene_setup,
        npc_activation_debug,
        log_entry={
            "scene": nar.scene_count,
            "summary": (brain.player_intent or player_message),
            "move": brain.move,
            "result": roll.result,
            "consequences": consequences,
            "clock_events": clock_events,
            "position": position,
            "effect": effect,
            "scene_type": scene_setup.scene_type,
            "npc_activation": npc_activation_debug,
            "validator": val_report,
            "_pacing_type": "action",
        },
        prompt_summary=f"Action ({roll.result}): {(brain.player_intent or player_message)[:80]}",
        roll_result_str=roll.result,
        config=config,
        agency_clock_events=agency_clock_events,
        roll=roll,
        consequences=consequences,
        position=position,
        effect=effect,
    )
    return game, narration, roll, burn_info, director_ctx


def _check_story_completion(game: GameState) -> None:
    """Check if the story has reached its natural end point."""
    bp = game.narrative.story_blueprint
    if not bp or not bp.acts:
        return
    if bp.story_complete:
        return
    acts = bp.acts
    if not acts:
        return
    final_end = (acts[-1].scene_range or default_scene_range())[1]
    sc = game.narrative.scene_count

    triggered = set(bp.triggered_transitions)
    penultimate_id = f"act_{len(acts) - 2}"
    final_act_entered = len(acts) >= 2 and penultimate_id in triggered

    if final_act_entered and sc >= final_end:
        bp.story_complete = True
        log(f"[Story] Complete: final act entered ('{penultimate_id}' triggered) + scene {sc} >= range end {final_end}")
        return

    if sc >= final_end and not final_act_entered:
        for i, act in enumerate(acts[:-1]):
            act_id = f"act_{i}"
            if act_id not in bp.triggered_transitions:
                act_range = act.scene_range or default_scene_range()
                if sc > act_range[1]:
                    bp.triggered_transitions.append(act_id)
                    log(f"[Story] Back-filled transition: {act_id} (scene {sc} > range end {act_range[1]})")
        triggered = set(bp.triggered_transitions)
        if len(acts) >= 2 and penultimate_id in triggered:
            bp.story_complete = True
            log(
                f"[Story] Complete (back-fill): '{penultimate_id}' triggered after "
                f"scene-range back-fill, scene {sc} >= {final_end}"
            )
            return

    if sc >= final_end + 5:
        bp.story_complete = True
        log(f"[Story] Complete (fallback): scene {sc} >= final_end+5 ({final_end + 5})")
