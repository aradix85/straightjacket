"""Shared helper: merge multiple yaml files from a directory into one dict.

Used by engine_loader, emotions_loader, and prompt_loader. Each loads one
directory of yaml files and flattens top-level keys into a single dict,
raising on duplicate keys across files so misconfiguration is visible.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml


def load_yaml_dir(
    directory: Path,
    *,
    missing_dir_hint: str,
    value_filter: Callable[[str, Any], bool] | None = None,
) -> dict[str, Any]:
    """Read every *.yaml file in `directory` and merge top-level keys.

    Raises FileNotFoundError if the directory is missing or empty, ValueError
    on any file that isn't a yaml dict, and ValueError on duplicate top-level
    keys across files (tracking the origin file for the error message).

    `missing_dir_hint` is appended to the FileNotFoundError message.

    `value_filter(key, value) -> bool`: if provided, keys whose value returns
    False are silently skipped. Use for per-file type constraints like
    "only string values accepted".
    """
    if not directory.is_dir():
        raise FileNotFoundError(f"Config directory not found: {directory}\n{missing_dir_hint}")
    files = sorted(directory.glob("*.yaml"))
    if not files:
        raise FileNotFoundError(f"No yaml files found in {directory}")
    merged: dict[str, Any] = {}
    origin: dict[str, Path] = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"{path} is not a valid YAML dict")
        for key, value in data.items():
            if value_filter is not None and not value_filter(key, value):
                continue
            if key in merged:
                raise ValueError(f"Duplicate top-level key '{key}' in {path} — already defined in {origin[key]}")
            merged[key] = value
            origin[key] = path
    return merged
