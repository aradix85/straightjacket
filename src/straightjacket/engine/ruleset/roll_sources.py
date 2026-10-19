from __future__ import annotations

from ..models import GameState
from .bond import connection_track
from .moves import PICK_METHODS, Move, TriggerCondition


def _meter_value(game: GameState, meter: str) -> int:
    value: int = getattr(game.resources, meter)
    return value


def _option_values(game: GameState, condition: TriggerCondition) -> dict[str, int]:
    values: dict[str, int] = {}
    for option in condition.roll_options:
        if option.using == "stat":
            values[option.stat] = game.stats[option.stat]
        elif option.using == "condition_meter":
            values[option.condition_meter] = _meter_value(game, option.condition_meter)
    return values


def best_roll_option(game: GameState, move: Move) -> tuple[str, int]:
    picks: list[tuple[str, int]] = []
    for condition in move.conditions:
        values = _option_values(game, condition)
        if values:
            pick = PICK_METHODS[condition.method] if condition.method in PICK_METHODS else PICK_METHODS["highest"]
            name = pick(values)
            picks.append((name, values[name]))
    return max(picks, key=lambda p: p[1])


def roll_by_method(game: GameState, move: Move, method: str) -> tuple[str, int]:
    condition = next(c for c in move.conditions if c.method == method)
    values = _option_values(game, condition)
    name = PICK_METHODS[method](values)
    return name, values[name]


def roll_source_without_stat(game: GameState, move: Move, target_npc: str | None) -> tuple[str, int] | None:
    options = [option for condition in move.conditions for option in condition.roll_options]
    meters = [option.condition_meter for option in options if option.using == "condition_meter"]
    if meters:
        best = max(meters, key=lambda meter: _meter_value(game, meter))
        return best, _meter_value(game, best)
    ranked = {option.label: option.value for option in options if option.using == "custom" and option.value is not None}
    track = connection_track(game, target_npc) if target_npc is not None else None
    if track is None or track.status != "bonded" or track.rank not in ranked:
        return None
    return track.rank, int(ranked[track.rank])
