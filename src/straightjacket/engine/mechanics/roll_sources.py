from __future__ import annotations

from ..datasworn.moves import Move
from ..models import GameState


def _meter_value(game: GameState, meter: str) -> int:
    value: int = getattr(game.resources, meter)
    return value


def roll_source_without_stat(game: GameState, move: Move, target_npc: str | None) -> tuple[str, int] | None:
    options = [option for condition in move.conditions for option in condition.roll_options]
    meters = [option.condition_meter for option in options if option.using == "condition_meter"]
    if meters:
        best = max(meters, key=lambda meter: _meter_value(game, meter))
        return best, _meter_value(game, best)
    ranked = {option.label: option.value for option in options if option.using == "custom" and option.value is not None}
    track = next(
        (
            t
            for t in game.progress_tracks
            if t.track_type == "connection" and t.id == f"connection_{target_npc}" and t.status == "active"
        ),
        None,
    )
    if track is None or track.rank not in ranked:
        return None
    return track.rank, int(ranked[track.rank])
