"""Datasworn-driven character creation. Fully deterministic — no AI call."""

from __future__ import annotations

import random as _random

from straightjacket.engine.datasworn.loader import extract_title
from straightjacket.engine.datasworn.settings import load_package

STAT_NAMES = ["edge", "heart", "iron", "shadow", "wits"]


def roll_character(setting_id: str = "starforged", game_cfg: dict | None = None) -> dict:
    """Build creation_data from Datasworn oracles.

    Returns a dict matching start_new_game's expected creation_data.
    """
    game_cfg = game_cfg or {}
    pkg = load_package(setting_id)

    name = _roll_name(pkg, game_cfg)
    pronouns = game_cfg.get("pronouns") or _random.choice(["he/him", "she/her", "they/them"])
    paths = _roll_paths(pkg, game_cfg)
    backstory = _roll_backstory(pkg, game_cfg)
    vow = _roll_vow(pkg, game_cfg)
    stats = _roll_stats(game_cfg)

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
    print(f"[CREATION] Vow: {vow}")
    print(f"[CREATION] Stats: {stats}")

    return {
        "setting_id": setting_id,
        "player_name": name,
        "pronouns": pronouns,
        "paths": paths,
        "backstory": backstory,
        "background_vow": vow,
        "stats": stats,
        "wishes": game_cfg.get("wishes", ""),
        "content_lines": game_cfg.get("content_lines", ""),
    }


def _roll_name(pkg, game_cfg: dict) -> str:
    if game_cfg.get("player_name"):
        return game_cfg["player_name"]
    name_paths = pkg.oracle_paths.get("names", [])
    import contextlib

    parts = []
    for np in name_paths[:2]:
        with contextlib.suppress(KeyError):
            parts.append(pkg.data.roll_oracle(np))
    return " ".join(parts) if parts else f"Wanderer-{_random.randint(100, 999)}"


def _roll_paths(pkg, game_cfg: dict) -> list[str]:
    if game_cfg.get("paths") and len(game_cfg["paths"]) == 2:
        return game_cfg["paths"]
    all_paths = pkg.data.paths()
    path_ids = [p.get("_id", "").rsplit("/", 1)[-1] for p in all_paths if p.get("_id")]
    if len(path_ids) >= 2:
        return _random.sample(path_ids, 2)
    return path_ids[:2]


def _roll_backstory(pkg, game_cfg: dict) -> str:
    if game_cfg.get("backstory"):
        return game_cfg["backstory"]
    try:
        table = pkg.data.backstory_prompts()
        if table:
            return table.roll_text()
    except Exception:
        pass
    return ""


def _roll_vow(pkg, game_cfg: dict) -> str:
    if game_cfg.get("background_vow"):
        return game_cfg["background_vow"]
    try:
        action, theme = pkg.roll_action_theme()
        return f"{action} {theme}".strip()
    except Exception:
        return "Survive"


def _roll_stats(game_cfg: dict) -> dict[str, int]:
    cfg_stats = game_cfg.get("stats")
    if cfg_stats and sum(cfg_stats.values()) == 7:
        return cfg_stats
    return _random_stats()


def _random_stats(target: int = 7) -> dict[str, int]:
    """Generate a random valid stat allocation: sum=target, each 0-3."""
    for _ in range(1000):
        values = [0] * 5
        remaining = target
        indices = list(range(5))
        _random.shuffle(indices)
        for i in indices:
            cap = min(3, remaining)
            if cap <= 0:
                break
            v = _random.randint(0, cap)
            values[i] = v
            remaining -= v
        if remaining > 0:
            for i in indices:
                add = min(3 - values[i], remaining)
                values[i] += add
                remaining -= add
                if remaining <= 0:
                    break
        if sum(values) == target and all(0 <= v <= 3 for v in values):
            return dict(zip(STAT_NAMES, values, strict=True))
    raise RuntimeError(f"Failed to generate valid stat allocation (target={target})")
