from ..ai.brain import call_brain
from ..ai.provider_base import AIProvider, drain_token_log
from ..datasworn.moves import get_moves
from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    apply_brain_location_time,
    can_burn_momentum,
    generate_consequence_sentences,
    is_dialog_branch,
    purge_old_fired_clocks,
    roll_action,
    roll_progress,
)
from ..mechanics.fate import resolve_fate, resolve_likelihood
from ..mechanics.random_events import drain_pending_events
from ..mechanics.scene import SceneSetup, check_scene
from ..mechanics.threats import advance_threat_by_id
from ..models import (
    BrainResult,
    EngineConfig,
    FateResult,
    GameState,
    ProgressTrack,
    RandomEvent,
    RollResult,
    ThreadEntry,
)
from ..npc import activate_npcs_for_prompt, find_npc, reactivate_npc
from ..prompt_action import build_action_prompt
from ..prompt_dialog import build_dialog_prompt
from ..story_state import get_pending_revelations
from .action_resolution import resolve_action_phase
from .finalization import narrate_scene
from .scene_finalization import finalize_scene
from .tracks import find_progress_track, roll_oracle_answer
from .turn_types import ActionResolution, RollOutcome, SceneContext


def process_turn(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None = None
) -> tuple[GameState, str, RollResult | None, dict | None, dict | None]:
    if game.game_over:
        raise RuntimeError(
            "process_turn called on a game with game_over=True. "
            "Caller must handle game_over (succession or new chapter) before requesting another turn."
        )

    _begin_turn(game, player_message)

    scene_setup = check_scene(game)

    brain = _run_brain_phase(provider, game, player_message, config)
    _sanitize_brain_output(game, brain)
    pending_random_events, fate_result = _resolve_brain_requests(game, brain)

    _apply_brain_state_mutations(game, brain)
    ctx = _build_scene_context(
        provider, game, brain, config, player_message, scene_setup, pending_random_events, fate_result
    )

    if is_dialog_branch(brain):
        narration, director_ctx = _process_dialog_turn(ctx)
        return game, narration, None, None, director_ctx

    game.narrative.scene_count += 1

    _maybe_create_track(game, brain)

    roll_outcome = _execute_roll(game, brain)
    roll = roll_outcome.roll

    burn_info = _check_burn_possibility(game, brain, roll_outcome, player_message, scene_setup)

    action_res = resolve_action_phase(game, brain, roll_outcome)

    narration, director_ctx = _narrate_action_and_finalize(ctx, roll_outcome, action_res, player_message)

    return game, narration, roll, burn_info, director_ctx


def _sanitize_brain_output(game: GameState, brain: BrainResult) -> None:
    if brain.dialog_only:
        return
    if brain.move == "dialog" or brain.move == "ask_the_oracle":
        return

    roll_type = _move_roll_type(game, brain.move)
    if roll_type != "action_roll":
        return

    if brain.stat == "none":
        log(
            f"[Brain] Sanitize: move={brain.move!r} requires action_roll but stat='none'. "
            f"Routing as dialog. Brain output likely invalid.",
            level="warning",
        )
        brain.dialog_only = True


def _move_roll_type(game: GameState, move: str) -> str | None:
    ds_moves = get_moves(game.setting_id) if game.setting_id else {}
    ds_move = ds_moves.get(move)
    if ds_move is not None:
        return ds_move.roll_type
    engine_move = eng().engine_moves.get(move)
    if engine_move is not None:
        return engine_move.roll_type
    return None


def _begin_turn(game: GameState, player_message: str) -> None:
    log(f"[Turn] Scene {game.narrative.scene_count + 1} | Player: {player_message[: eng().truncations.log_long]}")
    drain_pending_events()
    drain_token_log()
    purge_old_fired_clocks(game)
    game.last_turn_snapshot = game.snapshot()
    game.last_turn_snapshot.player_input = player_message


def _run_brain_phase(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None
) -> BrainResult:
    brain = call_brain(provider, game, player_message, config)
    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.brain = brain
    return brain


def _resolve_brain_requests(game: GameState, brain: BrainResult) -> tuple[list[RandomEvent], FateResult | None]:
    fate_result: FateResult | None = None
    if brain.fate_question:
        odds = resolve_likelihood(game, brain.fate_question)
        fate_result = resolve_fate(game, odds=odds, chaos_factor=game.world.chaos_factor, question=brain.fate_question)
        log(f"[Brain] Fate question resolved: '{brain.fate_question}' → {fate_result.answer}")

    pending_random_events = drain_pending_events()

    for event in pending_random_events:
        if event.target_id and any(t.id == event.target_id for t in game.threats):
            advance_threat_by_id(game, event.target_id, marks=1, source="random_event")

    return pending_random_events, fate_result


def _apply_brain_state_mutations(game: GameState, brain: BrainResult) -> None:
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
    fate_result: FateResult | None,
) -> SceneContext:
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
        fate_result=fate_result,
    )


def _process_dialog_turn(ctx: SceneContext) -> tuple[str, dict | None]:
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
        fate_result=ctx.fate_result,
    )
    narration = narrate_scene(
        ctx.provider,
        game,
        prompt,
        config=ctx.config,
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
        "_pacing_type": "breather",
    }
    if is_oracle:
        log_entry["oracle_answer"] = oracle_answer

    _, director_ctx = finalize_scene(
        ctx,
        narration,
        log_entry=log_entry,
        prompt_summary=f"{result_label.capitalize()}: {(brain.player_intent or ctx.player_message)[: eng().truncations.log_medium]}",
        roll_result_str=result_label,
    )
    return narration, director_ctx


def _maybe_create_track(game: GameState, brain: BrainResult) -> None:
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
    ds_moves = get_moves(game.setting_id) if game.setting_id else {}
    ds_move = ds_moves.get(brain.move)
    is_progress_roll = ds_move is not None and ds_move.roll_type == "progress_roll"
    track: ProgressTrack | None = None

    if is_progress_roll:
        assert ds_move is not None
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
        if stat_name == "none":
            raise ValueError(
                f"Brain returned stat='none' for action_roll move '{brain.move}'. "
                f"This is a Brain output error: action_roll moves require a real stat. "
                f"Brain should have either picked a valid stat or routed this as dialog/oracle."
            )
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


def _narrate_action_and_finalize(
    ctx: SceneContext,
    roll_outcome: RollOutcome,
    action_res: ActionResolution,
    player_message: str,
) -> tuple[str, dict | None]:
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
        fate_result=ctx.fate_result,
    )
    narration = narrate_scene(
        ctx.provider,
        game,
        prompt,
        config=ctx.config,
    )

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.narration = narration

    _, director_ctx = finalize_scene(
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
            "_pacing_type": "action",
        },
        prompt_summary=f"Action ({roll.result}): {(brain.player_intent or player_message)[: eng().truncations.log_medium]}",
        roll_result_str=roll.result,
        roll=roll,
        consequences=action_res.consequences,
        agency_clock_events=action_res.agency_clock_events,
    )
    return narration, director_ctx
