from .engine.config_loader import PROJECT_ROOT
from .engine.logging_util import log
from .engine.yaml_merge import load_text_dir

_strings: dict[str, str] | None = None


def _ensure_loaded() -> dict[str, str]:
    global _strings
    if _strings is None:
        _strings = load_text_dir(PROJECT_ROOT / "strings", missing_dir_hint="strings/ ships with the repo.")
        log(f"[Strings] {len(_strings)} strings ready")
    return _strings


def t(key: str, **variables: str | int) -> str:
    return _ensure_loaded()[key].format_map(variables)


def all_strings() -> dict[str, str]:
    return dict(_ensure_loaded())
