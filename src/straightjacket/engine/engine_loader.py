from __future__ import annotations

from typing import Any

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT
from .engine_config import EngineSettings, parse_engine_yaml
from .yaml_merge import load_yaml_dir

_ENGINE_DIR = PROJECT_ROOT / "engine"

_eng: EngineSettings | None = None


def eng() -> EngineSettings:
    global _eng
    if _eng is None:
        data = load_yaml_dir(
            _ENGINE_DIR,
            missing_dir_hint="The engine/ directory ships with the repo.",
        )
        _eng = parse_engine_yaml(data)
        _log(f"[Engine] Loaded {_ENGINE_DIR} ({len(data)} sections)")
    return _eng


def damage(category: str, position: str = "risky") -> int:
    segments = category.split(".")
    node: Any = eng().get_raw(segments[0])
    for key in segments[1:]:
        node = node[key]

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
