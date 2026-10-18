from __future__ import annotations

import re

from ..datasworn.moves import get_moves
from ..datasworn.settings import load_package
from ..engine_loader import eng
from ..ids import unique_id
from ..logging_util import log
from ..npc.bond import connection_track_id
from .impacts import clear_impact
from .legacy import apply_threat_overcome_bonus
from .outcome_result import OutcomeResult
from .suffer import suffer
from ..models import BrainResult, GameState, ProgressTrack, ThreadEntry


def _slug(name: str) -> str:
    return re.sub(r"\W+", "_", name.lower()).strip("_")


def start_track(game: GameState, brain: BrainResult, result: str) -> None:
    track_type = eng().get_raw("track_creating_moves").get(brain.move)
    if not track_type:
        return
    if result == "MISS" and brain.move in eng().get_raw("tracks_started_on_a_hit"):
        log(f"[Track] {brain.move} missed; no {track_type} track")
        return
    if brain.target_track is not None and brain.move in eng().get_raw("progress_mark_categories"):
        log(f"[Track] {brain.move} continues {brain.target_track}; no new {track_type} track")
        return
    assert brain.track_name
    assert brain.track_rank

    if track_type == "connection":
        if brain.target_npc is None:
            log(f"[Track] {brain.move}: its target turned out absent; no connection")
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
    track = ProgressTrack.new(id=track_id, name=name, track_type=track_type, rank=rank)
    game.progress_tracks.append(track)
    log(f"[Track] Created {track_type} track: {name} ({rank}), id={track_id}")

    if track_type == "vow":
        game.narrative.threads.append(
            ThreadEntry(
                id=unique_id(f"thread_{_slug(name)}", {t.id for t in game.narrative.threads}),
                name=name,
                thread_type="vow",
                weight=eng().random_events.seeded_list_weight,
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
    cfg = eng().suffer.forsake_vow
    complete_track(game, vow.id, "failed")
    result.consequences.append(eng().ai_text.consequence_labels["forsake_vow"].format(vow=vow.name))
    suffer(game, cfg.meter, cfg.cost, result)


def track_category_of_move(game: GameState, move: str) -> str | None:
    ds_move = get_moves(game.setting_id).get(move)
    if ds_move is not None and ds_move.roll_type == "progress_roll":
        return ds_move.track_category
    categories: dict[str, str] = eng().get_raw("progress_mark_categories")
    return categories.get(move)


def vow_acted_on(game: GameState, move: str, target_track: str | None) -> ProgressTrack | None:
    category = track_category_of_move(game, move)
    if category is None or eng().get_raw("track_types_by_category")[category] != "vow":
        return None
    if target_track is not None:
        return next(t for t in game.progress_tracks if t.id == target_track)
    vows = [t for t in game.progress_tracks if t.track_type == "vow" and t.status == "active"]
    return vows[0] if len(vows) == 1 else None


def find_progress_track(game: GameState, track_category: str, target_track: str | None) -> ProgressTrack:
    track_type = eng().get_raw("track_types_by_category")[track_category]
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


def roll_oracle_answer(game: GameState) -> str:
    action, theme = load_package(game.setting_id).roll_action_theme()
    return f"{action} / {theme}"
