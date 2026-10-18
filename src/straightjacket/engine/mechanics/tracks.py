from __future__ import annotations

from ..datasworn.moves import get_moves
from ..datasworn.settings import load_package
from ..engine_loader import eng
from ..logging_util import log
from .legacy import apply_threat_overcome_bonus
from ..models import GameState, ProgressTrack


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


def find_progress_track(game: GameState, track_category: str, target_track: str | None = None) -> ProgressTrack | None:
    track_type = eng().get_raw("track_types_by_category")[track_category]
    candidates = [t for t in game.progress_tracks if t.track_type == track_type and t.status == "active"]

    if not candidates:
        return None

    if target_track:
        track = next((t for t in candidates if t.id == target_track), None)
        if track is None:
            raise ValueError(f"Target track {target_track!r} is not an active {track_type} track")
        return track

    if len(candidates) == 1:
        return candidates[0]

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


def sync_combat_tracks(game: GameState) -> None:
    if game.world.combat_position:
        return
    for track in game.progress_tracks:
        if track.track_type == "combat" and track.status == "active":
            track.status = "failed"
            log(f"[Track] Orphaned combat track '{track.name}' removed (combat_position cleared)")


def roll_oracle_answer(game: GameState) -> str:
    action, theme = load_package(game.setting_id).roll_action_theme()
    return f"{action} / {theme}"
