from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.logging_util import log
from straightjacket.engine.models import consequence
from straightjacket.engine.ruleset.datasworn import load_ruleset
from straightjacket.engine.ruleset.meters import cap_momentum, max_momentum
from straightjacket.engine.serialization import read_key, shaped
from straightjacket.engine.setting.oracle_rolls import plain_text

if TYPE_CHECKING:
    from straightjacket.engine.models import Consequence, GameState


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
        where = f"{rules_file.datasworn_id}.rules.impacts"
        for category in rules_file.rule("impacts").values():
            for key, raw in read_key(category, "contents", dict, where).items():
                impacts[key] = Impact(
                    label=read_key(raw, "label", str, f"{where}.{key}"),
                    prevents_recovery=[
                        shaped(meter, str, f"{where}.{key}.prevents_recovery: expected str")
                        for meter in read_key(raw, "prevents_recovery", list, f"{where}.{key}")
                    ],
                    permanent=read_key(raw, "permanent", bool, f"{where}.{key}"),
                    description=plain_text(read_key(raw, "description", str, f"{where}.{key}")),
                )
    _cache[setting_id] = impacts
    return impacts


def apply_impact(game: GameState, key: str) -> bool:
    if key in game.impacts:
        return False
    impacts = get_impacts(game.setting_id)
    if key not in impacts:
        msg = f"Unknown impact {key!r} in {game.setting_id}; its rules have: {sorted(impacts)}"
        raise KeyError(msg)
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


def impact_consequence(game: GameState, kind: str, key: str) -> Consequence:
    return consequence(kind, impact=impact_label(game, key))
