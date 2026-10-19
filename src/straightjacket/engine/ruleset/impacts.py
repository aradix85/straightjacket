from __future__ import annotations

from dataclasses import dataclass

from ..logging_util import log
from ..models import GameState
from ..setting.oracle_rolls import plain_text
from ..setting.packages import load_package
from .config import rules


@dataclass(frozen=True)
class Impact:
    label: str
    prevents_recovery: list[str]
    permanent: bool
    description: str


_cache: dict[str, dict[str, Impact]] = {}


def get_impacts(setting_id: str) -> dict[str, Impact]:
    if setting_id in _cache:
        return _cache[setting_id]
    impacts: dict[str, Impact] = {}
    for pkg in reversed(list(load_package(setting_id).chain())):
        for category in (pkg.data.raw["rules"].get("impacts") or {}).values():
            for key, raw in category["contents"].items():
                impacts[key] = Impact(
                    label=raw["label"],
                    prevents_recovery=list(raw["prevents_recovery"]),
                    permanent=raw["permanent"],
                    description=plain_text(raw["description"]),
                )
    _cache[setting_id] = impacts
    return impacts


def recalc_max_momentum(game: GameState) -> None:
    base_max = rules().momentum.max
    new_max = max(0, base_max - len(game.impacts))
    game.resources.max_momentum = new_max
    if game.resources.momentum > new_max:
        game.resources.momentum = new_max


def apply_impact(game: GameState, key: str) -> bool:
    if key in game.impacts:
        return False
    impacts = get_impacts(game.setting_id)
    if key not in impacts:
        raise KeyError(f"Unknown impact {key!r} in {game.setting_id}; its rules have: {sorted(impacts)}")
    game.impacts.append(key)
    recalc_max_momentum(game)
    log(f"[Impact] {key} applied — max_momentum → {game.resources.max_momentum}")
    return True


def clear_impact(game: GameState, key: str) -> bool:
    if key not in game.impacts:
        return False
    if get_impacts(game.setting_id)[key].permanent:
        log(f"[Impact] Cannot clear permanent impact: {key}")
        return False
    game.impacts.remove(key)
    recalc_max_momentum(game)
    log(f"[Impact] {key} cleared — max_momentum → {game.resources.max_momentum}")
    return True


def blocks_recovery(game: GameState, track: str) -> str:
    impacts = get_impacts(game.setting_id)
    for key in game.impacts:
        if track in impacts[key].prevents_recovery:
            return key
    return ""


def impact_label(game: GameState, key: str) -> str:
    return get_impacts(game.setting_id)[key].label
