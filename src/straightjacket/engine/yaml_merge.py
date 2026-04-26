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
