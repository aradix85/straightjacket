"""Progress track mechanics: find, complete, sync, oracle rolls.

Extracted from turn.py. These are game mechanics, not turn pipeline logic.
"""

from __future__ import annotations

from ..datasworn.settings import active_package
from ..logging_util import log
from ..mechanics.legacy import apply_threat_overcome_bonus
from ..models import GameState, ProgressTrack


def find_progress_track(game: GameState, track_category: str, target_track: str | None = None) -> ProgressTrack | None:
    """Find the active progress track for a progress move.

    If target_track is given, matches by name substring (case-insensitive).
    If omitted and multiple active tracks of the type exist, raises ValueError.
    Filters out completed/failed tracks.
    """
    cat_lower = track_category.lower()
    type_map = {
        "vow": "vow",
        "connection": "connection",
        "combat": "combat",
        "expedition": "expedition",
        "delve": "delve",
        "scene challenge": "scene_challenge",
    }
    track_type = type_map.get(cat_lower, cat_lower)

    candidates = [t for t in game.progress_tracks if t.track_type == track_type and t.status == "active"]

    if not candidates:
        return None

    if target_track:
        target_lower = target_track.lower()
        matches = [t for t in candidates if target_lower in t.name.lower()]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(t.name for t in matches)
            raise ValueError(f"Ambiguous target_track '{target_track}' matches: {names}")
        return None

    if len(candidates) == 1:
        return candidates[0]

    names = ", ".join(t.name for t in candidates)
    raise ValueError(f"Multiple active {track_type} tracks: {names}. Brain must set target_track.")


def complete_track(game: GameState, track_id: str, outcome: str) -> None:
    """Mark a track as completed or failed. Handles side effects:
    - Combat tracks: clear combat_position
    - Vow tracks: deactivate linked thread, resolve linked threat
    """
    track = next((t for t in game.progress_tracks if t.id == track_id), None)
    if not track:
        log(f"[Track] complete_track: not found {track_id}")
        return
    track.status = outcome  # "completed" or "failed"
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
        # Resolve linked threat when vow completes or fails
        for threat in game.threats:
            if threat.linked_vow_id == track_id and threat.status == "active":
                threat.status = "overcome" if outcome == "completed" else "resolved"
                log(f"[Track] Linked threat '{threat.name}' → {threat.status}")
                # Step 12.2: XP bonus when vow completes with high-menace threat overcome
                if threat.status == "overcome":
                    apply_threat_overcome_bonus(game, threat)


def sync_combat_tracks(game: GameState) -> None:
    """Remove orphaned combat tracks when combat_position has been cleared.

    Called after post-narration processing. If combat ended via narrative
    (metadata extractor cleared combat_position) but the combat track is
    still active, the engine removes it.
    """
    if game.world.combat_position:
        return
    for track in game.progress_tracks:
        if track.track_type == "combat" and track.status == "active":
            track.status = "failed"
            log(f"[Track] Orphaned combat track '{track.name}' removed (combat_position cleared)")


def roll_oracle_answer(game: GameState) -> str:
    """Roll an oracle answer for ask_the_oracle moves. Returns a meaning pair string."""

    pkg = active_package(game)
    if not pkg:
        return ""
    action, theme = pkg.roll_action_theme()
    if action and theme:
        return f"{action} / {theme}"
    return ""
