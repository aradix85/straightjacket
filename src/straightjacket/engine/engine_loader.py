from __future__ import annotations

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
