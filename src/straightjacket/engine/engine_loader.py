from __future__ import annotations

from .config_loader import PROJECT_ROOT
from .engine_config import EngineSettings, parse_engine_yaml
from .logging_util import log
from .yaml_merge import load_yaml_dir

_CONFIG_DIRS = tuple(PROJECT_ROOT / name for name in ("engine", "gamemaster", "crafters", "ruleset"))

_eng: EngineSettings | None = None


def eng() -> EngineSettings:
    global _eng
    if _eng is None:
        data = load_yaml_dir(
            *_CONFIG_DIRS,
            missing_dir_hint="The engine, gamemaster, crafters, and ruleset directories ship with the repo.",
        )
        _eng = parse_engine_yaml(data)
        log(f"[Engine] Loaded {len(data)} sections from {', '.join(d.name for d in _CONFIG_DIRS)}")
    return _eng
