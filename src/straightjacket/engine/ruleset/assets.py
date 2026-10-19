from __future__ import annotations

from typing import Any

from ..models import GameState
from .datasworn import load_ruleset


def asset_data(game: GameState, asset_id: str) -> dict[str, Any] | None:
    parts = asset_id.split("/")
    key = parts[-1]
    for rules_file in reversed(load_ruleset(game.setting_id).files):
        categories = [parts[-2]] if len(parts) >= 2 else sorted(rules_file.assets)
        for category in categories:
            found = rules_file.asset(category, key)
            if found is not None:
                return found
    return None


def enabled_abilities(game: GameState, asset_id: str) -> list[bool]:
    if asset_id in game.asset_abilities:
        return list(game.asset_abilities[asset_id])
    data = asset_data(game, asset_id)
    if data is None:
        return []
    return [bool(ability.get("enabled")) for ability in data["abilities"]]


def enable_next_ability(game: GameState, asset_id: str) -> None:
    flags = enabled_abilities(game, asset_id)
    flags[flags.index(False)] = True
    game.asset_abilities[asset_id] = flags
