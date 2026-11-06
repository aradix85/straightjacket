import random

from straightjacket.engine.game.finalization import resolve_action_consequences, update_crisis
from straightjacket.engine.game.turn_types import ActionResolution
from straightjacket.engine.gamemaster.clocks import avert_complication, check_npc_agency, tick_threat_clock
from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.gamemaster.npc.matching import find_npc
from straightjacket.engine.gamemaster.questions import answers, gained
from straightjacket.engine.gamemaster.resolvers import resolve_effect, resolve_position
from straightjacket.engine.models import (
    BrainResult,
    ClockEvent,
    ClockFillResult,
    Consequence,
    GameState,
    RollResult,
    ThreatEvent,
    consequence,
)
from straightjacket.engine.ruleset.make_move import RollOutcome
from straightjacket.engine.ruleset.move_outcome import make_due_bond_test, make_follow_up_moves
from straightjacket.engine.ruleset.outcome_result import OutcomeResult
from straightjacket.engine.ruleset.suffer import tick_dying_clock
from straightjacket.engine.ruleset.threats import (
    advance_menace_on_miss,
    resolve_full_menace,
    take_pending_threat_events,
)
from straightjacket.engine.ruleset.tracks import apply_progress_and_legacy, resolve_progress_roll, start_track


def _maybe_tick_weak_hit_clock(
    game: GameState,
    roll: RollResult,
    position: str,
    clock_events: list[ClockEvent],
    fill_results: list[ClockFillResult],
) -> None:
    if answers().outcome(roll.result) != "partial" or position == "controlled":
        return
    should_tick = (position == "desperate") or (random.random() < gm().pacing.weak_hit_clock_tick_chance)
    if should_tick:
        tick_threat_clock(game, 1, clock_events, fill_results)


def _maybe_avert_complication(
    game: GameState, brain: BrainResult, roll: RollResult, consequences: list[Consequence]
) -> None:
    if not brain.target_clock or not gained(roll.result):
        return
    avert_complication(game, brain.target_clock)
    consequences.append(consequence("complication_averted", name=brain.target_clock))


def _collect_threat_events(game: GameState, roll: RollResult, outcome: OutcomeResult) -> list[ThreatEvent]:
    events = take_pending_threat_events(game)
    if answers().outcome(roll.result) == "failure":
        events.extend(advance_menace_on_miss(game))
    events.extend(resolve_full_menace(game, outcome))
    return events


def _count_information_gathered(game: GameState, brain: BrainResult, roll: RollResult) -> None:
    if not answers().gathers_information(brain.move) or not gained(roll.result):
        return
    if brain.target_npc is None:
        return
    target = find_npc(game, brain.target_npc)
    if target is None:
        msg = f"Target NPC {brain.target_npc!r} is not in the game"
        raise ValueError(msg)
    target.gather_count += 1


def resolve_action_phase(game: GameState, brain: BrainResult, roll_outcome: RollOutcome) -> ActionResolution:
    roll = roll_outcome.roll
    track = roll_outcome.track
    start_track(game, brain, roll.result)

    position = resolve_position(game, brain)
    effect = resolve_effect(game, brain, position)

    pending_from_prior_turn = list(game.world.pending_clock_fills)
    game.world.pending_clock_fills.clear()

    action = resolve_action_consequences(game, brain, roll, position)
    consequences = action.consequences
    clock_events = action.clock_events
    fill_results = pending_from_prior_turn + action.clock_fill_results

    apply_progress_and_legacy(game, action.outcome, brain, track)

    if track is not None:
        resolve_progress_roll(game, roll, track, action.outcome)

    _maybe_avert_complication(game, brain, roll, consequences)
    _maybe_tick_weak_hit_clock(game, roll, position, clock_events, fill_results)

    npc_agency, agency_clock_events, agency_fill_results = check_npc_agency(game)
    fill_results.extend(agency_fill_results)

    make_due_bond_test(game, brain.target_npc, brain.move, action.outcome)
    threat_events = _collect_threat_events(game, roll, action.outcome)
    tick_dying_clock(game, action.outcome)
    make_follow_up_moves(game, action.outcome)
    update_crisis(game)

    _count_information_gathered(game, brain, roll)

    return ActionResolution(
        position=position,
        effect=effect,
        consequences=consequences,
        clock_events=clock_events,
        npc_agency=npc_agency,
        agency_clock_events=agency_clock_events,
        threat_events=threat_events,
        clock_fill_results=fill_results,
    )
