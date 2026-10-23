from __future__ import annotations

import random
import re
from collections.abc import Callable

from ..gamemaster.config import gm
from ..ids import unique_id
from ..logging_util import log
from ..models import (
    BrainResult,
    ClockData,
    GameState,
    ProgressTrack,
    RollResult,
    ThreadEntry,
    ThreatData,
    ThreatEvent,
    consequence,
)
from .bond import connection_track, connection_track_id
from .bonuses import bond_of_bonus
from .config import rules
from .datasworn import load_ruleset
from .impacts import clear_impact
from .legacy import apply_threat_overcome_bonus, mark_legacy, mark_legacy_ticks, shifted_rank
from .moves import get_moves
from .outcome_result import OutcomeResult, move_outcome_config
from .progress import filled_boxes, mark_progress, menace_boxes, menace_total_boxes, new_track
from .suffer import suffer


def _slug(name: str) -> str:
    return re.sub(r"\W+", "_", name.lower()).strip("_")


def start_track(game: GameState, brain: BrainResult, result: str) -> None:
    track_type = rules().get_raw("track_creating_moves").get(brain.move)
    if not track_type:
        return
    if result not in rules().dice.hit_results and brain.move in rules().get_raw("tracks_started_on_a_hit"):
        log(f"[Track] {brain.move} missed; no {track_type} track")
        return
    if brain.target_track is not None and brain.move in rules().get_raw("progress_mark_categories"):
        log(f"[Track] {brain.move} continues {brain.target_track}; no new {track_type} track")
        return
    assert brain.track_name
    assert brain.track_rank

    if track_type == "connection":
        if brain.target_npc is None:
            log(f"[Track] {brain.move}: its target turned out absent; no connection")
            return
        if connection_track(game, brain.target_npc) is not None:
            log(f"[Track] {brain.target_npc} is already a connection; not made again")
            return
        base_id = connection_track_id(brain.target_npc)
    else:
        base_id = f"{track_type}_{_slug(brain.track_name)}"
    if any(t.id == base_id and t.status == "active" for t in game.progress_tracks):
        log(f"[Track] {track_type} '{brain.track_name}' is already active; not created again")
        return
    track = _add_track(game, base_id, brain.track_name, track_type, brain.track_rank)
    if track_type != "vow":
        return
    track.vowed_to = bond_of_bonus(game, brain.bonus_id)
    if brain.target_threat is not None:
        threat = next(t for t in game.threats if t.id == brain.target_threat)
        threat.linked_vow_id = track.id
        log(f"[Threat] '{threat.name}' now has the vow '{track.name}' sworn against it")


def _add_track(game: GameState, base_id: str, name: str, track_type: str, rank: str) -> ProgressTrack:
    track_id = unique_id(base_id, {t.id for t in game.progress_tracks})
    track = new_track(id=track_id, name=name, track_type=track_type, rank=rank)
    game.progress_tracks.append(track)
    log(f"[Track] Created {track_type} track: {name} ({rank}), id={track_id}")

    if track_type == "vow":
        thread_id = unique_id(f"thread_{_slug(name)}", {t.id for t in game.narrative.threads})
        game.narrative.threads.append(_vow_thread(thread_id, track, "vow"))
        log(f"[Track] Created linked thread for vow: {name}")
    return track


def _vow_thread(thread_id: str, vow: ProgressTrack, source: str) -> ThreadEntry:
    return ThreadEntry(
        id=thread_id,
        name=vow.name,
        thread_type="vow",
        source=source,
        weight=gm().random_events.seeded_list_weight,
        linked_track_id=vow.id,
        active=True,
    )


def swear_background_vow(game: GameState, vow_text: str, rank: str) -> None:
    vow_rank = rank if rank else rules().creation.background_vow_default_rank
    track = new_track(id="vow_background", name=vow_text, track_type="vow", rank=vow_rank)
    game.progress_tracks.append(track)
    game.narrative.threads.append(_vow_thread("thread_background_vow", track, "creation"))
    log(f"[Track] Background vow track: rank={vow_rank}, thread seeded")


def start_bound_vow(game: GameState, name: str, rank: str, impact: str) -> ProgressTrack:
    vow = _add_track(game, f"vow_{_slug(name)}", name, "vow", rank)
    vow.bound_impact = impact
    return vow


def forsake_vow(game: GameState, vow: ProgressTrack, result: OutcomeResult) -> None:
    cfg = rules().suffer.forsake_vow
    by_rank = cfg.cost_by_rank[load_ruleset(game.setting_id).id]
    complete_track(game, vow.id, "failed")
    result.consequences.append(consequence("forsake_vow", vow=vow.name))
    suffer(game, cfg.meter, by_rank[vow.rank] if by_rank is not None else cfg.cost, result)


def _keep_one_box(track: ProgressTrack) -> int:
    return min(track.ticks, rules().progress.ticks_per_box)


def _clear_lowest_die(track: ProgressTrack) -> int:
    die = rules().dice.challenge_die
    lowest = min(random.randint(1, die), random.randint(1, die))
    return max(0, track.ticks - lowest * rules().progress.ticks_per_box)


_RECOMMIT_RULES: dict[str, Callable[[ProgressTrack], int]] = {
    "keep_one_box": _keep_one_box,
    "clear_lowest_die": _clear_lowest_die,
}


def recommit_track(track: ProgressTrack, rule: str, result: OutcomeResult) -> None:
    track.ticks = _RECOMMIT_RULES[rule](track)
    higher = shifted_rank(track.rank, 1)
    if higher is not None:
        track.rank = higher
    result.consequences.append(consequence("recommit", track=track.name))
    log(f"[Track] Recommitted to {track.name}: {filled_boxes(track)} boxes, rank {track.rank}")


def resolve_progress_roll(game: GameState, roll: RollResult, track: ProgressTrack, outcome: OutcomeResult) -> None:
    if roll.result in rules().dice.hit_results:
        bonded = track.track_type in rules().get_raw("tracks_bonded_on_a_hit")
        complete_track(game, track.id, "bonded" if bonded else "completed")
        return
    cfg = move_outcome_config(game, roll.move)
    if "recommit_on_miss" in cfg:
        recommit_track(track, cfg["recommit_on_miss"], outcome)
    else:
        complete_track(game, track.id, "failed")


def apply_progress_and_legacy(
    game: GameState,
    outcome: OutcomeResult,
    brain: BrainResult,
    rolled_track: ProgressTrack | None,
) -> None:
    if outcome.progress_marks > 0:
        track_category = rules().get_raw("progress_mark_categories")[brain.move]
        track = find_progress_track(game, track_category, brain.target_track)
        for _ in range(outcome.progress_marks):
            added = mark_progress(track)
            if added:
                log(f"[Track] {track.name}: +{added} ticks ({filled_boxes(track)}/{rules().progress.boxes} boxes)")

    if outcome.legacy_track and outcome.legacy_fixed_ticks:
        mark_legacy_ticks(game, outcome.legacy_track, outcome.legacy_fixed_ticks)
    elif outcome.legacy_track:
        if rolled_track is None:
            raise ValueError(f"{brain.move}: a legacy reward by rank needs the progress track that was rolled")
        rank = shifted_rank(rolled_track.rank, outcome.legacy_rank_shift)
        if rank is not None:
            mark_legacy(game, outcome.legacy_track, source_rank=rank)

    if outcome.experience_rank_shift is not None:
        if rolled_track is None:
            raise ValueError(f"{brain.move}: experience by rank needs the progress track that was rolled")
        rank = shifted_rank(rolled_track.rank, outcome.experience_rank_shift)
        gained = rules().legacy.experience_by_rank[rank] if rank is not None else 0
        game.campaign.xp += gained
        log(f"[Legacy] Experience +{gained} for a {rolled_track.rank} vow (total {game.campaign.xp})")


def active_tracks(game: GameState) -> list[ProgressTrack]:
    return [t for t in game.progress_tracks if t.status == "active"]


def _vows(game: GameState, status: str) -> list[str]:
    return [t.name for t in game.progress_tracks if t.track_type == "vow" and t.status == status]


def vow_record(game: GameState) -> tuple[list[str], list[str], list[str]]:
    return _vows(game, "completed"), _vows(game, "failed"), _vows(game, "active")


def is_vow_thread(thread: ThreadEntry) -> bool:
    return thread.thread_type == "vow"


def track_category_of_move(game: GameState, move: str) -> str | None:
    ds_move = get_moves(game.setting_id).get(move)
    if ds_move is not None and ds_move.is_progress_roll:
        return ds_move.track_category
    categories: dict[str, str] = rules().get_raw("progress_mark_categories")
    return categories.get(move)


def vow_acted_on(game: GameState, move: str, target_track: str | None) -> ProgressTrack | None:
    category = track_category_of_move(game, move)
    if category is None or rules().get_raw("track_types_by_category")[category] != "vow":
        return None
    if target_track is not None:
        return next(t for t in game.progress_tracks if t.id == target_track)
    vows = [t for t in game.progress_tracks if t.track_type == "vow" and t.status == "active"]
    return vows[0] if len(vows) == 1 else None


def find_progress_track(game: GameState, track_category: str, target_track: str | None) -> ProgressTrack:
    track_type = rules().get_raw("track_types_by_category")[track_category]
    candidates = [t for t in game.progress_tracks if t.track_type == track_type and t.status == "active"]

    if target_track is not None:
        track = next((t for t in candidates if t.id == target_track), None)
        if track is None:
            raise ValueError(f"Target track {target_track!r} is not an active {track_type} track")
        return track

    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        raise ValueError(f"No active {track_type} track")
    names = ", ".join(t.name for t in candidates)
    raise ValueError(f"Multiple active {track_type} tracks: {names}. Brain must set target_track.")


def complete_track(game: GameState, track_id: str, outcome: str) -> None:
    track = next((t for t in game.progress_tracks if t.id == track_id), None)
    if track is None:
        raise KeyError(f"complete_track: no progress track with id {track_id!r}")
    track.status = outcome
    log(f"[Track] {track.name} ({track.track_type}) → {outcome}")

    if track.track_type == "combat" and game.world.combat_position:
        game.world.combat_position = ""
        log("[Track] Combat ended: cleared combat_position")

    if track.track_type == "vow":
        if track.bound_impact and outcome == "completed":
            clear_impact(game, track.bound_impact)

        for thread in game.narrative.threads:
            if thread.linked_track_id == track_id:
                thread.active = False
                log(f"[Track] Linked thread '{thread.name}' deactivated")
                break

        for threat in game.threats:
            if threat.linked_vow_id == track_id and threat.status == "active":
                threat.status = "overcome" if outcome == "completed" else "resolved"
                log(f"[Track] Linked threat '{threat.name}' → {threat.status}")

                if threat.status == "overcome":
                    apply_threat_overcome_bonus(game, threat)
                    _tell_overcome_under_pressure(game, threat)


def _tell_overcome_under_pressure(game: GameState, threat: ThreatData) -> None:
    if menace_boxes(threat) / menace_total_boxes(threat) < rules().threats.menace_high_threshold:
        return
    game.world.pending_threat_events.append(
        ThreatEvent(
            threat_id=threat.id,
            threat_name=threat.name,
            menace_full=False,
            source="overcome_under_pressure",
            development="",
        )
    )


def complete_track_of_clock(game: GameState, clock: ClockData) -> None:
    if clock.clock_type != "progress":
        return
    for track in game.progress_tracks:
        if track.name == clock.name and track.status == "active":
            complete_track(game, track.id, "completed")
            log(f"[ClockFill] linked progress track '{track.name}' completed")
            return
