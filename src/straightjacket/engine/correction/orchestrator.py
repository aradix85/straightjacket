from __future__ import annotations

from typing import Any

from ...i18n import t
from ..ai.provider_base import AIProvider
from ..director import should_call_director
from ..engine_loader import eng
from ..game import BurnOffer, DirectorCall, apply_post_narration, narrate_scene, replay_turn
from ..gamemaster.config import gm
from ..gamemaster.facts import facts_of_this_place, overrule_facts_by_hit, settle_facts_by_miss
from ..gamemaster.npc.activation import activate_npcs_for_prompt
from ..gamemaster.npc.matching import present_in_narration
from ..gamemaster.questions import answers, outcome_of
from ..logging_util import log
from ..models import (
    BrainResult,
    GameState,
    NarrationEntry,
    NpcData,
    ResolvedFact,
    SceneSetup,
    TurnSnapshot,
)
from ..prompt_action import build_action_prompt
from ..prompt_dialog import build_dialog_prompt
from ..prompt_loader import get_prompt
from ..ruleset.consequences import consequence_texts, generate_consequence_sentences
from ..xml_utils import xe as _xe
from .analysis import call_correction_brain
from .ops import apply_correction_ops


def _rewrite_prompt(
    game: GameState,
    snap: TurnSnapshot,
    brain: BrainResult,
    scene_setup: SceneSetup,
    activated_npcs: list[NpcData],
    mentioned_npcs: list[NpcData],
) -> tuple[str, list[ResolvedFact]]:
    roll = snap.roll
    facts = facts_of_this_place(game, snap.facts)
    last_entry = game.narrative.session_log[-1]
    consequences = last_entry.consequences

    if roll is None:
        prompt = build_dialog_prompt(
            game,
            brain,
            player_words=snap.player_input,
            scene_setup=scene_setup,
            activated_npcs=activated_npcs,
            mentioned_npcs=mentioned_npcs,
            result=last_entry.result,
            oracle_answer=last_entry.oracle_answer,
            random_events=snap.random_events,
            threat_events=snap.threat_events,
            consequence_texts=consequence_texts(consequences, game, brain),
            clock_fill_results=snap.clock_fill_results,
            npc_agency=snap.npc_agency,
            facts=facts,
            revelation=snap.revelation,
        )
        return prompt, facts

    outcome = answers().outcome(roll.result)
    facts = overrule_facts_by_hit(game, facts, outcome)
    facts = settle_facts_by_miss(game, facts, brain.move, outcome)
    told_clock_events = [e for e in last_entry.clock_events if not e.autonomous]
    consequence_sentences = generate_consequence_sentences(consequences, told_clock_events, game, brain)
    prompt = build_action_prompt(
        game,
        brain,
        roll,
        consequences,
        snap.npc_agency,
        consequence_sentences=consequence_sentences,
        player_words=snap.player_input,
        scene_setup=scene_setup,
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
        position=last_entry.position,
        effect=last_entry.effect,
        random_events=snap.random_events,
        threat_events=snap.threat_events,
        clock_fill_results=snap.clock_fill_results,
        facts=facts,
        revelation=snap.revelation,
    )
    return prompt, facts


def _update_state_error_logs(game: GameState, narration: str, intent: str) -> None:
    nar = game.narrative
    summary = get_prompt("history_corrected", intent=intent)
    nar.narration_history[-1] = NarrationEntry(
        scene=nar.scene_count,
        prompt_summary=summary,
        narration=narration[: gm().pacing.max_narration_chars],
    )
    nar.session_log[-1].summary = summary


def _maybe_queue_director(
    game: GameState,
    analysis: dict[str, Any],
    narration: str,
    metadata: dict[str, Any],
) -> DirectorCall | None:
    if not analysis["director_useful"]:
        return None
    director_reason = should_call_director(
        game,
        roll_result=game.narrative.session_log[-1].result,
        chaos_used=False,
        new_npcs_found=bool(metadata["new_npcs"]),
        revelation_landed=False,
    )
    if not director_reason:
        return None
    log(f"[Correction] Director queued (reason: {director_reason})")
    return DirectorCall(narration=narration)


def process_correction(
    provider: AIProvider, game: GameState, correction_text: str
) -> tuple[str, BurnOffer | None, DirectorCall | None]:
    snap = game.last_turn_snapshot
    if snap is None:
        log("[Correction] No snapshot available — cannot correct", level="warning")
        return t("correction.no_snapshot"), None, None
    brain, last_narration, scene_setup = snap.brain, snap.narration, snap.scene_setup
    if brain is None or last_narration is None or scene_setup is None:
        raise ValueError("The last turn's snapshot holds no Brain result, narration, or scene setup")

    analysis = call_correction_brain(provider, game, correction_text, snap, brain, last_narration)
    note = (
        get_prompt("block_correction_context", guidance=_xe(analysis["narrator_guidance"]))
        + "\n"
        + get_prompt("block_correction_instruction")
    )

    if analysis["correction_source"] == "input_misread":
        corrected_input = analysis["corrected_input"] or snap.player_input
        narration, burn_offer, director_ctx = replay_turn(provider, game, corrected_input, note)
        log("[Correction] Complete: source=input_misread, turn replayed")
        return narration, burn_offer, director_ctx

    apply_correction_ops(game, analysis["state_ops"])
    activated_npcs, mentioned_npcs = activate_npcs_for_prompt(game, brain, snap.player_input)
    prompt, facts = _rewrite_prompt(game, snap, brain, scene_setup, activated_npcs, mentioned_npcs)
    narration = narrate_scene(provider, game, f"{prompt}\n{note}")
    snap.narration = narration
    snap.facts = list(facts)

    metadata = apply_post_narration(
        provider,
        game,
        narration,
        brain,
        outcome_of(game.narrative.session_log[-1].result),
        present_in_narration(
            game, {n.id for n in activated_npcs} | {n.id for n in mentioned_npcs}, brain.target_npc, narration
        ),
        consequences=game.narrative.session_log[-1].consequences,
    )

    _update_state_error_logs(
        game, narration, (brain.player_intent or snap.player_input)[: eng().truncations.log_medium]
    )

    director_ctx = _maybe_queue_director(game, analysis, narration, metadata)

    log("[Correction] Complete: source=state_error, rewrite done")
    return narration, None, director_ctx
