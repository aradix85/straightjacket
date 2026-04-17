#!/usr/bin/env python3
"""Engine mechanics loader: reads engine.yaml.

Singleton pattern matching config_loader.py. Returns typed EngineSettings
for structured sections, with get_raw() for flexible sections.
"""

from __future__ import annotations

from typing import Any

import yaml

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT
from .engine_config import EngineSettings, parse_engine_yaml

_ENGINE_PATH = PROJECT_ROOT / "engine.yaml"

_eng: EngineSettings | None = None


def eng() -> EngineSettings:
    """Get the engine mechanics config. Loads on first access."""
    global _eng
    if _eng is None:
        if not _ENGINE_PATH.exists():
            raise FileNotFoundError(
                f"Engine config not found: {_ENGINE_PATH}\nThe engine.yaml file ships with the repo."
            )
        with open(_ENGINE_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"engine.yaml is not a valid YAML dict: {_ENGINE_PATH}")
        _eng = parse_engine_yaml(data)
        _log(f"[Engine] Loaded {_ENGINE_PATH}")
    return _eng


def reload_engine() -> EngineSettings:
    """Force reload from disk. Also clears derived caches (schemas)."""
    global _eng
    _eng = None
    from .ai.schemas import clear_brain_cache

    clear_brain_cache()
    return eng()


# CONVENIENCE: position-based damage lookup


def damage(category: str, position: str = "risky") -> int:
    """Look up a damage value from engine.yaml damage tables.

    Navigates the raw YAML dict by dotted-path. Each segment of `category` is
    a key into the dict. Leaves may be flat ints (position-agnostic) or dicts
    keyed by combat position.

    Strict: raises KeyError on missing paths and missing positions. Callers
    must supply a valid category path and a position that exists in the table.
    """
    raw = eng()._raw
    node: Any = raw
    for key in category.split("."):
        node = node[key]  # KeyError on missing key — straightjacket rule

    if isinstance(node, int | float):
        return int(node)

    if isinstance(node, dict):
        if position not in node:
            raise KeyError(
                f"damage table at '{category}' has no entry for position '{position}' — "
                f"available: {sorted(node.keys())}"
            )
        val = node[position]
        if not isinstance(val, int | float):
            raise TypeError(f"damage table '{category}.{position}' is not numeric: {val!r}")
        return int(val)

    raise TypeError(f"damage table at '{category}' is neither a number nor a position dict: {type(node).__name__}")
