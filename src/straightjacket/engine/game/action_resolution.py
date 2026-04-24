"""Action-roll consequence resolution.

Phase 9 of the turn pipeline: given a RollOutcome, produce an ActionResolution.
Sub-steps:
  - position/effect (deterministic from game state)
  - move outcome resolution + MISS clocks + crisis check
  - progress marks and legacy-track rewards
  - track completion on progress rolls
  - scene-challenge progress routing
  - WEAK_HIT threat-clock tick (turn-only; correction and burn skip this)
  - NPC agency checks
  - threat-event collection (menace on miss, Forsake Your Vow, overcome acks)
  - gather_information success counter

The scene-challenge and WEAK_HIT clock paths are intentionally turn-only:
they are mechanical turn boundaries, not re-narration events, so correction
and momentum-burn re-runs do not replay them.
"""

import random

from ..engine_loader import eng
from ..logging_util import log
from ..mechanics import (
    check_npc_agency,
    resolve_effect,
    resolve_position,
)
from ..mechanics.consequences import tick_threat_clock
from ..mechanics.threats import advance_menace_on_miss, resolve_full_menace
from ..models import BrainResult, ClockEvent, GameState, ProgressTrack, RollResult, ThreatEvent
from ..npc import find_npc
from .finalization import apply_progress_and_legacy, resolve_action_consequences
from .tracks import complete_track, find_progress_track
from .turn_types import ActionResolution, RollOutcome


def _apply_track_completion(game: GameState, roll: RollResult, track: ProgressTrack) -> None:
    """Complete or fail the progress track based on the progress-roll result."""
    if roll.result == "STRONG_HIT":
        complete_track(game, track.id, "completed")
    elif roll.result == "MISS":
        complete_track(game, track.id, "failed")


def _maybe_mark_scene_challenge(game: GameState, brain: BrainResult, roll: RollResult) -> None:
    """Step 10.2: if the move is in scene_challenge_progress_moves and the roll
    hit, tick the active scene_challenge progress track.
    """
    sc_progress_moves = eng().get_raw("scene_challenge_progress_moves")
    if brain.move not in sc_progress_moves or roll.result not in ("STRONG_HIT", "WEAK_HIT"):
        return
    sc_track = find_progress_track(game, "scene_challenge")
    if not sc_track:
        return
    added = sc_track.mark_progress()
    if added:
        log(f"[Track] Scene challenge '{sc_track.name}': +{added} ticks ({sc_track.filled_boxes}/10 boxes)")


def _maybe_tick_weak_hit_clock(
    game: GameState, roll: RollResult, position: str, clock_events: list[ClockEvent]
) -> None:
    """WEAK_HIT clock tick — turn-only (correction/burn re-narration skips this).
    Always ticks on desperate; otherwise rolls weak_hit_clock_tick_chance.
    """
    if roll.result != "WEAK_HIT" or position == "controlled":
        return
    should_tick = (position == "desperate") or (random.random() < eng().pacing.weak_hit_clock_tick_chance)
    if should_tick:
        tick_threat_clock(game, 1, clock_events)


def _collect_threat_events(game: GameState, roll: RollResult) -> list[ThreatEvent]:
    """Assemble the threat events for the prompt: menace-on-miss + Forsake Your Vow
    + overcome-under-pressure acknowledgments.
    """
    events: list[ThreatEvent] = advance_menace_on_miss(game) if roll.result == "MISS" else []
    events.extend(resolve_full_menace(game))

    high_threshold = eng().threats.menace_high_threshold
    for threat in game.threats:
        if threat.status == "overcome" and threat.menace_filled_boxes / 10 >= high_threshold:
            events.append(
                ThreatEvent(
                    threat_id=threat.id,
                    threat_name=threat.name,
                    ticks_added=0,
                    menace_full=False,
                    source="overcome_under_pressure",
                )
            )
    return events


def _track_gather_information_success(game: GameState, brain: BrainResult, roll: RollResult) -> None:
    """Increment gather_count on a successful gather_information move.
    Feeds into the information-gating subsystem (step 6).
    """
    if brain.move != "adventure/gather_information" or roll.result not in ("STRONG_HIT", "WEAK_HIT"):
        return
    if not brain.target_npc:
        return
    target = find_npc(game, brain.target_npc)
    if target:
        target.gather_count += 1


def resolve_action_phase(game: GameState, brain: BrainResult, roll_outcome: RollOutcome) -> ActionResolution:
    """Phase 9: resolve every mechanical consequence of the roll. Sub-steps:
    position/effect, move outcome + clocks + crisis, progress marks and legacy,
    track completion, scene challenge routing, WEAK_HIT clocks, NPC agency,
    threat events, gather_information tracking.
    """
    roll = roll_outcome.roll
    ds_move = roll_outcome.ds_move
    track = roll_outcome.track
    is_progress_roll = roll_outcome.is_progress_roll

    # Position and effect (deterministic from game state)
    position = resolve_position(game, brain)
    effect = resolve_effect(game, brain, position)

    # Move outcome + MISS clocks + crisis (shared with correction/burn)
    action = resolve_action_consequences(game, brain, roll, position)
    consequences = action.consequences
    clock_events = action.clock_events

    # Progress marks and legacy tracks (shared with correction/burn)
    if action.outcome:
        source_category = ds_move.track_category if ds_move else "vow"
        source_rank = track.rank if is_progress_roll and track else "dangerous"
        apply_progress_and_legacy(game, action.outcome, brain, source_category, source_rank)

    if is_progress_roll and track:
        _apply_track_completion(game, roll, track)

    _maybe_mark_scene_challenge(game, brain, roll)
    _maybe_tick_weak_hit_clock(game, roll, position, clock_events)

    npc_agency, agency_clock_events = check_npc_agency(game)

    threat_events = _collect_threat_events(game, roll)

    _track_gather_information_success(game, brain, roll)

    return ActionResolution(
        position=position,
        effect=effect,
        consequences=consequences,
        clock_events=clock_events,
        npc_agency=npc_agency,
        agency_clock_events=agency_clock_events,
        threat_events=threat_events,
    )
