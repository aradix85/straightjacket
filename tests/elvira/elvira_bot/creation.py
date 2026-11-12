from __future__ import annotations

import random as _random
from typing import TYPE_CHECKING, Any

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.datasworn import load_ruleset
from straightjacket.engine.ruleset.stats import stat_descriptions, validate_stats
from straightjacket.engine.setting.packages import load_package
from tests.elvira.elvira_bot.console import say

if TYPE_CHECKING:
    from straightjacket.engine.setting.packages import SettingPackage


def roll_character(setting_id: str, game_cfg: dict[str, Any]) -> dict[str, Any]:
    pkg = load_package(setting_id)

    name = _roll_name(pkg, game_cfg)
    pronouns = game_cfg.get("pronouns") or _random.choice(rules().creation.pronoun_options)
    paths = _roll_paths(pkg, game_cfg)
    backstory = _roll_backstory(pkg, game_cfg)
    vow = _roll_vow(pkg, game_cfg)
    stats = _roll_stats(setting_id, game_cfg)
    truths = _roll_truths(pkg, game_cfg)
    assets = _roll_starting_assets(pkg, game_cfg)
    vow_rank = game_cfg.get("background_vow_rank", rules().creation.background_vow_default_rank)
    vow_subject = game_cfg.get("vow_subject", "")

    say(f"[CREATION] Setting: {pkg.title}")
    say(f"[CREATION] Name: {name} ({pronouns})")
    say(f"[CREATION] Paths: {paths}")
    if backstory:
        say(f"[CREATION] Backstory: {backstory[:80]}")
    say(f"[CREATION] Vow: {vow} (rank: {vow_rank})")
    if vow_subject:
        say(f"[CREATION] Vow subject: {vow_subject}")
    say(f"[CREATION] Stats: {stats}")
    if truths:
        say(f"[CREATION] Truths: {len(truths)} selected")
    if assets:
        say(f"[CREATION] Starting assets: {assets}")

    return {
        "setting_id": setting_id,
        "tone": pkg.default_tone,
        "player_name": name,
        "pronouns": pronouns,
        "paths": paths,
        "backstory": backstory,
        "background_vow": vow,
        "background_vow_rank": vow_rank,
        "vow_subject": vow_subject,
        "stats": stats,
        "assets": assets,
        "truths": truths,
        "wishes": game_cfg.get("wishes", ""),
        "content_lines": game_cfg.get("content_lines", ""),
    }


def _roll_name(pkg: SettingPackage, game_cfg: dict[str, Any]) -> str:
    if game_cfg.get("player_name"):
        name: str = game_cfg["player_name"]
        return name
    tables = list(pkg.name_tables(gm().naming.category).values())[:2]
    return " ".join(table.roll().text for table in tables)


def _asset_ids(pkg: SettingPackage, categories: list[str]) -> list[str]:
    own = load_ruleset(pkg.id).setting_file
    return [asset.id.rsplit("/", 1)[-1] for cat in categories for asset in own.assets_of(cat)]


def _roll_paths(pkg: SettingPackage, game_cfg: dict[str, Any]) -> list[str]:
    max_paths = rules().creation.max_paths[load_ruleset(pkg.id).id]
    if game_cfg.get("paths") and len(game_cfg["paths"]) == max_paths:
        paths: list[str] = game_cfg["paths"]
        return paths
    path_ids = _asset_ids(pkg, ["path"])
    return _random.sample(path_ids, min(max_paths, len(path_ids)))


def _roll_backstory(pkg: SettingPackage, game_cfg: dict[str, Any]) -> str:
    if game_cfg.get("backstory"):
        backstory: str = game_cfg["backstory"]
        return backstory
    if pkg.creation_flow.has_backstory_oracle:
        return pkg.oracle_table(pkg.oracle_paths.backstory).roll().text
    return ""


def _roll_vow(pkg: SettingPackage, game_cfg: dict[str, Any]) -> str:
    if game_cfg.get("background_vow"):
        vow: str = game_cfg["background_vow"]
        return vow
    action, theme = pkg.roll_action_theme()
    return f"{action} {theme}".strip()


def _roll_stats(setting_id: str, game_cfg: dict[str, Any]) -> dict[str, int]:
    cfg_stats: dict[str, int] | None = game_cfg.get("stats")
    if cfg_stats:
        validate_stats(cfg_stats, setting_id)
        return cfg_stats
    array = list(rules().stats.creation_array)
    _random.shuffle(array)
    return dict(zip(stat_descriptions(setting_id), array, strict=True))


def _roll_truths(pkg: SettingPackage, game_cfg: dict[str, Any]) -> dict[str, str]:
    if game_cfg.get("truths"):
        truths: dict[str, str] = game_cfg["truths"]
        return truths
    if not pkg.creation_flow.has_truths:
        return {}
    result = {}
    for truth_id, truth in pkg.data.truths().items():
        result[truth_id] = _random.choice(truth.options).summary
    return result


def _roll_starting_assets(pkg: SettingPackage, game_cfg: dict[str, Any]) -> list[str]:
    if game_cfg.get("assets"):
        assets: list[str] = game_cfg["assets"]
        return assets
    max_assets = rules().creation.max_starting_assets[load_ruleset(pkg.id).id]
    available = _asset_ids(pkg, pkg.creation_flow.starting_asset_categories)
    return _random.sample(available, min(max_assets, len(available)))
