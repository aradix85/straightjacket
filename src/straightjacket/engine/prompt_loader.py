from .config_loader import PROJECT_ROOT, cfg
from .logging_util import log
from .yaml_merge import load_yaml_dir

_prompts: dict[str, str] | None = None


def _ensure_loaded() -> dict[str, str]:
    global _prompts
    if _prompts is None:
        directory = PROJECT_ROOT / cfg().ai.prompts_dir
        raw = load_yaml_dir(directory, missing_dir_hint="Check ai.prompts_dir in config.yaml.")
        not_text = sorted(key for key, val in raw.items() if not isinstance(val, str))
        if not_text:
            raise ValueError(f"Prompts must be text; these are not: {not_text}")
        _prompts = raw
        log(f"[Prompts] Loaded {len(_prompts)} prompts from {directory}")
    return _prompts


_PREFIX_MARKER = "\x00"


def get_prompt_prefix(name: str, until: str, **variables: str) -> str:
    rendered = get_prompt(name, **{**variables, until: _PREFIX_MARKER})
    if _PREFIX_MARKER not in rendered:
        raise KeyError(f"Prompt '{name}' has no placeholder '{until}'")
    return rendered[: rendered.index(_PREFIX_MARKER)]


def get_prompt(name: str, **variables: str) -> str:
    return _ensure_loaded()[name].format_map(variables)
