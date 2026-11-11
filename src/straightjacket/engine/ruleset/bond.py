from __future__ import annotations

from typing import TYPE_CHECKING

from straightjacket.engine.logging_util import log
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.progress import filled_boxes, new_track, ranks

if TYPE_CHECKING:
    from straightjacket.engine.models import GameState, NpcData, ProgressTrack


def connection_track_id(npc_id: str) -> str:
    return f"connection_{npc_id}"


def starts_a_connection(move: str) -> bool:
    return rules().track_creating_moves.get(move) == "connection"


def is_bonded(track: ProgressTrack) -> bool:
    return track.status == "bonded"


def bonded_tracks(game: GameState) -> list[ProgressTrack]:
    return [t for t in game.progress_tracks if is_bonded(t)]


def connection_track(game: GameState, npc_id: str) -> ProgressTrack | None:
    track_id = connection_track_id(npc_id)
    return next((t for t in game.progress_tracks if t.id == track_id and t.status in {"active", "bonded"}), None)


def seal_bond(game: GameState, npc: NpcData) -> ProgressTrack:
    track = connection_track(game, npc.id)
    if track is None:
        track = new_track(
            track_id=connection_track_id(npc.id), name=npc.name, track_type="connection", rank=ranks()[-1]
        )
        game.progress_tracks.append(track)
    track.status = "bonded"
    track.ticks = track.max_ticks
    return track


def get_npc_bond(game: GameState, npc_id: str) -> int:
    track = connection_track(game, npc_id)
    return filled_boxes(track) if track is not None else 0


def merge_connections(game: GameState, kept: NpcData, merged: NpcData) -> None:
    for track in game.progress_tracks:
        if track.vowed_to == merged.id:
            track.vowed_to = kept.id
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
    log(f"[NPC] Connection of '{merged.name}' kept for '{kept.name}' ({filled_boxes(merged_track)} boxes)")
