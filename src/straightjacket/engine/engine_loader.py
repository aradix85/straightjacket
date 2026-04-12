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

    Navigates the raw YAML dict. Handles position-keyed dicts and flat ints.
    Returns 0 if the path doesn't exist.
    """
    raw = eng()._raw
    node: Any = raw
    for key in category.split("."):
        try:
            node = node[key]
        except (KeyError, TypeError, IndexError):
            return 0

    if isinstance(node, int | float):
        return int(node)

    if isinstance(node, dict):
        val = node.get(position, node.get("risky"))
        if isinstance(val, int | float):
            return int(val)

    return 0
