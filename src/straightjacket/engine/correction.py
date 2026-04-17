#!/usr/bin/env python3
"""Straightjacket correction flow: undo/redo turns, state patching."""

import json
import re
import uuid

from ..i18n import t
from .ai.brain import call_brain
from .ai.provider_base import AIProvider, create_with_retry
from .ai.schemas import CORRECTION_OUTPUT_SCHEMA
from .config_loader import model_for_role, sampling_params
from .datasworn.moves import get_moves
from .director import should_call_director
from .engine_loader import eng
from .game.finalization import apply_post_narration, narrate_scene, resolve_action_consequences
from .logging_util import log
from .mechanics import (
    apply_brain_location_time,
    check_npc_agency,
    generate_consequence_sentences,
    record_scene_intensity,
    resolve_effect,
    resolve_position,
    roll_action,
    update_chaos_factor,
)
from .models import (
    NPC_STATUSES,
    BrainResult,
    EngineConfig,
    GameState,
    NarrationEntry,
    NpcData,
    SceneLogEntry,
    TurnSnapshot,
)
from .npc import activate_npcs_for_prompt, consolidate_memory, find_npc
from .npc.lifecycle import sanitize_aliases
from .prompt_blocks import get_narration_lang
from .prompt_builders import build_action_prompt, build_dialog_prompt
from .prompt_loader import get_prompt


def call_correction_brain(
    provider: AIProvider, game: GameState, correction_text: str, config: EngineConfig | None = None
) -> dict:
    """Analyse a ## correction request against the last turn snapshot."""
    snap = game.last_turn_snapshot
    if not snap:
        raise ValueError("No last_turn_snapshot available for correction")

    _cfg = config or EngineConfig()
    lang = get_narration_lang(_cfg)

    def _npc_line(n: NpcData) -> str:
        aliases = f" aliases:{','.join(n.aliases)}" if n.aliases else ""
        return f'id:{n.id} name:"{n.name}"{aliases} disposition:{n.disposition} desc:"{n.description[:120]}"'

    npc_lines = "\n".join(_npc_line(n) for n in game.npcs) or "(none)"

    brain = snap.brain or BrainResult()
    roll = snap.roll
    roll_summary = (
        f"{roll.result} ({roll.move}, {roll.stat_name}={roll.stat_value}, "
        f"d1={roll.d1}+d2={roll.d2} vs c1={roll.c1}/c2={roll.c2})"
        if roll
        else "dialog (no roll)"
    )

    system = get_prompt("correction_brain", lang=lang)
    w = game.world

    user_msg = f"""## correction from player: {correction_text}

<last_turn>
player_input: {(snap.player_input or "")}
brain_interpretation: move={brain.move} stat={brain.stat} intent={brain.player_intent[:200]}
roll: {roll_summary}
narration (first 600 chars): {(snap.narration or "")[:600]}
</last_turn>

<current_state>
location: {w.current_location}
scene_context: {w.current_scene_context[:200]}
time: {w.time_of_day}
npcs:
{npc_lines}
</current_state>"""

    log(f"[Correction] Analysing: {correction_text[:100]}")
    try:
        response = create_with_retry(
            provider,
            model=model_for_role("correction"),
            system=system,
            messages=[{"role": "user", "content": user_msg}],
            json_schema=CORRECTION_OUTPUT_SCHEMA,
            **sampling_params("correction"),
        )
        result = json.loads(response.content)
        log(
            f"[Correction] source={result['correction_source']} "
            f"reroll={result['reroll_needed']} ops={len(result['state_ops'])}"
        )
        return result
    except Exception as e:
        # Intentional graceful degradation — see AI-CALL SUPPRESSION POLICY in provider_base.py.
        log(f"[Correction] Brain failed ({type(e).__name__}: {e}), falling back to no-op state_error", level="warning")
        return {
            "correction_source": "state_error",
            "corrected_input": "",
            "reroll_needed": False,
            "corrected_stat": "none",
            "narrator_guidance": correction_text,
            "director_useful": False,
            "state_ops": [],
        }


def _apply_correction_ops(game: GameState, ops: list) -> None:
    """Apply the atomic state_ops returned by call_correction_brain."""
    for op_dict in ops:
        op = op_dict.get("op")

        if op == "npc_edit":
            npc = find_npc(game, op_dict.get("npc_id", ""))
            if npc and op_dict.get("fields"):
                allowed = {"name", "description", "disposition", "agenda", "instinct", "aliases", "status"}
                edits = {k: v for k, v in op_dict["fields"].items() if k in allowed and v is not None}

                # Rename detection: if name is changing, engine owns alias bookkeeping.
                # Pop aliases from edits so the model can't overwrite our list.
                old_name = npc.name
                is_rename = "name" in edits and edits["name"] != old_name
                if is_rename:
                    edits.pop("aliases", None)

                # Status validation
                if "status" in edits and edits["status"] not in NPC_STATUSES:
                    edits.pop("status")

                for k, v in edits.items():
                    setattr(npc, k, v)

                # After rename: move old name to aliases, strip new name from aliases
                if is_rename and old_name:
                    if old_name not in npc.aliases:
                        npc.aliases.append(old_name)
                    new_lower = edits["name"].lower()
                    npc.aliases = [a for a in npc.aliases if a.lower() != new_lower]

                # Clean up death annotation if status set to deceased
                if edits.get("status") == "deceased" and npc.description:
                    npc.description = re.sub(
                        r"\s*\[?(VERSTORBEN|DECEASED|TOT|DEAD)\]?\s*", "", npc.description, flags=re.IGNORECASE
                    ).strip()

                if edits:
                    log(
                        f"[Correction] npc_edit: {npc.name} fields={list(edits.keys())}"
                        f"{' (RENAME)' if is_rename else ''}"
                    )

        elif op == "npc_split":
            existing = find_npc(game, op_dict.get("npc_id", ""))
            if existing:
                new_name = op_dict.get("split_name") or "Unknown"
                new_desc = op_dict.get("split_description") or ""
                new_id = f"npc_{uuid.uuid4().hex[:8]}"
                new_npc = NpcData(
                    id=new_id,
                    name=new_name,
                    description=new_desc,
                )
                game.npcs.append(new_npc)
                log(f"[Correction] npc_split: '{existing.name}' → also '{new_name}' ({new_id})")

        elif op == "npc_merge":
            target = find_npc(game, op_dict.get("npc_id", ""))
            source = find_npc(game, op_dict.get("merge_source_id", ""))
            if target and source and target is not source:
                target.memory.extend(source.memory)
                for alias in source.aliases:
                    if alias not in target.aliases:
                        target.aliases.append(alias)
                if source.name not in target.aliases:
                    target.aliases.append(source.name)
                game.npcs = [n for n in game.npcs if n.id != source.id]
                sanitize_aliases(target)
                consolidate_memory(target)
                log(f"[Correction] npc_merge: '{source.name}' absorbed into '{target.name}'")

        elif op == "location_edit":
            if op_dict.get("value"):
                game.world.current_location = op_dict["value"]
                log(f"[Correction] location → {game.world.current_location}")

        elif op == "scene_context":
            if op_dict.get("value"):
                game.world.current_scene_context = op_dict["value"]
                log("[Correction] scene_context updated")

        elif op == "time_edit":
            if op_dict.get("value"):
                game.world.time_of_day = op_dict["value"]
                log(f"[Correction] time_of_day → {game.world.time_of_day}")

        elif op == "backstory_append":
            if op_dict.get("value"):
                sep = "\n" if game.backstory else ""
                game.backstory += sep + op_dict["value"]
                log("[Correction] backstory appended")


def _restore_from_snapshot(game: GameState, snap: "TurnSnapshot") -> None:
    """Fully restore all turn-mutable GameState fields from a snapshot."""
    game.restore(snap)
    log("[Correction] State fully restored from snapshot")


def process_correction(
    provider: AIProvider, game: GameState, correction_text: str, config: EngineConfig | None = None
) -> tuple[GameState, str, dict | None]:
    """Handle a ## correction request."""
    snap = game.last_turn_snapshot
    if not snap:
        log("[Correction] No snapshot available — cannot correct", level="warning")
        return game, t("correction.no_snapshot"), None

    _cfg = config or EngineConfig()
    nar = game.narrative
    consequences: list[str] = []

    # Step 1: Analyse the correction
    analysis = call_correction_brain(provider, game, correction_text, _cfg)
    source = analysis["correction_source"]

    # Step 2a: input_misread → full state restore, then re-run Brain + optional Roll
    if source == "input_misread":
        _restore_from_snapshot(game, snap)
        corrected_input = analysis.get("corrected_input") or (snap.player_input or "")

        brain = call_brain(provider, game, corrected_input, _cfg)
        apply_brain_location_time(game, brain)

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
                from .game.finalization import apply_progress_and_legacy
                from .game.tracks import find_progress_track

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
                config=_cfg,
                activated_npcs=activated_npcs,
                mentioned_npcs=mentioned_npcs,
                position=position,
                effect=effect,
                consequence_sentences=consequence_sentences,
            )
        else:
            roll = None
            nar.scene_count += 1
            activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, corrected_input)
            prompt = build_dialog_prompt(
                game,
                brain,
                player_words=corrected_input,
                activated_npcs=activated_npcs,
                mentioned_npcs=mentioned_npcs,
                config=_cfg,
            )

    # Step 2b: state_error → patch state in-place, no re-roll
    else:
        roll = snap.roll
        brain = snap.brain or BrainResult()
        _apply_correction_ops(game, analysis.get("state_ops", []))
        activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, (snap.player_input or ""))
        _last_entry = nar.session_log[-1] if nar.session_log else None
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
                config=_cfg,
                activated_npcs=activated_npcs,
                mentioned_npcs=mentioned_npcs,
                consequence_sentences=consequence_sentences,
            )
        else:
            prompt = build_dialog_prompt(
                game,
                brain,
                player_words=(snap.player_input or ""),
                activated_npcs=activated_npcs,
                mentioned_npcs=mentioned_npcs,
                config=_cfg,
            )

    # Step 3: Narrator rewrite
    correction_tag = (
        f"\n<correction_context>{analysis['narrator_guidance']}</correction_context>"
        f"\n<correction_instruction>Rewrite the scene incorporating the correction above. "
        f"Same events and outcome — only adjust what the correction requires.</correction_instruction>"
    )
    prompt = prompt + correction_tag

    narration, _ = narrate_scene(provider, game, prompt, config=_cfg)

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.narration = narration
        if source == "input_misread":
            game.last_turn_snapshot.brain = brain
            game.last_turn_snapshot.roll = roll

    # Step 4: Engine-side state mutations
    _scene_present_ids = {n.id for n in activated_npcs} | {n.id for n in mentioned_npcs}
    metadata = apply_post_narration(
        provider,
        game,
        narration,
        brain,
        roll,
        _scene_present_ids,
        [n.name for n in game.npcs if n.id in _scene_present_ids],
        config=_cfg,
        consequences=consequences if roll else [],
    )

    # Step 5: Update session_log / narration_history
    intent = (brain.player_intent or snap.player_input or "")[:80]
    narration_entry = NarrationEntry(
        scene=nar.scene_count,
        prompt_summary=f"[corrected] {intent}",
        narration=narration[: eng().pacing.max_narration_chars],
    )

    if source == "input_misread":
        if roll:
            update_chaos_factor(game, roll.result)
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
                summary=f"[corrected] {intent}",
                move=brain.move,
                result=roll.result if roll else "dialog",
            )
        )
        if len(nar.session_log) > eng().pacing.max_session_log:
            nar.session_log = nar.session_log[-eng().pacing.max_session_log :]
    else:
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
                    summary=f"[corrected] {intent}",
                    move=brain.move,
                    result=roll.result if roll else "dialog",
                )
            )

    # Step 6: Director
    director_ctx = None
    if analysis.get("director_useful"):
        director_reason = should_call_director(
            game,
            roll_result=roll.result if roll else "dialog",
            chaos_used=False,
            new_npcs_found=bool(metadata.get("new_npcs")),
            revelation_used=False,
        )
        if director_reason:
            director_ctx = {"narration": narration, "config": _cfg}
            log(f"[Correction] Director queued (reason: {director_reason})")
            bp = game.narrative.story_blueprint
            if director_reason.startswith("phase:") and bp is not None:
                bp.triggered_director_phases.append(director_reason[len("phase:") :])

    log(f"[Correction] Complete: source={source}, rewrite done")

    # Sync corrected state to database
    from .db import sync as _db_sync

    _db_sync(game)

    return game, narration, director_ctx
