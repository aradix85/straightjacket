from __future__ import annotations

from ..datasworn.settings import active_package
from ..engine_loader import eng
from ..logging_util import log
from .legacy import apply_threat_overcome_bonus
from ..models import GameState, ProgressTrack


def find_progress_track(game: GameState, track_category: str, target_track: str | None = None) -> ProgressTrack | None:
    track_type = eng().get_raw("track_types_by_category")[track_category]
    candidates = [t for t in game.progress_tracks if t.track_type == track_type and t.status == "active"]

    if not candidates:
        return None

    if target_track:
        return next((t for t in candidates if t.id == target_track), None)

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
            if threat.linked_vow_id is None:
                continue
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
    pkg = active_package(game)
    if not pkg:
        return ""
    action, theme = pkg.roll_action_theme()
    if action and theme:
        return f"{action} / {theme}"
    return ""
