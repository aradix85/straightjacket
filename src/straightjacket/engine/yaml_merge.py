from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml_dir(directory: Path, *, missing_dir_hint: str) -> dict[str, Any]:
    if not directory.is_dir():
        raise FileNotFoundError(f"Config directory not found: {directory}\n{missing_dir_hint}")
    files = sorted(directory.glob("*.yaml"))
    if not files:
        raise FileNotFoundError(f"No yaml files found in {directory}")
    merged: dict[str, Any] = {}
    origin: dict[str, Path] = {}
    for path in files:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"{path} is not a valid YAML dict")
        for key, value in data.items():
            if key in merged:
                raise ValueError(f"Duplicate top-level key '{key}' in {path} — already defined in {origin[key]}")
            merged[key] = value
            origin[key] = path
    return merged


def load_text_dir(directory: Path, *, missing_dir_hint: str) -> dict[str, str]:
    merged = load_yaml_dir(directory, missing_dir_hint=missing_dir_hint)
    not_text = sorted(key for key, value in merged.items() if not isinstance(value, str))
    if not_text:
        raise ValueError(f"{directory} holds text only; these keys are not text: {not_text}")
    return merged
