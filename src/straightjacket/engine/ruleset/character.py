from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import GameState
from ..setting.packages import SettingPackage
from .config import rules
from .progress import ranks
from .stats import stat_descriptions, validate_stats
from .tracks import swear_background_vow


@dataclass(frozen=True)
class Character:
    stats: dict[str, int]
    paths: list[str]
    concept: str
    assets: list[str]
    background_vow: str
    background_vow_rank: str


def _path_names(paths: list[str], pkg: SettingPackage) -> list[str]:
    max_paths = rules().creation.max_paths
    if len(paths) > max_paths:
        raise ValueError(f"Too many paths: {len(paths)} (max {max_paths})")
    names: list[str] = []
    for pid in paths:
        path = pkg.data.asset("path", pid)
        if path is None:
            raise ValueError(f"Path '{pid}' not found in setting '{pkg.id}'")
        names.append(path["name"])
    return names


def _validate_assets(assets: list[str], pkg: SettingPackage) -> None:
    max_assets = rules().creation.max_starting_assets
    if len(assets) > max_assets:
        raise ValueError(f"Too many starting assets: {len(assets)} (max {max_assets})")
    allowed_cats = set(pkg.creation_flow.starting_asset_categories)
    for asset_id in assets:
        if not any(pkg.data.asset(cat, asset_id) for cat in allowed_cats):
            raise ValueError(f"Asset '{asset_id}' not in allowed categories: {allowed_cats}")


def make_character(creation_data: dict[str, Any], pkg: SettingPackage) -> Character:
    stats = creation_data["stats"]
    paths = list(creation_data["paths"])
    assets = list(creation_data["assets"])
    background_vow = creation_data["background_vow"]
    vow_rank = creation_data["background_vow_rank"]
    validate_stats(stats, pkg.id)
    path_names = _path_names(paths, pkg)
    _validate_assets(assets, pkg)
    if not background_vow:
        raise ValueError("creation_data['background_vow'] is empty. The background vow becomes the first vow track.")
    if vow_rank and vow_rank not in ranks():
        raise ValueError(f"Invalid vow rank: '{vow_rank}' (valid: {ranks()})")
    return Character(
        stats={n: stats[n] for n in stat_descriptions(pkg.id)},
        paths=paths,
        concept=", ".join(path_names),
        assets=assets,
        background_vow=background_vow,
        background_vow_rank=vow_rank,
    )


def give_character(game: GameState, character: Character) -> None:
    game.stats = dict(character.stats)
    game.paths = list(character.paths)
    game.character_concept = character.concept
    game.assets = list(character.assets)
    game.background_vow = character.background_vow
    swear_background_vow(game, character.background_vow, character.background_vow_rank)
