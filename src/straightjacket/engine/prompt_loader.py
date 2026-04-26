from pathlib import Path

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT, cfg, model_family_for_role
from .format_utils import PartialFormatDict
from .yaml_merge import load_yaml_dir


def _prompts_dir() -> Path:
    return PROJECT_ROOT / cfg().ai.prompts_dir


_prompts: dict[str, str] | None = None


def _ensure_loaded() -> dict:
    global _prompts
    if _prompts is None:
        directory = _prompts_dir()
        raw = load_yaml_dir(directory, missing_dir_hint="Check ai.prompts_dir in config.yaml.")
        _prompts = {}
        for key, val in raw.items():
            if not isinstance(val, str):
                _log(f"[Prompts] Ignoring non-string prompt '{key}' (type {type(val).__name__})", level="warning")
                continue
            _prompts[key] = val
        _log(f"[Prompts] Loaded {len(_prompts)} prompts from {directory}")
    return _prompts


def get_prompt(name: str, role: str | None = None, **variables: str) -> str:
    prompts = _ensure_loaded()

    if role is not None:
        family = model_family_for_role(role)
        variant_key = f"{name}_{family}"
        template = prompts.get(variant_key)
        if template is None:
            template = prompts.get(name)
            if template is None:
                raise KeyError(
                    f"Unknown prompt: tried '{variant_key}' (role={role}, family={family}) "
                    f"and bare '{name}', neither defined."
                )
    else:
        template = prompts.get(name)
        if template is None:
            raise KeyError(f"Unknown prompt: '{name}'")

    if variables:
        return template.format_map(PartialFormatDict(variables))
    return template
