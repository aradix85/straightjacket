from __future__ import annotations

import random
import re
from collections.abc import Callable

from ..gamemaster.config import gm
from ..ids import unique_id
from ..logging_util import log
from ..models import BrainResult, ClockData, GameState, ProgressTrack, ThreadEntry, consequence
from ..setting.packages import load_package
from .bond import connection_track, connection_track_id
from .config import rules
from .impacts import clear_impact
from .legacy import apply_threat_overcome_bonus, shifted_rank
from .moves import get_moves
from .outcome_result import OutcomeResult
from .progress import filled_boxes, new_track
from .suffer import suffer


def _slug(name: str) -> str:
    return re.sub(r"\W+", "_", name.lower()).strip("_")


def start_track(game: GameState, brain: BrainResult, result: str) -> None:
    track_type = rules().get_raw("track_creating_moves").get(brain.move)
    if not track_type:
        return
    if result == "MISS" and brain.move in rules().get_raw("tracks_started_on_a_hit"):
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
    _add_track(game, base_id, brain.track_name, track_type, brain.track_rank)


def _add_track(game: GameState, base_id: str, name: str, track_type: str, rank: str) -> ProgressTrack:
    track_id = unique_id(base_id, {t.id for t in game.progress_tracks})
    track = new_track(id=track_id, name=name, track_type=track_type, rank=rank)
    game.progress_tracks.append(track)
    log(f"[Track] Created {track_type} track: {name} ({rank}), id={track_id}")

    if track_type == "vow":
        game.narrative.threads.append(
            ThreadEntry(
                id=unique_id(f"thread_{_slug(name)}", {t.id for t in game.narrative.threads}),
                name=name,
                thread_type="vow",
                weight=gm().random_events.seeded_list_weight,
                source="vow",
                linked_track_id=track_id,
            )
        )
        log(f"[Track] Created linked thread for vow: {name}")
    return track


def start_bound_vow(game: GameState, name: str, rank: str, impact: str) -> ProgressTrack:
    vow = _add_track(game, f"vow_{_slug(name)}", name, "vow", rank)
    vow.bound_impact = impact
    return vow


def forsake_vow(game: GameState, vow: ProgressTrack, result: OutcomeResult) -> None:
    cfg = rules().suffer.forsake_vow
    complete_track(game, vow.id, "failed")
    result.consequences.append(consequence("forsake_vow", vow=vow.name))
    suffer(game, cfg.meter, cfg.cost, result)


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


def track_category_of_move(game: GameState, move: str) -> str | None:
    ds_move = get_moves(game.setting_id).get(move)
    if ds_move is not None and ds_move.roll_type == "progress_roll":
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


def complete_track_of_clock(game: GameState, clock: ClockData) -> None:
    if clock.clock_type != "progress":
        return
    for track in game.progress_tracks:
        if track.name == clock.name and track.status == "active":
            complete_track(game, track.id, "completed")
            log(f"[ClockFill] linked progress track '{track.name}' completed")
            return


def roll_oracle_answer(game: GameState) -> str:
    action, theme = load_package(game.setting_id).roll_action_theme()
    return f"{action} / {theme}"
