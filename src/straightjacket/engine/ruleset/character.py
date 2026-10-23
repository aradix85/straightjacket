from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import GameState
from ..setting.packages import SettingPackage
from .config import rules
from .datasworn import RulesFile, load_ruleset
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


def _path_names(paths: list[str], own: RulesFile) -> list[str]:
    names: list[str] = []
    for pid in paths:
        path = own.asset("path", pid)
        if path is None:
            raise ValueError(f"Path '{pid}' is not among the paths of '{own.datasworn_id}'")
        names.append(path["name"])
    return names


def _validate_assets(assets: list[str], pkg: SettingPackage, own: RulesFile) -> None:
    allowed_cats = set(pkg.creation_flow.starting_asset_categories)
    for asset_id in assets:
        if not any(own.asset(cat, asset_id) for cat in allowed_cats):
            raise ValueError(f"Asset '{asset_id}' not in allowed categories: {allowed_cats}")


def _check_choices(paths: list[str], assets: list[str], ruleset_id: str) -> None:
    creation = rules().creation
    for kind, picks, limit in (
        ("paths", paths, creation.max_paths[ruleset_id]),
        ("starting assets", assets, creation.max_starting_assets[ruleset_id]),
    ):
        if len(picks) > limit:
            raise ValueError(f"Too many {kind}: {len(picks)} (max {limit})")
    chosen = paths + assets
    if len(set(chosen)) < len(chosen):
        raise ValueError(f"An asset is chosen twice: {chosen}")


def make_character(creation_data: dict[str, Any], pkg: SettingPackage) -> Character:
    stats = creation_data["stats"]
    paths = list(creation_data["paths"])
    assets = list(creation_data["assets"])
    background_vow = creation_data["background_vow"]
    vow_rank = creation_data["background_vow_rank"]
    validate_stats(stats, pkg.id)
    ruleset = load_ruleset(pkg.id)
    own = ruleset.setting_file
    _check_choices(paths, assets, ruleset.id)
    _validate_assets(assets, pkg, own)
    paths += [asset_id for asset_id in assets if own.asset("path", asset_id) is not None]
    assets = [asset_id for asset_id in assets if asset_id not in paths]
    path_names = _path_names(paths, own)
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
