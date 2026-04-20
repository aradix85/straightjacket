"""Engine mechanics loader: reads and merges engine/*.yaml files.

Singleton pattern matching config_loader.py. Returns typed EngineSettings
for structured sections, with get_raw() for flexible sections.

Engine config is split across one yaml per subsystem under engine/. The
loader globs the directory, merges top-level keys into a single dict, and
hands that dict to parse_engine_yaml. Duplicate top-level keys across files
raise — each key belongs in exactly one file.
"""

from __future__ import annotations

from typing import Any

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT
from .engine_config import EngineSettings, parse_engine_yaml
from .yaml_merge import load_yaml_dir

_ENGINE_DIR = PROJECT_ROOT / "engine"

_eng: EngineSettings | None = None


def eng() -> EngineSettings:
    """Get the engine mechanics config. Loads on first access."""
    global _eng
    if _eng is None:
        data = load_yaml_dir(
            _ENGINE_DIR,
            missing_dir_hint="The engine/ directory ships with the repo.",
        )
        _eng = parse_engine_yaml(data)
        _log(f"[Engine] Loaded {_ENGINE_DIR} ({len(data)} sections)")
    return _eng


# CONVENIENCE: position-based damage lookup


def damage(category: str, position: str = "risky") -> int:
    """Look up a damage value from engine.yaml damage tables.

    Navigates the raw YAML dict by dotted-path. Each segment of `category` is
    a key into the dict. Leaves may be flat ints (position-agnostic) or dicts
    keyed by combat position.

    Strict: raises KeyError on missing paths and missing positions. Callers
    must supply a valid category path and a position that exists in the table.
    """
    segments = category.split(".")
    node: Any = eng().get_raw(segments[0])
    for key in segments[1:]:
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
