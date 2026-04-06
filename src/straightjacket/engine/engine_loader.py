#!/usr/bin/env python3
"""Engine mechanics loader: reads engine.yaml.

Singleton pattern matching config_loader.py. Provides dot-access
to all game mechanics values (damage tables, NPC limits, chaos, etc.).
"""


import yaml

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT, _ConfigNode

_ENGINE_PATH = PROJECT_ROOT / "engine.yaml"

_eng: _ConfigNode | None = None

def eng() -> _ConfigNode:
    """Get the engine mechanics config. Loads on first access."""
    global _eng
    if _eng is None:
        if not _ENGINE_PATH.exists():
            raise FileNotFoundError(
                f"Engine config not found: {_ENGINE_PATH}\n"
                f"The engine.yaml file ships with the repo."
            )
        with open(_ENGINE_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"engine.yaml is not a valid YAML dict: {_ENGINE_PATH}")
        _eng = _ConfigNode(data, "engine")
        _log(f"[Engine] Loaded {_ENGINE_PATH}")
    return _eng

def reload_engine() -> _ConfigNode:
    """Force reload from disk."""
    global _eng
    _eng = None
    return eng()

# CONVENIENCE: position-based damage lookup

def damage(category: str, position: str = "risky") -> int:
    """Look up a damage value from engine.yaml damage tables.

    Usage:
        damage("miss.combat", "desperate")     -> 3
        damage("miss.social.spirit", "risky")   -> 1
        damage("miss.other.supply")             -> 1  (flat, ignores position)
        damage("miss.clock_ticks", "desperate") -> 2
        damage("momentum.loss", "desperate")    -> 3

    Handles both position-keyed dicts and flat ints.
    Returns 0 if the path doesn't exist.
    """
    node = eng()
    for key in category.split("."):
        try:
            node = getattr(node, key) if isinstance(node, _ConfigNode) else node[key]
        except (AttributeError, KeyError, TypeError):
            return 0

    # Flat int (e.g. miss.social.bond: 1)
    if isinstance(node, (int, float)):
        return int(node)

    # Position-keyed dict (e.g. miss.combat: {controlled: 1, risky: 2, desperate: 3})
    if isinstance(node, _ConfigNode):
        try:
            return int(getattr(node, position))
        except (AttributeError, KeyError):
            # Fall back to risky if position not found
            try:
                return int(node.risky)
            except (AttributeError, KeyError):
                return 0

    return 0
