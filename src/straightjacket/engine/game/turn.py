import copy
import re
from typing import Any
from ..ai.brain import call_brain
from ..ai.provider_base import AIProvider, drain_token_log, NarrationSink
from ..datasworn.moves import get_moves
from ..engine_loader import eng
from ..logging_util import log
from ..ids import unique_id
from ..mechanics import (
    apply_brain_location_time,
    can_burn_momentum,
    clear_facts_settled_by_hit,
    settle_facts_by_miss,
    generate_consequence_sentences,
    is_dialog_branch,
    keep_action_dice,
    keep_progress_dice,
    purge_old_fired_clocks,
    remember_facts,
    resolve_turn_facts,
    roll_action,
    roll_progress,
)
from ..mechanics import check_npc_agency
from ..mechanics.random_events import drain_pending_events
from ..mechanics.scene import check_scene
from ..mechanics.threats import advance_threat_by_id
from ..models import (
    BrainResult,
    EngineConfig,
    GameState,
    ProgressTrack,
    RandomEvent,
    ResolvedFact,
    RollResult,
    SceneSetup,
    ThreadEntry,
    TurnSnapshot,
)
from ..npc import activate_npcs_for_prompt, find_npc, reactivate_npc
from ..prompt_action import build_action_prompt
from ..prompt_dialog import build_dialog_prompt
from ..story_state import get_pending_revelations
from .action_resolution import resolve_action_phase
from .finalization import narrate_scene
from .scene_finalization import finalize_scene
from ..mechanics import find_progress_track, roll_oracle_answer
from ..mechanics.bonuses import apply_momentum_on_hit, chosen_bonus
from .turn_types import ActionResolution, BurnOffer, RollOutcome, SceneContext


def process_turn(
    provider: AIProvider,
    game: GameState,
    player_message: str,
    config: EngineConfig | None = None,
    stream: NarrationSink | None = None,
) -> tuple[GameState, str, RollResult | None, BurnOffer | None, dict[str, Any] | None]:
    if game.game_over:
        raise RuntimeError(
            "process_turn called on a game with game_over=True. "
            "Caller must continue the campaign through succession before requesting another turn."
        )

    _begin_turn(game, player_message)
    scene_setup = check_scene(game)
    _advance_threats_targeted_by(game, drain_pending_events())
    snapshot = game.snapshot()
    snapshot.player_input = player_message
    snapshot.scene_setup = scene_setup
    game.last_turn_snapshot = snapshot

    narration, roll, burn_offer, director_ctx = _play_turn(
        provider, game, player_message, config, scene_setup, stream, earlier=None, narrator_note="", label="Action"
    )
    return game, narration, roll, burn_offer, director_ctx


def replay_turn(
    provider: AIProvider,
    game: GameState,
    player_message: str,
    config: EngineConfig | None,
    narrator_note: str,
) -> tuple[str, BurnOffer | None, dict[str, Any] | None]:
    snap = game.last_turn_snapshot
    if snap is None or snap.scene_setup is None:
        raise ValueError("replay_turn needs the snapshot of a played turn, taken after its scene test")
    scene_setup = snap.scene_setup
    earlier = copy.deepcopy(snap)
    game.restore(snap)
    game.last_turn_snapshot = snap
    snap.player_input = player_message
    log(
        f"[Turn] Replaying scene {game.narrative.scene_count + 1} | Player: {player_message[: eng().truncations.log_long]}"
    )

    narration, _roll, burn_offer, director_ctx = _play_turn(
        provider,
        game,
        player_message,
        config,
        scene_setup,
        None,
        earlier=earlier,
        narrator_note=narrator_note,
        label="Corrected action",
    )
    return narration, burn_offer, director_ctx


def _play_turn(
    provider: AIProvider,
    game: GameState,
    player_message: str,
    config: EngineConfig | None,
    scene_setup: SceneSetup,
    stream: NarrationSink | None,
    *,
    earlier: TurnSnapshot | None,
    narrator_note: str,
    label: str,
) -> tuple[str, RollResult | None, BurnOffer | None, dict[str, Any] | None]:
    brain = _run_brain_phase(provider, game, player_message, config)
    _sanitize_brain_output(game, brain)
    _apply_brain_state_mutations(game, brain)
    if earlier is not None:
        remember_facts(game, earlier.facts)
    facts, pending_random_events = _resolve_brain_requests(game, brain)

    ctx = build_scene_context(provider, game, brain, config, player_message, scene_setup, pending_random_events, facts)
    ctx.stream = stream
    ctx.narrator_note = narrator_note
    ctx.summary_label = label

    if is_dialog_branch(brain):
        narration, director_ctx = _process_dialog_turn(ctx)
        return narration, None, None, director_ctx

    game.narrative.scene_count += 1

    _maybe_create_track(game, brain)

    roll_outcome = _execute_roll(game, brain, earlier.roll if earlier is not None else None)
    burn_offer = _offer_momentum_burn(ctx, roll_outcome)

    narration, director_ctx = resolve_and_narrate_action(ctx, roll_outcome)

    return narration, roll_outcome.roll, burn_offer, director_ctx


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


def _run_brain_phase(
    provider: AIProvider, game: GameState, player_message: str, config: EngineConfig | None
) -> BrainResult:
    brain = call_brain(provider, game, player_message, config)
    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.brain = brain
    return brain


def _advance_threats_targeted_by(game: GameState, events: list[RandomEvent]) -> None:
    for event in events:
        if event.target_id and any(t.id == event.target_id for t in game.threats):
            advance_threat_by_id(game, event.target_id, marks=1, source="random_event")


def _resolve_brain_requests(game: GameState, brain: BrainResult) -> tuple[list[ResolvedFact], list[RandomEvent]]:
    facts = resolve_turn_facts(game, brain)
    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.facts = list(facts)
    pending_random_events = drain_pending_events()
    _advance_threats_targeted_by(game, pending_random_events)
    return facts, pending_random_events


def _apply_brain_state_mutations(game: GameState, brain: BrainResult) -> None:
    tid = brain.target_npc
    if tid:
        target = find_npc(game, tid)
        if target and target.status == "background":
            reactivate_npc(target, reason=f"targeted by player in scene {game.narrative.scene_count + 1}")
    apply_brain_location_time(game, brain)


def build_scene_context(
    provider: AIProvider,
    game: GameState,
    brain: BrainResult,
    config: EngineConfig | None,
    player_message: str,
    scene_setup: SceneSetup,
    pending_random_events: list[RandomEvent],
    facts: list[ResolvedFact],
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
        facts=facts,
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
        pending_random_events=pending_random_events,
    )


def _process_dialog_turn(ctx: SceneContext) -> tuple[str, dict[str, Any] | None]:
    game = ctx.game
    brain = ctx.brain
    is_oracle = brain.move == "ask_the_oracle"
    game.narrative.scene_count += 1

    oracle_answer = roll_oracle_answer(game) if is_oracle and not ctx.facts else ""

    pending_fills = list(game.world.pending_clock_fills)
    game.world.pending_clock_fills.clear()
    npc_agency, agency_clock_events, agency_fill_results = check_npc_agency(game)
    pending_fills.extend(agency_fill_results)

    prompt = build_dialog_prompt(
        game,
        brain,
        player_words=ctx.player_message,
        scene_setup=ctx.scene_setup,
        activated_npcs=ctx.activated_npcs,
        mentioned_npcs=ctx.mentioned_npcs,
        oracle_answer=oracle_answer,
        random_events=ctx.pending_random_events,
        clock_fill_results=pending_fills,
        npc_agency=npc_agency,
        facts=ctx.facts,
    )
    prompt = _with_narrator_note(prompt, ctx.narrator_note)
    narration = narrate_scene(
        ctx.provider,
        game,
        prompt,
        config=ctx.config,
        stream=ctx.stream,
    )

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.narration = narration

    result_label = "oracle" if is_oracle else "dialog"
    log_entry: dict[str, Any] = {
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
        agency_clock_events=agency_clock_events,
    )
    return narration, director_ctx


def _maybe_create_track(game: GameState, brain: BrainResult) -> None:
    track_creating = eng().get_raw("track_creating_moves")
    track_category = track_creating.get(brain.move)
    if not track_category:
        return
    assert brain.track_name
    assert brain.track_rank

    slug = re.sub(r"\W+", "_", brain.track_name.lower()).strip("_")
    base_id = f"{track_category}_{slug}"
    if any(t.id == base_id and t.status == "active" for t in game.progress_tracks):
        log(f"[Track] {track_category} '{brain.track_name}' is already active; not created again")
        return
    track_id = unique_id(base_id, {t.id for t in game.progress_tracks})
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
                id=unique_id(f"thread_{slug}", {t.id for t in game.narrative.threads}),
                name=brain.track_name,
                thread_type="vow",
                weight=2,
                source="vow",
                linked_track_id=track_id,
            )
        )
        log(f"[Track] Created linked thread for vow: {brain.track_name}")


def _execute_roll(game: GameState, brain: BrainResult, earlier: RollResult | None) -> RollOutcome:
    ds_moves = get_moves(game.setting_id) if game.setting_id else {}
    ds_move = ds_moves.get(brain.move)
    is_progress_roll = ds_move is not None and ds_move.roll_type == "progress_roll"
    track: ProgressTrack | None = None

    if is_progress_roll:
        assert ds_move is not None
        track = find_progress_track(game, ds_move.track_category, target_track=brain.target_track)
        filled = track.filled_boxes if track else 0
        track_name = track.name if track else ds_move.track_category
        if earlier is None:
            roll = roll_progress(track_name, filled, brain.move)
        else:
            roll = keep_progress_dice(earlier, track_name, filled, brain.move)
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
        bonus = chosen_bonus(game, brain.bonus_id)
        adds = game.resources.next_move_bonus + (bonus.add if bonus else 0)
        stat_value, momentum = game.get_stat(stat_name), game.resources.momentum
        if earlier is None:
            roll = roll_action(stat_name, stat_value, brain.move, momentum, adds)
        else:
            roll = keep_action_dice(earlier, stat_name, stat_value, brain.move, momentum, adds)
        game.resources.next_move_bonus = 0
        if bonus:
            apply_momentum_on_hit(game, bonus, roll.result)
        _log_action_roll(roll, adds, cancelled=game.resources.momentum < 0 and -game.resources.momentum == roll.d1)

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.roll = roll

    return RollOutcome(roll=roll, ds_move=ds_move, track=track, is_progress_roll=is_progress_roll)


def _log_action_roll(roll: RollResult, adds: int, cancelled: bool) -> None:
    raw = (0 if cancelled else roll.d1) + roll.stat_value + adds
    score = f"{raw}→{roll.action_score}(cap)" if raw > roll.action_score else str(roll.action_score)
    log(
        f"[Roll] {roll.move} ({roll.stat_name}={roll.stat_value}): "
        f"{roll.d1}+{roll.stat_value}{f'+{adds}' if adds else ''}={score} vs [{roll.c1},{roll.c2}] "
        f"→ {roll.result}{' MATCH!' if roll.match else ''}"
        f"{' (action die cancelled by negative momentum)' if cancelled else ''}"
    )


def _offer_momentum_burn(ctx: SceneContext, roll_outcome: RollOutcome) -> BurnOffer | None:
    game = ctx.game
    roll = roll_outcome.roll
    if roll_outcome.is_progress_roll:
        return None
    new_result = can_burn_momentum(game, roll)
    if new_result is None:
        return None
    return BurnOffer(
        roll=roll,
        new_result=new_result,
        cost=game.resources.momentum,
        brain=ctx.brain,
        player_words=ctx.player_message,
        scene_setup=ctx.scene_setup,
        ds_move=roll_outcome.ds_move,
        random_events=list(ctx.pending_random_events),
        facts=list(ctx.facts),
        resume_snapshot=game.snapshot(),
    )


def resolve_and_narrate_action(ctx: SceneContext, roll_outcome: RollOutcome) -> tuple[str, dict[str, Any] | None]:
    action_res = resolve_action_phase(ctx.game, ctx.brain, roll_outcome)
    clear_facts_settled_by_hit(ctx.game, ctx.facts, roll_outcome.roll.result)
    ctx.facts = settle_facts_by_miss(ctx.game, ctx.facts, ctx.brain.move, roll_outcome.roll.result)
    return _narrate_action_and_finalize(ctx, roll_outcome, action_res)


def _with_narrator_note(prompt: str, note: str) -> str:
    return prompt.replace("<task>", f"{note}\n<task>") if note else prompt


def _narrate_action_and_finalize(
    ctx: SceneContext,
    roll_outcome: RollOutcome,
    action_res: ActionResolution,
) -> tuple[str, dict[str, Any] | None]:
    game = ctx.game
    brain = ctx.brain
    roll = roll_outcome.roll
    player_message = ctx.player_message

    consequence_sentences = generate_consequence_sentences(
        action_res.consequences, action_res.clock_events, game, brain
    )

    prompt = build_action_prompt(
        game,
        brain,
        roll,
        action_res.consequences,
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
        clock_fill_results=action_res.clock_fill_results,
        facts=ctx.facts,
    )
    prompt = _with_narrator_note(prompt, ctx.narrator_note)
    narration = narrate_scene(
        ctx.provider,
        game,
        prompt,
        config=ctx.config,
        stream=ctx.stream,
    )

    if game.last_turn_snapshot is not None:
        game.last_turn_snapshot.roll = roll
        game.last_turn_snapshot.narration = narration

    summary_label = ctx.summary_label
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
        prompt_summary=f"{summary_label} ({roll.result}): {(brain.player_intent or player_message)[: eng().truncations.log_medium]}",
        roll_result_str=roll.result,
        roll=roll,
        consequences=action_res.consequences,
        agency_clock_events=action_res.agency_clock_events,
    )
    return narration, director_ctx
