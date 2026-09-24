from __future__ import annotations

import re
from dataclasses import dataclass

from ..engine_loader import eng
from ..logging_util import log
from ..models import GameState
from .assets import asset_data, enabled_abilities
from .move_effects import strip_datasworn_links

_ADD = re.compile(r"\badd \+(\d)", re.IGNORECASE)
_MOMENTUM_ON_HIT = re.compile(r"add \+\d and take \+(\d) momentum on a hit", re.IGNORECASE)


@dataclass(frozen=True)
class RollBonus:
    id: str
    source: str
    condition: str
    add: int
    momentum_on_hit: int


def roll_bonuses(game: GameState) -> list[RollBonus]:
    cfg = eng().get_raw("roll_bonuses")
    options: list[RollBonus] = []
    for asset_id in game.assets:
        data = asset_data(game, asset_id)
        if data is None:
            continue
        flags = enabled_abilities(game, asset_id)
        for index, (ability, enabled) in enumerate(zip(data["abilities"], flags, strict=False)):
            text = strip_datasworn_links(str(ability["text"]))
            add = _ADD.search(text)
            if not enabled or add is None:
                continue
            momentum = _MOMENTUM_ON_HIT.search(text)
            options.append(
                RollBonus(
                    id=f"{asset_id}#{index}",
                    source=str(data["name"]),
                    condition=text[: cfg["condition_chars"]],
                    add=int(add.group(1)),
                    momentum_on_hit=int(momentum.group(1)) if momentum else 0,
                )
            )
    aid = cfg["connection_aid"]
    for track in game.progress_tracks:
        if track.track_type == "connection" and track.status == "active":
            options.append(
                RollBonus(
                    id=f"connection:{track.id.removeprefix('connection_')}",
                    source=track.name,
                    condition=aid["condition"].format(name=track.name),
                    add=aid["add"],
                    momentum_on_hit=aid["momentum_on_hit"],
                )
            )
    return options


def chosen_bonus(game: GameState, bonus_id: str | None) -> RollBonus | None:
    if not bonus_id:
        return None
    for option in roll_bonuses(game):
        if option.id == bonus_id:
            log(f"[Bonus] {option.source}: +{option.add}")
            return option
    log(f"[Bonus] Brain chose unknown bonus '{bonus_id}'; ignored", level="warning")
    return None


def apply_momentum_on_hit(game: GameState, bonus: RollBonus, result: str) -> None:
    if bonus.momentum_on_hit and result in ("STRONG_HIT", "WEAK_HIT"):
        _e = eng()
        game.resources.adjust_momentum(bonus.momentum_on_hit, floor=_e.momentum.floor, ceiling=_e.momentum.max)
        log(f"[Bonus] {bonus.source}: +{bonus.momentum_on_hit} momentum on a hit")


def bonus_block(game: GameState) -> str:
    options = roll_bonuses(game)
    if not options:
        return ""
    lines = "\n".join(f"  {option.id}: {option.source}. {option.condition}" for option in options)
    return f"<bonuses>\n{lines}\n</bonuses>"
