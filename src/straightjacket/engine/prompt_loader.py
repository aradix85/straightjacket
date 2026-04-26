"""Straightjacket prompt loader: yaml-driven AI prompts.

Prompts live in a directory of yaml files, one per subsystem cluster
(brain, narrator, architect, validator, director, tasks, blocks). The loader
globs the directory and merges top-level keys. The file ships with the repo.
If it's missing, the engine does not start. Template variables use {name}
syntax, filled at runtime.

Role-aware lookup. When `role` is supplied to get_prompt, the loader
resolves the role's model family via model_family_for_role and tries
`{name}_{family}` first; if that variant is absent it falls back to the
bare `{name}`. Absence of both raises KeyError. This lets prompts ship
model-specific variants (e.g. `narrator_system_glm`, `narrator_system_qwen`)
alongside a universal fallback (`narrator_system`) without forcing every
role to maintain a variant for every model.
"""

from pathlib import Path

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT, cfg, model_family_for_role
from .format_utils import PartialFormatDict
from .yaml_merge import load_yaml_dir


def _prompts_dir() -> Path:
    return PROJECT_ROOT / cfg().ai.prompts_dir


_prompts: dict[str, str] | None = None


def _ensure_loaded() -> dict:
    """Load prompts from yaml directory on first access."""
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
    """Get a prompt by name, filling template variables.

    Without `role`, returns the prompt under exactly `name`. Unknown name
    raises KeyError.

    With `role`, resolves the role's model family and prefers the variant
    `{name}_{family}` if present. Falls back to bare `{name}` when the
    variant is absent. Absence of both raises KeyError naming both keys
    that were tried.

    Missing template variables are left as {name} in the output (partial
    formatting).
    """
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
