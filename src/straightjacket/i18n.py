from pathlib import Path

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.logging_util import log
from straightjacket.engine.yaml_merge import load_text_dir

_cache: dict[Path, dict[str, str]] = {}


def _ensure_loaded() -> dict[str, str]:
    directory = PROJECT_ROOT / "strings"
    if directory not in _cache:
        strings = load_text_dir(directory, missing_dir_hint="strings/ ships with the repo.")
        _cache[directory] = strings
        log(f"[Strings] {len(strings)} strings ready")
    return _cache[directory]


def t(key: str, **variables: str | int) -> str:
    return _ensure_loaded()[key].format_map(variables)


def all_strings() -> dict[str, str]:
    return dict(_ensure_loaded())
