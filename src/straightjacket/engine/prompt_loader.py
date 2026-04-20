"""Straightjacket prompt loader: yaml-driven AI prompts.

Prompts live in a directory of yaml files, one per subsystem cluster
(brain, narrator, architect, validator, director, tasks, blocks). The loader
globs the directory and merges top-level keys. The file ships with the repo.
If it's missing, the engine does not start. Template variables use {name}
syntax, filled at runtime.
"""

from pathlib import Path

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT, cfg
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


def get_prompt(name: str, **variables: str) -> str:
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
