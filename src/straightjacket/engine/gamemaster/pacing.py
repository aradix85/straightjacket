from __future__ import annotations

from ..models import GameState
from .config import gm


def get_pacing_hint(game: GameState) -> str:
    history = game.narrative.scene_intensity_history[-gm().pacing.window_size :]
    if not history:
        return "neutral"

    consecutive_intense = 0
    for h in reversed(history):
        if h in gm().pacing.intense_scene_types:
            consecutive_intense += 1
        else:
            break
    if consecutive_intense >= gm().pacing.intense_threshold:
        return "breather"

    consecutive_calm = 0
    for h in reversed(history):
        if h == "breather":
            consecutive_calm += 1
        else:
            break
    if consecutive_calm >= gm().pacing.calm_threshold:
        return "action"
    return "neutral"


def record_scene_intensity(game: GameState, scene_type: str) -> None:
    window = gm().pacing.window_size
    game.narrative.scene_intensity_history.append(scene_type)
    if len(game.narrative.scene_intensity_history) > window:
        game.narrative.scene_intensity_history = game.narrative.scene_intensity_history[-window:]
