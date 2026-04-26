"""Correction orchestration: snapshot restore, re-roll, re-narration, post-narration state."""

from __future__ import annotations

from ...i18n import t
from ..ai.brain import BrainResult, call_brain
from ..ai.provider_base import AIProvider
from ..datasworn.moves import get_moves
from ..db import sync as _db_sync
from ..director import should_call_director
from ..engine_loader import eng
from ..game.finalization import (
    apply_post_narration,
    apply_progress_and_legacy,
    narrate_scene,
    resolve_action_consequences,
)
from ..game.tracks import find_progress_track
from ..logging_util import log
from ..mechanics import (
    apply_brain_location_time,
    check_npc_agency,
    generate_consequence_sentences,
    record_scene_intensity,
    resolve_effect,
    resolve_position,
    roll_action,
    update_chaos_factor,
)
from ..models import EngineConfig, GameState, NarrationEntry, SceneLogEntry, TurnSnapshot
from ..npc import activate_npcs_for_prompt
from ..prompt_action import build_action_prompt
from ..prompt_dialog import build_dialog_prompt
from ..prompt_loader import get_prompt
from .analysis import call_correction_brain
from .ops import _apply_correction_ops


def _restore_from_snapshot(game: GameState, snap: TurnSnapshot) -> None:
    """Fully restore all turn-mutable GameState fields from a snapshot."""
    game.restore(snap)
    log("[Correction] State fully restored from snapshot")


def _handle_input_misread(
    provider: AIProvider, game: GameState, snap: TurnSnapshot, analysis: dict, _cfg: EngineConfig
) -> tuple[BrainResult, object, str, list[str]]:
    """Step 2a: input_misread → restore state, re-run Brain, optionally re-roll,
    and build the corrected prompt. Returns (brain, roll_or_none, prompt, consequences).
    """
    _restore_from_snapshot(game, snap)
    corrected_input = analysis.get("corrected_input") or (snap.player_input or "")

    brain = call_brain(provider, game, corrected_input, _cfg)
    apply_brain_location_time(game, brain)

    nar = game.narrative
    consequences: list[str] = []

    if analysis.get("reroll_needed") and brain.stat != "none":
        nar.scene_count += 1
        stat_name = brain.stat
        roll = roll_action(stat_name, game.get_stat(stat_name), brain.move)
        log(f"[Correction] Re-rolled: {roll.result} ({stat_name})")
        position = resolve_position(game, brain)
        effect = resolve_effect(game, brain, position)

        action = resolve_action_consequences(game, brain, roll, position)
        consequences = action.consequences
        clock_events = action.clock_events

        # Re-apply progress and legacy marks from the re-resolved outcome
        # (snapshot restored the original state, so we need to re-consume)
        if action.outcome:
            ds_moves = get_moves(game.setting_id) if game.setting_id else {}
            ds_move = ds_moves.get(brain.move)
            source_category = ds_move.track_category if ds_move else "vow"
            src_track = find_progress_track(game, source_category, target_track=brain.target_track)
            source_rank = src_track.rank if src_track else "dangerous"
            apply_progress_and_legacy(game, action.outcome, brain, source_category, source_rank)

        npc_agency, _ = check_npc_agency(game)
        activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, corrected_input)

        consequence_sentences = generate_consequence_sentences(consequences, clock_events, game, brain)

        prompt = build_action_prompt(
            game,
            brain,
            roll,
            consequences,
            clock_events,
            npc_agency,
            player_words=corrected_input,
            activated_npcs=activated_npcs,
            mentioned_npcs=mentioned_npcs,
            position=position,
            effect=effect,
            consequence_sentences=consequence_sentences,
        )
        return brain, roll, prompt, consequences

    # Dialog path: no reroll
    nar.scene_count += 1
    activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, corrected_input)
    prompt = build_dialog_prompt(
        game,
        brain,
        player_words=corrected_input,
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
    )
    return brain, None, prompt, consequences


def _handle_state_error(
    game: GameState, snap: TurnSnapshot, analysis: dict
) -> tuple[BrainResult, object, str, list[str]]:
    """Step 2b: state_error → patch state in-place, no re-roll, re-narrate with
    the same brain+roll context the previous turn had. Returns (brain, roll_or_none,
    prompt, consequences).
    """
    roll = snap.roll
    # Sentinel brain when the snapshot has none — the field is optional on TurnSnapshot
    # but resolve_* and prompt builders expect a real BrainResult.
    brain = snap.brain or BrainResult(type="none", move="none", stat="none")
    _apply_correction_ops(game, analysis.get("state_ops", []))

    activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, (snap.player_input or ""))
    _last_entry = game.narrative.session_log[-1] if game.narrative.session_log else None

    if roll:
        consequences = _last_entry.consequences if _last_entry else []
        clock_events = _last_entry.clock_events if _last_entry else []
        npc_agency, _ = check_npc_agency(game)
        consequence_sentences = generate_consequence_sentences(consequences, clock_events, game, brain)
        prompt = build_action_prompt(
            game,
            brain,
            roll,
            consequences,
            clock_events,
            npc_agency,
            player_words=(snap.player_input or ""),
            activated_npcs=activated_npcs,
            mentioned_npcs=mentioned_npcs,
            consequence_sentences=consequence_sentences,
        )
        return brain, roll, prompt, consequences

    prompt = build_dialog_prompt(
        game,
        brain,
        player_words=(snap.player_input or ""),
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
    )
    return brain, None, prompt, []


def _update_correction_logs(
    game: GameState, brain: BrainResult, roll: object, narration: str, intent: str, source: str
) -> None:
    """Step 5: update session_log and narration_history. input_misread appends
    a fresh entry; state_error overwrites the last entry in place.
    """
    nar = game.narrative
    narration_entry = NarrationEntry(
        scene=nar.scene_count,
        prompt_summary=f"[corrected] {intent}",
        narration=narration[: eng().pacing.max_narration_chars],
    )

    if source == "input_misread":
        if roll:
            update_chaos_factor(game, roll.result)  # type: ignore[attr-defined]
            scene_type = "action"
        else:
            scene_type = "breather"
        record_scene_intensity(game, scene_type)
        nar.narration_history.append(narration_entry)
        if len(nar.narration_history) > eng().pacing.max_narration_history:
            nar.narration_history = nar.narration_history[-eng().pacing.max_narration_history :]
        nar.session_log.append(
            SceneLogEntry(
                scene=nar.scene_count,
                scene_type="expected",
                summary=f"[corrected] {intent}",
                move=brain.move,
                result=roll.result if roll else "dialog",  # type: ignore[attr-defined]
            )
        )
        if len(nar.session_log) > eng().pacing.max_session_log:
            nar.session_log = nar.session_log[-eng().pacing.max_session_log :]
        return

    # state_error: overwrite last entry
    if nar.narration_history:
        nar.narration_history[-1] = narration_entry
    else:
        nar.narration_history.append(narration_entry)
    if nar.session_log:
        nar.session_log[-1].summary = f"[corrected] {intent}"
    else:
        nar.session_log.append(
            SceneLogEntry(
                scene=nar.scene_count,
                scene_type="expected",
                summary=f"[corrected] {intent}",
                move=brain.move,
                result=roll.result if roll else "dialog",  # type: ignore[attr-defined]
            )
        )


def _maybe_queue_director(
    game: GameState, analysis: dict, roll: object, narration: str, metadata: dict, _cfg: EngineConfig
) -> dict | None:
    """Step 6: if the correction analysis flagged director-useful and the usual
    should_call_director triggers fire, return the director context to be run
    by the caller; else return None.
    """
    if not analysis.get("director_useful"):
        return None
    director_reason = should_call_director(
        game,
        roll_result=roll.result if roll else "dialog",  # type: ignore[attr-defined]
        chaos_used=False,
        new_npcs_found=bool(metadata.get("new_npcs")),
        revelation_used=False,
    )
    if not director_reason:
        return None
    log(f"[Correction] Director queued (reason: {director_reason})")
    bp = game.narrative.story_blueprint
    if director_reason.startswith("phase:") and bp is not None:
        bp.triggered_director_phases.append(director_reason[len("phase:") :])
    return {"narration": narration, "config": _cfg}


def process_correction(
    provider: AIProvider, game: GameState, correction_text: str, config: EngineConfig | None = None
) -> tuple[GameState, str, dict | None]:
    """Handle a ## correction request. Six steps, each delegated to a helper:
    1. Analyse the correction (input_misread vs state_error).
    2. Rebuild brain/roll/prompt via the path-specific handler.
    3. Narrator rewrite with correction tag appended.
    4. Engine-side post-narration state mutations.
    5. Update session_log / narration_history per source type.
    6. Optionally queue the director.
    """
    snap = game.last_turn_snapshot
    if not snap:
        log("[Correction] No snapshot available — cannot correct", level="warning")
        return game, t("correction.no_snapshot"), None

    _cfg = config or EngineConfig()

    # Step 1: Analyse
    analysis = call_correction_brain(provider, game, correction_text, _cfg)
    source = analysis["correction_source"]

    # Step 2: Dispatch to path-specific handler
    if source == "input_misread":
        brain, roll, prompt, consequences = _handle_input_misread(provider, game, snap, analysis, _cfg)
    else:
        brain, roll, prompt, consequences = _handle_state_error(game, snap, analysis)

    # Step 3: Narrator rewrite
    correction_tag = (
        f"\n<correction_context>{analysis['narrator_guidance']}</correction_context>"
        f"\n{get_prompt('block_correction_instruction', role='narrator')}"
    )
    prompt = prompt + correction_tag
    narration, _ = narrate_scene(provider, game, prompt, config=_cfg)

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.narration = narration
        if source == "input_misread":
            game.last_turn_snapshot.brain = brain
            game.last_turn_snapshot.roll = roll  # type: ignore[assignment]

    # Step 4: Post-narration state mutations
    activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, (snap.player_input or ""))
    _scene_present_ids = {n.id for n in activated_npcs} | {n.id for n in mentioned_npcs}
    metadata = apply_post_narration(
        provider,
        game,
        narration,
        brain,
        roll,  # type: ignore[arg-type]
        _scene_present_ids,
        [n.name for n in game.npcs if n.id in _scene_present_ids],
        config=_cfg,
        consequences=consequences if roll else [],
    )

    # Step 5: Update logs
    intent = (brain.player_intent or snap.player_input or "")[: eng().truncations.log_medium]
    _update_correction_logs(game, brain, roll, narration, intent, source)

    # Step 6: Director
    director_ctx = _maybe_queue_director(game, analysis, roll, narration, metadata, _cfg)

    log(f"[Correction] Complete: source={source}, rewrite done")
    _db_sync(game)
    return game, narration, director_ctx
