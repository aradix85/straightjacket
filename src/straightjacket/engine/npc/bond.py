#!/usr/bin/env python3
"""NPC bond query: reads connection track progress."""

from __future__ import annotations

from ..models import GameState


def get_npc_bond(game: GameState, npc_id: str) -> int:
    """NPC bond level from connection track filled_boxes. 0 if no track."""
    for track in game.progress_tracks:
        if track.track_type == "connection" and track.id == f"connection_{npc_id}" and track.status == "active":
            return track.filled_boxes
    return 0
