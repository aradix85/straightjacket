from __future__ import annotations

from ..logging_util import log
from ..models import GameState, NpcData, ProgressTrack


def connection_track_id(npc_id: str) -> str:
    return f"connection_{npc_id}"


def connection_track(game: GameState, npc_id: str) -> ProgressTrack | None:
    track_id = connection_track_id(npc_id)
    return next((t for t in game.progress_tracks if t.id == track_id and t.status in ("active", "bonded")), None)


def get_npc_bond(game: GameState, npc_id: str) -> int:
    track = connection_track(game, npc_id)
    return track.filled_boxes if track is not None else 0


def merge_connections(game: GameState, kept: NpcData, merged: NpcData) -> None:
    merged_track = connection_track(game, merged.id)
    if merged_track is None:
        return
    kept_track = connection_track(game, kept.id)
    if kept_track is not None and kept_track.ticks >= merged_track.ticks:
        game.progress_tracks.remove(merged_track)
        return
    if kept_track is not None:
        game.progress_tracks.remove(kept_track)
    merged_track.id = connection_track_id(kept.id)
    merged_track.name = kept.name
    log(f"[NPC] Connection of '{merged.name}' kept for '{kept.name}' ({merged_track.filled_boxes} boxes)")
