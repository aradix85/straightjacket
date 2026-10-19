from __future__ import annotations

from ..models import GameState, ProgressTrack


def connection_track_id(npc_id: str) -> str:
    return f"connection_{npc_id}"


def connection_track(game: GameState, npc_id: str) -> ProgressTrack | None:
    track_id = connection_track_id(npc_id)
    return next((t for t in game.progress_tracks if t.id == track_id and t.status in ("active", "bonded")), None)


def get_npc_bond(game: GameState, npc_id: str) -> int:
    track = connection_track(game, npc_id)
    return track.filled_boxes if track is not None else 0
