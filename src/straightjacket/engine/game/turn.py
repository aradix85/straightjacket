import copy
from typing import Any

from ..ai.brain import call_brain
from ..ai.provider_base import AIProvider, NarrationSink
from ..engine_loader import eng
from ..gamemaster.clock_ticks import check_npc_agency, purge_old_fired_clocks
from ..gamemaster.facts import (
    clear_facts_settled_by_hit,
    overrule_facts_by_hit,
    release_absent_target,
    remember_facts,
    settle_facts_by_miss,
)
from ..gamemaster.generation import generate_place_on_arrival, resolve_turn_facts
from ..gamemaster.npc.activation import activate_npcs_for_prompt
from ..gamemaster.npc.lifecycle import reactivate_npc
from ..gamemaster.npc.matching import find_npc
from ..gamemaster.questions import answers
from ..gamemaster.random_events import drain_pending_events
from ..gamemaster.resolvers import is_dialog_branch
from ..gamemaster.scene import check_scene
from ..gamemaster.world import apply_brain_location_time
from ..logging_util import log
from ..models import (
    BrainResult,
    ClockFillResult,
    GameState,
    PlaceRecord,
    ProgressTrack,
    RandomEvent,
    ResolvedFact,
    RollResult,
    SceneSetup,
    ThreatEvent,
    TurnSnapshot,
)
from ..prompt_action import build_action_prompt
from ..prompt_dialog import build_dialog_prompt
from ..prompt_loader import get_prompt
from ..ruleset.bonuses import apply_momentum_on_hit, chosen_bonus
from ..ruleset.config import rules
from ..ruleset.consequences import generate_consequence_sentences
from ..ruleset.meters import momentum
from ..ruleset.move_outcome import make_follow_up_moves
from ..ruleset.moves import PICK_METHODS, Move, get_moves
from ..ruleset.outcome_result import OutcomeResult
from ..ruleset.progress import filled_boxes
from ..ruleset.roll_sources import roll_by_method, roll_source_without_stat
from ..ruleset.rolls import (
    can_burn_momentum,
    downgrade_in_position,
    keep_action_dice,
    keep_progress_dice,
    roll_action,
    roll_progress,
)
from ..ruleset.suffer import tick_dying_clock
from ..ruleset.threats import advance_threat_by_id, resolve_full_menace, take_pending_threat_events
from ..ruleset.tracks import find_progress_track, roll_oracle_answer
from ..story_state import get_pending_revelations
from .action_resolution import resolve_action_phase
from .finalization import narrate_scene, update_crisis
from .scene_finalization import finalize_scene
from .turn_types import ActionResolution, BurnOffer, DirectorCall, RollOutcome, SceneContext


def process_turn(
    provider: AIProvider,
    game: GameState,
    player_message: str,
    stream: NarrationSink | None,
) -> tuple[str, RollResult | None, BurnOffer | None, DirectorCall | None]:
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
        provider,
        game,
        player_message,
        scene_setup,
        stream,
        earlier=None,
        earlier_places=[],
        narrator_note="",
        label=get_prompt("history_label_action"),
    )
    return narration, roll, burn_offer, director_ctx


def replay_turn(
    provider: AIProvider,
    game: GameState,
    player_message: str,
    narrator_note: str,
) -> tuple[str, BurnOffer | None, DirectorCall | None]:
    snap = game.last_turn_snapshot
    if snap is None or snap.scene_setup is None:
        raise ValueError("replay_turn needs the snapshot of a played turn, taken after its scene test")
    scene_setup = snap.scene_setup
    earlier = copy.deepcopy(snap)
    earlier_places = list(game.world.places)
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
        scene_setup,
        None,
        earlier=earlier,
        earlier_places=earlier_places,
        narrator_note=narrator_note,
        label=get_prompt("history_label_corrected"),
    )
    return narration, burn_offer, director_ctx


def _play_turn(
    provider: AIProvider,
    game: GameState,
    player_message: str,
    scene_setup: SceneSetup,
    stream: NarrationSink | None,
    *,
    earlier: TurnSnapshot | None,
    earlier_places: list[PlaceRecord],
    narrator_note: str,
    label: str,
) -> tuple[str, RollResult | None, BurnOffer | None, DirectorCall | None]:
    brain = _run_brain_phase(provider, game, player_message)
    _sanitize_brain_output(game, brain)
    moved = _apply_brain_state_mutations(game, brain)
    generate_place_on_arrival(game, brain, moved, earlier_places)
    if earlier is not None:
        remember_facts(game, earlier.facts)
    facts, pending_random_events = _resolve_brain_requests(game, brain)
    release_absent_target(brain, facts)

    ctx = build_scene_context(
        provider,
        game,
        brain,
        player_message,
        scene_setup,
        pending_random_events,
        facts,
        label,
        stream=stream,
        narrator_note=narrator_note,
    )

    if is_dialog_branch(brain):
        narration, director_ctx = _process_dialog_turn(ctx)
        return narration, None, None, director_ctx

    game.narrative.scene_count += 1

    roll_outcome = _execute_roll(game, brain, earlier.roll if earlier is not None else None)
    burn_offer = _offer_momentum_burn(ctx, roll_outcome)

    narration, director_ctx = resolve_and_narrate_action(ctx, roll_outcome)

    return narration, roll_outcome.roll, burn_offer, director_ctx


def _sanitize_brain_output(game: GameState, brain: BrainResult) -> None:
    if brain.dialog_only or brain.stat != "none" or brain.move in get_moves(game.setting_id):
        return
    if rules().engine_moves[brain.move].roll_type == "action_roll":
        log(f"[Brain] {brain.move!r} names no stat; it plays as dialog")
        brain.dialog_only = True


def _snapshot_of_turn(game: GameState) -> TurnSnapshot:
    snapshot = game.last_turn_snapshot
    if snapshot is None:
        raise ValueError("A turn runs only after its snapshot is taken")
    return snapshot


def _keep_what_the_turn_told(
    game: GameState,
    random_events: list[RandomEvent],
    threat_events: list[ThreatEvent],
    clock_fill_results: list[ClockFillResult],
    npc_agency: list[str],
) -> None:
    snapshot = _snapshot_of_turn(game)
    snapshot.random_events = list(random_events)
    snapshot.threat_events = list(threat_events)
    snapshot.clock_fill_results = list(clock_fill_results)
    snapshot.npc_agency = list(npc_agency)


def _begin_turn(game: GameState, player_message: str) -> None:
    log(f"[Turn] Scene {game.narrative.scene_count + 1} | Player: {player_message[: eng().truncations.log_long]}")
    drain_pending_events()
    purge_old_fired_clocks(game)


def _run_brain_phase(provider: AIProvider, game: GameState, player_message: str) -> BrainResult:
    brain = call_brain(provider, game, player_message)
    _snapshot_of_turn(game).brain = brain
    return brain


def _advance_threats_targeted_by(game: GameState, events: list[RandomEvent]) -> None:
    for event in events:
        if event.target_id and any(t.id == event.target_id for t in game.threats):
            advance_threat_by_id(game, event.target_id)


def _resolve_brain_requests(game: GameState, brain: BrainResult) -> tuple[list[ResolvedFact], list[RandomEvent]]:
    facts = resolve_turn_facts(game, brain)
    _snapshot_of_turn(game).facts = list(facts)
    pending_random_events = drain_pending_events()
    _advance_threats_targeted_by(game, pending_random_events)
    return facts, pending_random_events


def _apply_brain_state_mutations(game: GameState, brain: BrainResult) -> bool:
    tid = brain.target_npc
    if tid:
        target = find_npc(game, tid)
        if target and target.status == "background":
            reactivate_npc(target, reason=f"targeted by player in scene {game.narrative.scene_count + 1}")
    return apply_brain_location_time(game, brain)


def build_scene_context(
    provider: AIProvider,
    game: GameState,
    brain: BrainResult,
    player_message: str,
    scene_setup: SceneSetup,
    pending_random_events: list[RandomEvent],
    facts: list[ResolvedFact],
    summary_label: str,
    *,
    stream: NarrationSink | None,
    narrator_note: str,
) -> SceneContext:
    activated_npcs, mentioned_npcs = activate_npcs_for_prompt(game, brain, player_message)
    scene_present_ids = {n.id for n in activated_npcs} | {n.id for n in mentioned_npcs}
    pending_revs = get_pending_revelations(game)

    return SceneContext(
        provider=provider,
        game=game,
        brain=brain,
        player_message=player_message,
        scene_setup=scene_setup,
        scene_present_ids=scene_present_ids,
        pending_revs=pending_revs,
        facts=facts,
        summary_label=summary_label,
        activated_npcs=activated_npcs,
        mentioned_npcs=mentioned_npcs,
        pending_random_events=pending_random_events,
        stream=stream,
        narrator_note=narrator_note,
    )


def _process_dialog_turn(ctx: SceneContext) -> tuple[str, DirectorCall | None]:
    game = ctx.game
    brain = ctx.brain
    is_oracle = brain.move == "ask_the_oracle"
    game.narrative.scene_count += 1

    oracle_answer = roll_oracle_answer(game) if is_oracle and not ctx.facts else ""

    pending_fills = list(game.world.pending_clock_fills)
    game.world.pending_clock_fills.clear()
    npc_agency, agency_clock_events, agency_fill_results = check_npc_agency(game)
    pending_fills.extend(agency_fill_results)
    engine_moves = OutcomeResult()
    tick_dying_clock(game, engine_moves)
    threat_events = take_pending_threat_events(game)
    threat_events.extend(resolve_full_menace(game, engine_moves))
    make_follow_up_moves(game, engine_moves)
    update_crisis(game)
    _keep_what_the_turn_told(game, ctx.pending_random_events, threat_events, pending_fills, npc_agency)

    prompt = build_dialog_prompt(
        game,
        brain,
        player_words=ctx.player_message,
        scene_setup=ctx.scene_setup,
        activated_npcs=ctx.activated_npcs,
        mentioned_npcs=ctx.mentioned_npcs,
        oracle_answer=oracle_answer,
        random_events=ctx.pending_random_events,
        threat_events=threat_events,
        consequences=engine_moves.consequences,
        clock_fill_results=pending_fills,
        npc_agency=npc_agency,
        facts=ctx.facts,
    )
    prompt = _with_narrator_note(prompt, ctx.narrator_note)
    narration = narrate_scene(
        ctx.provider,
        game,
        prompt,
        stream=ctx.stream,
    )

    _snapshot_of_turn(game).narration = narration

    result_label = "oracle" if is_oracle else "dialog"
    log_entry: dict[str, Any] = {
        "scene": game.narrative.scene_count,
        "summary": (brain.player_intent or ctx.player_message),
        "move": brain.move,
        "result": result_label,
        "consequences": engine_moves.consequences,
        "clock_events": [],
        "scene_type": ctx.scene_setup.scene_type,
        "_pacing_type": "breather",
    }
    if is_oracle:
        log_entry["oracle_answer"] = oracle_answer

    _, director_ctx = finalize_scene(
        ctx,
        narration,
        log_entry=log_entry,
        prompt_summary=get_prompt(
            "history_oracle" if is_oracle else "history_dialog",
            intent=(brain.player_intent or ctx.player_message)[: eng().truncations.log_medium],
        ),
        roll_result_str=result_label,
        consequences=engine_moves.consequences,
        agency_clock_events=agency_clock_events,
        threat_events=threat_events,
    )
    return narration, director_ctx


def _execute_roll(game: GameState, brain: BrainResult, earlier: RollResult | None) -> RollOutcome:
    ds_move = get_moves(game.setting_id).get(brain.move)
    track: ProgressTrack | None = None

    if ds_move is not None and ds_move.roll_type == "progress_roll":
        track = find_progress_track(game, ds_move.track_category, brain.target_track)
        filled = filled_boxes(track)
        if earlier is None:
            roll = roll_progress(track.name, filled, brain.move)
        else:
            roll = keep_progress_dice(earlier, track.name, filled, brain.move)
        roll = downgrade_in_position(game, roll)
        log(
            f"[Roll] {roll.move} (progress: {track.name}={filled} boxes): "
            f"{roll.action_score} vs [{roll.c1},{roll.c2}] "
            f"→ {roll.result}{' MATCH!' if roll.match else ''}"
        )
    else:
        stat_name, stat_value = _roll_source(game, brain, ds_move)
        bonus = chosen_bonus(game, brain.bonus_id)
        adds = game.resources.next_move_bonus + (bonus.add if bonus else 0)
        rolled_momentum = momentum(game)
        if earlier is None:
            roll = roll_action(stat_name, stat_value, brain.move, rolled_momentum, adds)
        else:
            roll = keep_action_dice(earlier, stat_name, stat_value, brain.move, rolled_momentum, adds)
        game.resources.next_move_bonus = 0
        if bonus:
            apply_momentum_on_hit(game, bonus, roll.result)
        _log_action_roll(roll, adds, cancelled=rolled_momentum < 0 and -rolled_momentum == roll.d1)

    _snapshot_of_turn(game).roll = roll

    return RollOutcome(roll=roll, ds_move=ds_move, track=track)


def _roll_source(game: GameState, brain: BrainResult, ds_move: Move | None) -> tuple[str, int]:
    if ds_move is not None and not ds_move.valid_stats:
        source = roll_source_without_stat(game, ds_move, brain.target_npc)
        if source is None:
            raise ValueError(f"{brain.move!r} has nothing to roll with for target {brain.target_npc!r}")
        return source
    if brain.stat == "none":
        raise ValueError(f"{brain.move!r} is an action roll, but the Brain named no stat")
    if brain.stat in PICK_METHODS:
        if ds_move is None:
            raise ValueError(f"{brain.move!r} has no way that rolls the {brain.stat} stat")
        return roll_by_method(game, ds_move, brain.stat)
    return brain.stat, game.stats[brain.stat]


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
    if roll_outcome.track is not None:
        return None
    new_result = can_burn_momentum(game, roll)
    if new_result is None:
        return None
    return BurnOffer(
        roll=roll,
        new_result=new_result,
        cost=momentum(game),
        brain=ctx.brain,
        player_words=ctx.player_message,
        scene_setup=ctx.scene_setup,
        ds_move=roll_outcome.ds_move,
        random_events=list(ctx.pending_random_events),
        facts=list(ctx.facts),
        resume_snapshot=game.snapshot(),
    )


def resolve_and_narrate_action(ctx: SceneContext, roll_outcome: RollOutcome) -> tuple[str, DirectorCall | None]:
    action_res = resolve_action_phase(ctx.game, ctx.brain, roll_outcome)
    outcome = answers().outcome(roll_outcome.roll.result)
    clear_facts_settled_by_hit(ctx.game, ctx.facts, outcome)
    ctx.facts = overrule_facts_by_hit(ctx.game, ctx.facts, outcome)
    ctx.facts = settle_facts_by_miss(ctx.game, ctx.facts, ctx.brain.move, outcome)
    return _narrate_action_and_finalize(ctx, roll_outcome, action_res)


def _with_narrator_note(prompt: str, note: str) -> str:
    return prompt.replace("<task>", f"{note}\n<task>") if note else prompt


def _narrate_action_and_finalize(
    ctx: SceneContext,
    roll_outcome: RollOutcome,
    action_res: ActionResolution,
) -> tuple[str, DirectorCall | None]:
    game = ctx.game
    brain = ctx.brain
    roll = roll_outcome.roll
    player_message = ctx.player_message

    consequence_sentences = generate_consequence_sentences(
        action_res.consequences, action_res.clock_events, game, brain
    )
    _keep_what_the_turn_told(
        game,
        ctx.pending_random_events,
        action_res.threat_events,
        action_res.clock_fill_results,
        action_res.npc_agency,
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
        stream=ctx.stream,
    )

    snapshot = _snapshot_of_turn(game)
    snapshot.roll = roll
    snapshot.narration = narration

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
            "_pacing_type": "action",
        },
        prompt_summary=get_prompt(
            "history_action",
            label=ctx.summary_label,
            result=roll.result,
            intent=(brain.player_intent or player_message)[: eng().truncations.log_medium],
        ),
        roll_result_str=roll.result,
        roll=roll,
        consequences=action_res.consequences,
        agency_clock_events=action_res.agency_clock_events,
        threat_events=action_res.threat_events,
    )
    return narration, director_ctx
