from __future__ import annotations

import random as _random

from straightjacket.engine.gamemaster.config import gm
from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.datasworn import load_ruleset
from straightjacket.engine.ruleset.stats import stat_descriptions, validate_stats
from straightjacket.engine.setting.packages import SettingPackage, load_package


def roll_character(setting_id: str, game_cfg: dict) -> dict:
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

    path_display = []
    for pid in paths:
        asset = load_ruleset(setting_id).setting_file.asset("path", pid)
        if asset:
            path_display.append(asset["name"])

    print(f"[CREATION] Setting: {pkg.title}")
    print(f"[CREATION] Name: {name} ({pronouns})")
    print(f"[CREATION] Paths: {', '.join(path_display) or paths}")
    if backstory:
        print(f"[CREATION] Backstory: {backstory[:80]}")
    print(f"[CREATION] Vow: {vow} (rank: {vow_rank})")
    if vow_subject:
        print(f"[CREATION] Vow subject: {vow_subject}")
    print(f"[CREATION] Stats: {stats}")
    if truths:
        print(f"[CREATION] Truths: {len(truths)} selected")
    if assets:
        print(f"[CREATION] Starting assets: {assets}")

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


def _roll_name(pkg: SettingPackage, game_cfg: dict) -> str:
    if game_cfg.get("player_name"):
        return game_cfg["player_name"]
    tables = list(pkg.name_tables(gm().naming.category).values())[:2]
    return " ".join(table.roll().text for table in tables)


def _roll_paths(pkg: SettingPackage, game_cfg: dict) -> list[str]:
    max_paths = rules().creation.max_paths
    if game_cfg.get("paths") and len(game_cfg["paths"]) == max_paths:
        return game_cfg["paths"]
    all_paths = load_ruleset(pkg.id).setting_file.assets_of("path")
    path_ids = [p.get("_id", "").rsplit("/", 1)[-1] for p in all_paths if p.get("_id")]
    return _random.sample(path_ids, min(max_paths, len(path_ids)))


def _roll_backstory(pkg: SettingPackage, game_cfg: dict) -> str:
    if game_cfg.get("backstory"):
        return game_cfg["backstory"]
    if pkg.creation_flow.has_backstory_oracle:
        return pkg.oracle_table(pkg.oracle_paths.backstory).roll().text
    return ""


def _roll_vow(pkg: SettingPackage, game_cfg: dict) -> str:
    if game_cfg.get("background_vow"):
        return game_cfg["background_vow"]
    try:
        action, theme = pkg.roll_action_theme()
        return f"{action} {theme}".strip()
    except Exception:
        return "Survive"


def _roll_stats(setting_id: str, game_cfg: dict) -> dict[str, int]:
    cfg_stats = game_cfg.get("stats")
    if cfg_stats:
        validate_stats(cfg_stats, setting_id)
        return cfg_stats
    array = list(rules().stats.creation_array)
    _random.shuffle(array)
    return dict(zip(stat_descriptions(setting_id), array, strict=True))


def _roll_truths(pkg: SettingPackage, game_cfg: dict) -> dict[str, str]:
    if game_cfg.get("truths"):
        return game_cfg["truths"]
    flow = pkg.creation_flow
    if not flow.has_truths:
        return {}
    raw_truths = pkg.data.truths()
    if not raw_truths:
        return {}
    result = {}
    for truth_id, truth_data in raw_truths.items():
        options = truth_data.get("options", [])
        if options:
            chosen = _random.choice(options)
            text = chosen["summary"] if "summary" in chosen else chosen["description"]
            result[truth_id] = text
    return result


def _roll_starting_assets(pkg: SettingPackage, game_cfg: dict) -> list[str]:
    if game_cfg.get("assets"):
        return game_cfg["assets"]
    flow = pkg.creation_flow
    cats = flow.starting_asset_categories
    if not cats:
        return []
    max_assets = rules().creation.max_starting_assets
    available = []
    for cat in cats:
        for asset in load_ruleset(pkg.id).setting_file.assets_of(cat):
            asset_id = asset.get("_id", "").rsplit("/", 1)[-1]
            if asset_id:
                available.append(asset_id)
    if not available:
        return []
    return _random.sample(available, min(max_assets, len(available)))
