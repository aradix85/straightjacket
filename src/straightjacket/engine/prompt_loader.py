"""Straightjacket prompt loader: yaml-driven AI prompts.

Prompts live in a directory of yaml files, one per subsystem cluster
(brain, narrator, architect, validator, director, tasks, blocks). The loader
globs the directory and merges top-level keys. The file ships with the repo.
If it's missing, the engine does not start. Template variables use {name}
syntax, filled at runtime.
"""

import yaml
from pathlib import Path

from .config_loader import PROJECT_ROOT, cfg


from .bootstrap_log import bootstrap_log as _log
from .format_utils import PartialFormatDict


def _prompts_dir() -> Path:
    return PROJECT_ROOT / cfg().ai.prompts_dir


_prompts: dict[str, str] | None = None


def _ensure_loaded() -> dict:
    """Load prompts from yaml directory on first access."""
    global _prompts
    if _prompts is None:
        directory = _prompts_dir()
        if not directory.is_dir():
            raise FileNotFoundError(f"Prompts directory not found: {directory}\nCheck ai.prompts_dir in config.yaml.")
        files = sorted(directory.glob("*.yaml"))
        if not files:
            raise FileNotFoundError(f"No yaml files found in {directory}")
        _prompts = {}
        origin: dict[str, Path] = {}
        for path in files:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ValueError(f"{path} is not a valid YAML dict")
            for key, val in data.items():
                if not isinstance(val, str):
                    _log(f"[Prompts] Ignoring non-string prompt '{key}' in {path}", level="warning")
                    continue
                if key in _prompts:
                    raise ValueError(f"Duplicate prompt key '{key}' in {path} — already defined in {origin[key]}")
                _prompts[key] = val
                origin[key] = path
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


def reload_prompts() -> None:
    """Force reload from disk."""
    global _prompts
    _prompts = None
    _ensure_loaded()
