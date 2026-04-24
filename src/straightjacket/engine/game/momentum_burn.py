"""Momentum burn: re-narrate a scene after burning momentum to upgrade the result.

Extracted from the original correction.py flow. Shares snapshot/restore pattern with correction
but is a separate game flow with its own pipeline.
"""

from ..ai.provider_base import AIProvider
from ..datasworn.moves import get_moves
from ..db import sync as _db_sync
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    generate_consequence_sentences,
    resolve_effect,
    resolve_position,
    update_chaos_factor,
)
from ..mechanics.scene import SceneSetup
from ..models import (
    BrainResult,
    EngineConfig,
    GameState,
    NarrationEntry,
    RollResult,
    TurnSnapshot,
)
from ..npc import activate_npcs_for_prompt
from ..prompt_builders import build_action_prompt

from .finalization import apply_post_narration, apply_progress_and_legacy, narrate_scene, resolve_action_consequences
from .tracks import find_progress_track


def process_momentum_burn(
    provider: AIProvider,
    game: GameState,
    old_roll: RollResult,
    new_result: str,
    brain_data: BrainResult,
    player_words: str = "",
    config: EngineConfig | None = None,
    pre_snapshot: TurnSnapshot | None = None,
    scene_setup: SceneSetup | None = None,
) -> tuple[GameState, str]:
    """Re-narrate a scene after momentum burn upgrades the result."""
    if not pre_snapshot:
        log("[Burn] No pre_snapshot — cannot restore state", level="warning")
        return game, "(Momentum burn failed — no snapshot available.)"

    # Full state restore (NPCs revert to pre-turn state), then burn momentum
    game.restore(pre_snapshot)
    _e = eng()
    game.resources.reset_momentum(floor=_e.momentum.floor, reset_value=_e.momentum.start, max_cap=_e.momentum.max)

    upgraded = RollResult(
        old_roll.d1,
        old_roll.d2,
        old_roll.c1,
        old_roll.c2,
        old_roll.stat_name,
        old_roll.stat_value,
        old_roll.action_score,
        new_result,
        old_roll.move,
        old_roll.match,
    )

    position = resolve_position(game, brain_data)
    effect = resolve_effect(game, brain_data, position)

    action = resolve_action_consequences(game, brain_data, upgraded, position)
    consequences = action.consequences
    clock_events = action.clock_events

    # Re-apply progress and legacy marks from re-resolved outcome after upgrade
    if action.outcome:
        ds_moves = get_moves(game.setting_id) if game.setting_id else {}
        ds_move = ds_moves.get(brain_data.move)
        source_category = ds_move.track_category if ds_move else "vow"
        src_track = find_progress_track(game, source_category, target_track=brain_data.target_track)
        source_rank = src_track.rank if src_track else "dangerous"
        apply_progress_and_legacy(game, action.outcome, brain_data, source_category, source_rank)

    activated_npcs, mentioned_npcs, _ = activate_npcs_for_prompt(game, brain_data, player_words)

    consequence_sentences = generate_consequence_sentences(consequences, clock_events, game, brain_data)

    prompt = build_action_prompt(
        game,
        brain_data,
        upgraded,
        consequences,
        clock_events,
        [],
        player_words=player_words,
        scene_setup=scene_setup,
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
        position=position,
        effect=effect,
        consequence_sentences=consequence_sentences,
    )
    injection = eng().ai_text.validator_blocks["momentum_burn_injection"]
    prompt = prompt.replace("<task>", f"{injection}\n<task>")

    narration, _ = narrate_scene(provider, game, prompt, config=config)

    _scene_present_ids = {n.id for n in activated_npcs} | {n.id for n in mentioned_npcs}
    apply_post_narration(
        provider,
        game,
        narration,
        brain_data,
        upgraded,
        _scene_present_ids,
        [n.name for n in game.npcs if n.id in _scene_present_ids],
        config=config,
        consequences=consequences,
    )

    update_chaos_factor(game, new_result)

    nar = game.narrative
    if nar.narration_history:
        nar.narration_history[-1] = NarrationEntry(
            scene=nar.scene_count,
            prompt_summary=f"Momentum burn ({new_result}): {brain_data.player_intent[: eng().truncations.log_medium]}",
            narration=narration,
        )

    if nar.session_log:
        nar.session_log[-1].result = new_result
        nar.session_log[-1].consequences = consequences
        nar.session_log[-1].clock_events = clock_events
        nar.session_log[-1].scene_type = scene_setup.scene_type if scene_setup else "expected"

    _db_sync(game)

    return game, narration
