from __future__ import annotations

from dataclasses import dataclass

from ..logging_util import log
from ..models import GameState, Resources
from ..setting.packages import load_package
from .config import rules

_MOMENTUM = "momentum"


@dataclass(frozen=True)
class ConditionMeter:
    min: int
    max: int
    start: int


_cache: dict[str, dict[str, ConditionMeter]] = {}


def condition_meters(setting_id: str) -> dict[str, ConditionMeter]:
    if setting_id in _cache:
        return _cache[setting_id]
    meters: dict[str, ConditionMeter] = {}
    for pkg in reversed(list(load_package(setting_id).chain())):
        for key, raw in (pkg.data.raw["rules"].get("condition_meters") or {}).items():
            meters[key] = ConditionMeter(min=raw["min"], max=raw["max"], start=raw["value"])
    _cache[setting_id] = meters
    return meters


def starting_resources(setting_id: str) -> Resources:
    meters = {key: meter.start for key, meter in condition_meters(setting_id).items()}
    meters[_MOMENTUM] = rules().momentum.start
    return Resources(meters=meters, next_move_bonus=0)


def is_condition_meter(game: GameState, name: str) -> bool:
    return name in condition_meters(game.setting_id)


def lose(game: GameState, meter: str, amount: int) -> int:
    old = game.resources.meters[meter]
    new = max(condition_meters(game.setting_id)[meter].min, old - amount)
    game.resources.meters[meter] = new
    if new != old:
        log(f"[Meters] {meter} -{old - new} ({old}→{new})")
    return old - new


def gain(game: GameState, meter: str, amount: int) -> int:
    old = game.resources.meters[meter]
    new = min(condition_meters(game.setting_id)[meter].max, old + amount)
    game.resources.meters[meter] = new
    if new != old:
        log(f"[Meters] {meter} +{new - old} ({old}→{new})")
    return new - old


def in_crisis(game: GameState) -> bool:
    return any(game.resources.meters[meter] <= 0 for meter in rules().meters.crisis_at_zero)


def is_momentum(name: str) -> bool:
    return name == _MOMENTUM


def momentum(game: GameState) -> int:
    return game.resources.meters[_MOMENTUM]


def max_momentum(game: GameState) -> int:
    return max(0, rules().momentum.max - len(game.impacts))


def _set_momentum(game: GameState, value: int, why: str) -> None:
    old = momentum(game)
    game.resources.meters[_MOMENTUM] = value
    if value != old:
        log(f"[Meters] momentum {why} ({old}→{value})")


def adjust_momentum(game: GameState, delta: int) -> None:
    value = max(rules().momentum.floor, min(max_momentum(game), momentum(game) + delta))
    _set_momentum(game, value, f"{'+' if delta > 0 else ''}{delta}")


def cap_momentum(game: GameState) -> None:
    if momentum(game) > max_momentum(game):
        _set_momentum(game, max_momentum(game), "capped")


def reset_momentum(game: GameState) -> None:
    cfg = rules().momentum
    _set_momentum(game, max(cfg.reset_floor, cfg.start - (cfg.max - max_momentum(game))), "burned")
