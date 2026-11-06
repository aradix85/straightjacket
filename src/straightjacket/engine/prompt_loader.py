from pathlib import Path

from straightjacket.engine.config_loader import PROJECT_ROOT, cfg
from straightjacket.engine.logging_util import log
from straightjacket.engine.yaml_merge import load_text_dir

_cache: dict[Path, dict[str, str]] = {}


def _ensure_loaded() -> dict[str, str]:
    directory = PROJECT_ROOT / cfg().ai.prompts_dir
    if directory not in _cache:
        prompts = load_text_dir(directory, missing_dir_hint="Check ai.prompts_dir in config.yaml.")
        _cache[directory] = prompts
        log(f"[Prompts] Loaded {len(prompts)} prompts from {directory}")
    return _cache[directory]


_PREFIX_MARKER = "\x00"


def get_prompt_prefix(name: str, until: str, **variables: str) -> str:
    rendered = get_prompt(name, **{**variables, until: _PREFIX_MARKER})
    if _PREFIX_MARKER not in rendered:
        msg = f"Prompt '{name}' has no placeholder '{until}'"
        raise KeyError(msg)
    return rendered[: rendered.index(_PREFIX_MARKER)]


def get_prompt(name: str, **variables: str) -> str:
    return _ensure_loaded()[name].format_map(variables)
