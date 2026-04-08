#!/usr/bin/env python3
"""Straightjacket prompt loader: yaml-driven AI prompts.

prompts.yaml is the single source of truth for all AI system prompts.
The file ships with the repo. If it's missing, the engine does not start.
Template variables use {name} syntax, filled at runtime.
"""

import yaml

from .config_loader import PROJECT_ROOT


from .bootstrap_log import bootstrap_log as _log
from .format_utils import PartialFormatDict

_PROMPTS_PATH = PROJECT_ROOT / "prompts.yaml"

_prompts: dict[str, str] | None = None


def _ensure_loaded() -> dict:
    """Load prompts from yaml on first access.

    prompts.yaml is the single source of truth. If it's missing, raise an error.
    """
    global _prompts
    if _prompts is None:
        if not _PROMPTS_PATH.exists():
            raise FileNotFoundError(
                f"Prompts file not found: {_PROMPTS_PATH}\n"
                f"The prompts.yaml file ships with the repo — if you deleted it, restore it from git."
            )
        with open(_PROMPTS_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Prompts file is not a valid YAML dict: {_PROMPTS_PATH}")
        # Validate all values are strings
        _prompts = {}
        for key, val in data.items():
            if isinstance(val, str):
                _prompts[key] = val
            else:
                _log(f"[Prompts] Ignoring non-string prompt '{key}'", level="warning")
        _log(f"[Prompts] Loaded {len(_prompts)} prompts from {_PROMPTS_PATH}")
    return _prompts


def get_prompt(name: str, **variables) -> str:
    """Get a prompt by name, filling template variables.

    Missing variables are left as {name} in the output (partial formatting).
    Unknown prompt names raise KeyError.
    """
    prompts = _ensure_loaded()
    template = prompts.get(name)
    if template is None:
        raise KeyError(f"Unknown prompt: '{name}'")
    if variables:
        return template.format_map(PartialFormatDict(variables))
    return template


def reload_prompts():
    """Force reload from disk."""
    global _prompts
    _prompts = None
    _ensure_loaded()
