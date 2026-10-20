from __future__ import annotations

import re
from dataclasses import dataclass

from ..logging_util import log
from ..models import GameState
from ..prompt_loader import get_prompt
from ..setting.oracle_rolls import plain_text
from ..xml_utils import xe as _xe
from .assets import asset_data, enabled_abilities
from .config import rules
from .datasworn import load_ruleset
from .meters import adjust_momentum

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
    cfg = rules().roll_bonuses
    options: list[RollBonus] = []
    for asset_id in [*game.paths, *game.assets]:
        data = asset_data(game, asset_id)
        if data is None:
            continue
        flags = enabled_abilities(game, asset_id)
        for index, (ability, enabled) in enumerate(zip(data["abilities"], flags, strict=True)):
            text = plain_text(str(ability["text"]))
            add = _ADD.search(text)
            if not enabled or add is None:
                continue
            momentum = _MOMENTUM_ON_HIT.search(text)
            options.append(
                RollBonus(
                    id=f"{asset_id}#{index}",
                    source=str(data["name"]),
                    condition=text[: cfg.condition_chars],
                    add=int(add.group(1)),
                    momentum_on_hit=int(momentum.group(1)) if momentum else 0,
                )
            )
    aid = cfg.connection_aid[load_ruleset(game.setting_id).id]
    for track in game.progress_tracks:
        if track.track_type == "connection" and track.status in ("active", "bonded"):
            options.append(
                RollBonus(
                    id=f"connection:{track.id.removeprefix('connection_')}",
                    source=track.name,
                    condition=aid.condition.format(name=track.name),
                    add=aid.bonded_add if track.status == "bonded" else aid.add,
                    momentum_on_hit=aid.momentum_on_hit,
                )
            )
    return options


def chosen_bonus(game: GameState, bonus_id: str | None) -> RollBonus | None:
    if bonus_id is None:
        return None
    for option in roll_bonuses(game):
        if option.id == bonus_id:
            log(f"[Bonus] {option.source}: +{option.add}")
            return option
    raise ValueError(f"Bonus {bonus_id!r} is not on offer")


def apply_momentum_on_hit(game: GameState, bonus: RollBonus, result: str) -> None:
    if bonus.momentum_on_hit and result in rules().dice.hit_results:
        adjust_momentum(game, bonus.momentum_on_hit)
        log(f"[Bonus] {bonus.source}: +{bonus.momentum_on_hit} momentum on a hit")


def bonus_block(game: GameState) -> str:
    options = roll_bonuses(game)
    if not options:
        return ""
    lines = "\n".join(
        get_prompt("brain_bonus_line", id=option.id, source=_xe(option.source), condition=_xe(option.condition))
        for option in options
    )
    return get_prompt("brain_bonuses_wrapper", lines=lines)
