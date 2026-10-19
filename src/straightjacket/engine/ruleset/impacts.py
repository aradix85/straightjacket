from __future__ import annotations

from dataclasses import dataclass

from ..logging_util import log
from ..models import GameState
from ..setting.oracle_rolls import plain_text
from .datasworn import load_ruleset
from .meters import cap_momentum, max_momentum


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
    for rules_file in load_ruleset(setting_id).files:
        for category in (rules_file.rules.get("impacts") or {}).values():
            for key, raw in category["contents"].items():
                impacts[key] = Impact(
                    label=raw["label"],
                    prevents_recovery=list(raw["prevents_recovery"]),
                    permanent=raw["permanent"],
                    description=plain_text(raw["description"]),
                )
    _cache[setting_id] = impacts
    return impacts


def apply_impact(game: GameState, key: str) -> bool:
    if key in game.impacts:
        return False
    impacts = get_impacts(game.setting_id)
    if key not in impacts:
        raise KeyError(f"Unknown impact {key!r} in {game.setting_id}; its rules have: {sorted(impacts)}")
    game.impacts.append(key)
    cap_momentum(game)
    log(f"[Impact] {key} applied — max momentum → {max_momentum(game)}")
    return True


def clear_impact(game: GameState, key: str) -> bool:
    if key not in game.impacts:
        return False
    if get_impacts(game.setting_id)[key].permanent:
        log(f"[Impact] Cannot clear permanent impact: {key}")
        return False
    game.impacts.remove(key)
    log(f"[Impact] {key} cleared — max momentum → {max_momentum(game)}")
    return True


def blocks_recovery(game: GameState, track: str) -> str:
    impacts = get_impacts(game.setting_id)
    for key in game.impacts:
        if track in impacts[key].prevents_recovery:
            return key
    return ""


def impact_label(game: GameState, key: str) -> str:
    return get_impacts(game.setting_id)[key].label
