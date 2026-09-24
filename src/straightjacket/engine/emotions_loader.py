from typing import Any
from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT
from .yaml_merge import load_yaml_dir

_EMOTIONS_DIR = PROJECT_ROOT / "emotions"

_data: dict[str, Any] | None = None


def _ensure_loaded() -> dict[str, Any]:
    global _data
    if _data is None:
        _data = load_yaml_dir(
            _EMOTIONS_DIR,
            missing_dir_hint="The emotions/ directory ships with the repo.",
        )
        _log(f"[Emotions] Loaded {_EMOTIONS_DIR} ({len(_data)} sections)")
    return _data


def importance_map() -> dict[str, int]:
    result: dict[str, int] = _ensure_loaded()["importance"]
    return result


def keyword_boosts() -> dict[int, list[str]]:
    raw = _ensure_loaded()["keyword_boosts"]
    return {int(k): v for k, v in raw.items()}


def disposition_map() -> dict[str, str]:
    result: dict[str, str] = _ensure_loaded()["disposition_map"]
    return result


def normalize_disposition(raw: str) -> str:
    return disposition_map().get(raw.lower().strip(), "neutral")
