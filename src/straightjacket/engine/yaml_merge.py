from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from pathlib import Path


def load_yaml_dir(directory: Path, *, missing_dir_hint: str) -> dict[str, object]:
    if not directory.is_dir():
        msg = f"Config directory not found: {directory}\n{missing_dir_hint}"
        raise FileNotFoundError(msg)
    files = sorted(directory.glob("*.yaml"))
    if not files:
        msg = f"No yaml files found in {directory}"
        raise FileNotFoundError(msg)
    merged: dict[str, object] = {}
    origin: dict[str, Path] = {}
    for path in files:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            msg = f"{path} is not a valid YAML dict"
            raise TypeError(msg)
        for key, value in data.items():
            if not isinstance(key, str):
                msg = f"Top-level key {key!r} in {path} is not text"
                raise TypeError(msg)
            if key in merged:
                msg = f"Duplicate top-level key '{key}' in {path} — already defined in {origin[key]}"
                raise ValueError(msg)
            merged[key] = value
            origin[key] = path
    return merged


def load_text_dir(directory: Path, *, missing_dir_hint: str) -> dict[str, str]:
    merged = load_yaml_dir(directory, missing_dir_hint=missing_dir_hint)
    texts = {key: value for key, value in merged.items() if isinstance(value, str)}
    if not_text := sorted(set(merged) - set(texts)):
        msg = f"{directory} holds text only; these keys are not text: {not_text}"
        raise ValueError(msg)
    return texts
