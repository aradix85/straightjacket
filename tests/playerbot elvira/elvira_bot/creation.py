"""Datasworn-driven character creation. Fully deterministic — no AI call."""

from __future__ import annotations

import random as _random

from straightjacket.engine.datasworn.loader import extract_title
from straightjacket.engine.datasworn.settings import SettingPackage, load_package
from straightjacket.engine.engine_loader import eng

STAT_NAMES = ["edge", "heart", "iron", "shadow", "wits"]


def roll_character(setting_id: str = "starforged", game_cfg: dict | None = None) -> dict:
    """Build creation_data from Datasworn oracles.

    Returns a dict matching start_new_game's expected creation_data.
    """
    game_cfg = game_cfg or {}
    pkg = load_package(setting_id)
    _e = eng()

    name = _roll_name(pkg, game_cfg)
    pronouns = game_cfg.get("pronouns") or _random.choice(["he/him", "she/her", "they/them"])
    paths = _roll_paths(pkg, game_cfg)
    backstory = _roll_backstory(pkg, game_cfg)
    vow = _roll_vow(pkg, game_cfg)
    stats = _roll_stats(game_cfg)
    truths = _roll_truths(pkg, game_cfg)
    assets = _roll_starting_assets(pkg, game_cfg)
    vow_rank = game_cfg.get("background_vow_rank", _e.creation.background_vow_default_rank)
    vow_subject = game_cfg.get("vow_subject", "")

    path_display = []
    for pid in paths:
        asset = pkg.data.asset("path", pid)
        if asset:
            path_display.append(extract_title(asset, pid))

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
    name_paths = pkg.oracle_paths.get("names", [])
    import contextlib

    parts = []
    for np in name_paths[:2]:
        with contextlib.suppress(KeyError):
            parts.append(pkg.data.roll_oracle(np))
    return " ".join(parts) if parts else f"Wanderer-{_random.randint(100, 999)}"


def _roll_paths(pkg: SettingPackage, game_cfg: dict) -> list[str]:
    if game_cfg.get("paths") and len(game_cfg["paths"]) == 2:
        return game_cfg["paths"]
    all_paths = pkg.data.paths()
    path_ids = [p.get("_id", "").rsplit("/", 1)[-1] for p in all_paths if p.get("_id")]
    if len(path_ids) >= 2:
        return _random.sample(path_ids, 2)
    return path_ids[:2]


def _roll_backstory(pkg: SettingPackage, game_cfg: dict) -> str:
    if game_cfg.get("backstory"):
        return game_cfg["backstory"]
    try:
        table = pkg.data.backstory_prompts()
        if table:
            return table.roll().text
    except Exception:
        pass
    return ""


def _roll_vow(pkg: SettingPackage, game_cfg: dict) -> str:
    if game_cfg.get("background_vow"):
        return game_cfg["background_vow"]
    try:
        action, theme = pkg.roll_action_theme()
        return f"{action} {theme}".strip()
    except Exception:
        return "Survive"


def _roll_stats(game_cfg: dict) -> dict[str, int]:
    _e = eng()
    target = _e.stats.target_sum
    valid_arrays = [list(a) for a in _e.stats.valid_arrays]
    cfg_stats = game_cfg.get("stats")
    if cfg_stats and sum(cfg_stats.values()) == target and sorted(cfg_stats.values(), reverse=True) in valid_arrays:
        return cfg_stats
    return _random_stats(target, valid_arrays)


def _random_stats(target: int, valid_arrays: list[list[int]]) -> dict[str, int]:
    """Generate a random valid stat allocation from valid_arrays."""
    if not valid_arrays:
        raise RuntimeError("No valid stat arrays configured in engine.yaml")
    # Pick a random valid array and shuffle it across stat names
    array = list(_random.choice(valid_arrays))
    _random.shuffle(array)
    return dict(zip(STAT_NAMES, array, strict=True))


def _roll_truths(pkg: SettingPackage, game_cfg: dict) -> dict[str, str]:
    """Roll truths for this setting. Returns {truth_id: chosen_summary}."""
    if game_cfg.get("truths"):
        return game_cfg["truths"]
    flow = pkg.creation_flow
    if not flow.get("has_truths"):
        return {}
    raw_truths = pkg.data.truths()
    if not raw_truths:
        return {}
    result = {}
    for truth_id, truth_data in raw_truths.items():
        options = truth_data.get("options", [])
        if options:
            chosen = _random.choice(options)
            result[truth_id] = chosen.get("summary", "")
    return result


def _roll_starting_assets(pkg: SettingPackage, game_cfg: dict) -> list[str]:
    """Roll one starting asset from allowed categories."""
    if game_cfg.get("assets"):
        return game_cfg["assets"]
    _e = eng()
    flow = pkg.creation_flow
    cats = flow.get("starting_asset_categories", [])
    if not cats:
        return []
    max_assets = _e.creation.max_starting_assets
    available = []
    for cat in cats:
        for asset in pkg.data.assets(cat):
            asset_id = asset.get("_id", "").rsplit("/", 1)[-1]
            if asset_id:
                available.append(asset_id)
    if not available:
        return []
    return _random.sample(available, min(max_assets, len(available)))
