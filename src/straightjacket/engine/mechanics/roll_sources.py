from __future__ import annotations

from ..datasworn.moves import Move
from ..models import GameState
from ..npc.bond import connection_track


def _meter_value(game: GameState, meter: str) -> int:
    value: int = getattr(game.resources, meter)
    return value


def best_roll_option(game: GameState, move: Move) -> tuple[str, int]:
    values: dict[str, int] = {}
    for option in (option for condition in move.conditions for option in condition.roll_options):
        if option.using == "stat":
            values[option.stat] = game.stats[option.stat]
        elif option.using == "condition_meter":
            values[option.condition_meter] = _meter_value(game, option.condition_meter)
    best = max(values, key=values.__getitem__)
    return best, values[best]


def roll_source_without_stat(game: GameState, move: Move, target_npc: str | None) -> tuple[str, int] | None:
    options = [option for condition in move.conditions for option in condition.roll_options]
    meters = [option.condition_meter for option in options if option.using == "condition_meter"]
    if meters:
        best = max(meters, key=lambda meter: _meter_value(game, meter))
        return best, _meter_value(game, best)
    ranked = {option.label: option.value for option in options if option.using == "custom" and option.value is not None}
    track = connection_track(game, target_npc) if target_npc is not None else None
    if track is None or track.rank not in ranked:
        return None
    return track.rank, int(ranked[track.rank])
