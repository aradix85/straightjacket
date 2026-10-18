from __future__ import annotations

from typing import Any
from ...i18n import t
from ..ai.provider_base import AIProvider
from ..director import should_call_director
from ..engine_loader import eng
from ..game import BurnOffer, DirectorCall, replay_turn
from ..game.finalization import apply_post_narration, narrate_scene
from ..logging_util import log
from ..mechanics import (
    check_npc_agency,
    facts_of_this_place,
    generate_consequence_sentences,
    overrule_facts_by_hit,
    settle_facts_by_miss,
)
from ..models import (
    BrainResult,
    GameState,
    NarrationEntry,
    NpcData,
    ResolvedFact,
    RollResult,
    TurnSnapshot,
)
from ..npc import activate_npcs_for_prompt
from ..prompt_action import build_action_prompt
from ..prompt_dialog import build_dialog_prompt
from ..prompt_loader import get_prompt
from ..xml_utils import xe as _xe
from .analysis import call_correction_brain
from .ops import apply_correction_ops


def _rewrite_prompt(
    game: GameState,
    snap: TurnSnapshot,
    brain: BrainResult,
    activated_npcs: list[NpcData],
    mentioned_npcs: list[NpcData],
) -> tuple[str, list[str], list[ResolvedFact]]:
    roll = snap.roll
    facts = facts_of_this_place(game, snap.facts)
    last_entry = game.narrative.session_log[-1]

    if roll is None:
        prompt = build_dialog_prompt(
            game,
            brain,
            player_words=snap.player_input,
            activated_npcs=activated_npcs,
            mentioned_npcs=mentioned_npcs,
            oracle_answer=last_entry.oracle_answer,
            facts=facts,
        )
        return prompt, [], facts

    facts = overrule_facts_by_hit(game, facts, roll.result)
    facts = settle_facts_by_miss(game, facts, brain.move, roll.result)
    consequences = last_entry.consequences
    npc_agency, _, _ = check_npc_agency(game)
    consequence_sentences = generate_consequence_sentences(consequences, last_entry.clock_events, game, brain)
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
    return prompt, consequences, facts


def _update_state_error_logs(game: GameState, narration: str, intent: str) -> None:
    nar = game.narrative
    summary = get_prompt("history_corrected", intent=intent)
    nar.narration_history[-1] = NarrationEntry(
        scene=nar.scene_count,
        prompt_summary=summary,
        narration=narration[: eng().pacing.max_narration_chars],
    )
    nar.session_log[-1].summary = summary


def _maybe_queue_director(
    game: GameState,
    analysis: dict[str, Any],
    roll: RollResult | None,
    narration: str,
    metadata: dict[str, Any],
) -> DirectorCall | None:
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
    return DirectorCall(narration=narration)


def process_correction(
    provider: AIProvider, game: GameState, correction_text: str
) -> tuple[GameState, str, BurnOffer | None, DirectorCall | None]:
    snap = game.last_turn_snapshot
    if snap is None:
        log("[Correction] No snapshot available — cannot correct", level="warning")
        return game, t("correction.no_snapshot"), None, None
    brain, last_narration = snap.brain, snap.narration
    if brain is None or last_narration is None:
        raise ValueError("The last turn's snapshot holds no Brain result or narration")

    analysis = call_correction_brain(provider, game, correction_text, snap, brain, last_narration)
    note = (
        f"<correction_context>{_xe(analysis['narrator_guidance'])}</correction_context>\n"
        f"{get_prompt('block_correction_instruction', role='narrator')}"
    )

    if analysis["correction_source"] == "input_misread":
        corrected_input = analysis["corrected_input"] or snap.player_input
        narration, burn_offer, director_ctx = replay_turn(provider, game, corrected_input, note)
        log("[Correction] Complete: source=input_misread, turn replayed")
        return game, narration, burn_offer, director_ctx

    roll = snap.roll
    apply_correction_ops(game, analysis["state_ops"])
    activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain, snap.player_input)
    prompt, consequences, facts = _rewrite_prompt(game, snap, brain, activated_npcs, mentioned_npcs)
    narration = narrate_scene(provider, game, f"{prompt}\n{note}")
    snap.narration = narration
    snap.facts = list(facts)

    scene_present_ids = {n.id for n in activated_npcs} | {n.id for n in mentioned_npcs}
    metadata = apply_post_narration(
        provider,
        game,
        narration,
        brain,
        roll,
        scene_present_ids,
        [n.name for n in game.npcs if n.id in scene_present_ids],
        consequences=consequences,
    )

    _update_state_error_logs(
        game, narration, (brain.player_intent or snap.player_input)[: eng().truncations.log_medium]
    )

    director_ctx = _maybe_queue_director(game, analysis, roll, narration, metadata)

    log("[Correction] Complete: source=state_error, rewrite done")
    return game, narration, None, director_ctx
