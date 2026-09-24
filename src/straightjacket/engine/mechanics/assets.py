from __future__ import annotations

from typing import Any

from ..datasworn.settings import SettingPackage, load_package
from ..models import GameState


def asset_data(game: GameState, asset_id: str) -> dict[str, Any] | None:
    parts = asset_id.split("/")
    if len(parts) < 2:
        return None
    category, key = parts[-2], parts[-1]
    package: SettingPackage | None = load_package(game.setting_id)
    while package is not None:
        found = package.data.asset(category, key)
        if found is not None:
            return found
        package = package.parent
    return None


def enabled_abilities(game: GameState, asset_id: str) -> list[bool]:
    if asset_id in game.asset_abilities:
        return list(game.asset_abilities[asset_id])
    data = asset_data(game, asset_id)
    if data is None:
        return []
    return [bool(ability.get("enabled")) for ability in data["abilities"]]


def enable_next_ability(game: GameState, asset_id: str) -> bool:
    flags = enabled_abilities(game, asset_id)
    if all(flags):
        return False
    flags[flags.index(False)] = True
    game.asset_abilities[asset_id] = flags
    return True
