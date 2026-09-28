from __future__ import annotations

from typing import Any
from ...i18n import t
from ..ai.provider_base import AIProvider
from ..db import sync as _db_sync
from ..director import should_call_director
from ..engine_loader import eng
from ..game import BurnOffer, replay_turn
from ..game.finalization import apply_post_narration, narrate_scene
from ..logging_util import log
from ..mechanics import check_npc_agency, facts_of_this_place, generate_consequence_sentences
from ..models import (
    BrainResult,
    EngineConfig,
    GameState,
    NarrationEntry,
    ResolvedFact,
    RollResult,
    SceneLogEntry,
    TurnSnapshot,
)
from ..npc import activate_npcs_for_prompt
from ..prompt_action import build_action_prompt
from ..prompt_dialog import build_dialog_prompt
from ..prompt_loader import get_prompt
from ..xml_utils import xe as _xe
from .analysis import call_correction_brain
from .ops import _apply_correction_ops


def _handle_state_error(
    game: GameState, snap: TurnSnapshot, analysis: dict[str, Any]
) -> tuple[BrainResult, RollResult | None, str, list[str], list[ResolvedFact]]:
    roll = snap.roll

    brain = snap.brain or BrainResult(type="none", move="none", stat="none")
    _apply_correction_ops(game, analysis["state_ops"])
    facts = facts_of_this_place(game, snap.facts)

    activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, snap.player_input)
    _last_entry = game.narrative.session_log[-1] if game.narrative.session_log else None

    if roll:
        consequences = _last_entry.consequences if _last_entry else []
        clock_events = _last_entry.clock_events if _last_entry else []
        npc_agency, _, _ = check_npc_agency(game)
        consequence_sentences = generate_consequence_sentences(consequences, clock_events, game, brain)
        prompt = build_action_prompt(
            game,
            brain,
            roll,
            consequences,
            npc_agency,
            player_words=snap.player_input,
            activated_npcs=activated_npcs,
            mentioned_npcs=mentioned_npcs,
            consequence_sentences=consequence_sentences,
            facts=facts,
        )
        return brain, roll, prompt, consequences, facts

    prompt = build_dialog_prompt(
        game,
        brain,
        player_words=snap.player_input,
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
        oracle_answer=_last_entry.oracle_answer if _last_entry else "",
        facts=facts,
    )
    return brain, None, prompt, [], facts


def _update_state_error_logs(
    game: GameState, brain: BrainResult, roll: RollResult | None, narration: str, intent: str
) -> None:
    nar = game.narrative
    narration_entry = NarrationEntry(
        scene=nar.scene_count,
        prompt_summary=f"[corrected] {intent}",
        narration=narration[: eng().pacing.max_narration_chars],
    )
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
                result=roll.result if roll else "dialog",
            )
        )


def _maybe_queue_director(
    game: GameState,
    analysis: dict[str, Any],
    roll: RollResult | None,
    narration: str,
    metadata: dict[str, Any],
    _cfg: EngineConfig,
) -> dict[str, Any] | None:
    if not analysis["director_useful"]:
        return None
    director_reason = should_call_director(
        game,
        roll_result=roll.result if roll else "dialog",
        chaos_used=False,
        new_npcs_found=bool(metadata["new_npcs"]),
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
) -> tuple[GameState, str, BurnOffer | None, dict[str, Any] | None]:
    snap = game.last_turn_snapshot
    if not snap:
        log("[Correction] No snapshot available — cannot correct", level="warning")
        return game, t("correction.no_snapshot"), None, None

    _cfg = config or EngineConfig()

    analysis = call_correction_brain(provider, game, correction_text, _cfg)
    note = (
        f"<correction_context>{_xe(analysis['narrator_guidance'])}</correction_context>\n"
        f"{get_prompt('block_correction_instruction', role='narrator')}"
    )

    if analysis["correction_source"] == "input_misread":
        corrected_input = analysis["corrected_input"] or snap.player_input
        narration, burn_offer, director_ctx = replay_turn(provider, game, corrected_input, _cfg, note)
        log("[Correction] Complete: source=input_misread, turn replayed")
        return game, narration, burn_offer, director_ctx

    brain, roll, prompt, consequences, facts = _handle_state_error(game, snap, analysis)
    narration = narrate_scene(provider, game, f"{prompt}\n{note}", config=_cfg)
    snap.narration = narration
    snap.facts = list(facts)

    activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, snap.player_input)
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

    intent = (brain.player_intent or snap.player_input)[: eng().truncations.log_medium]
    _update_state_error_logs(game, brain, roll, narration, intent)

    director_ctx = _maybe_queue_director(game, analysis, roll, narration, metadata, _cfg)

    log("[Correction] Complete: source=state_error, rewrite done")
    _db_sync(game)
    return game, narration, None, director_ctx
