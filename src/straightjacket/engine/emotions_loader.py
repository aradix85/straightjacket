"""Emotions loader: reads and merges emotions/*.yaml.

Provides importance scoring data, DE→EN normalization, and disposition
mapping from a directory of yaml files instead of hardcoded Python dicts.
One file per subsystem: importance.yaml, keyword_boosts.yaml, disposition_map.yaml.
"""

from pathlib import Path

import yaml

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT

_EMOTIONS_DIR = PROJECT_ROOT / "emotions"

_data: dict | None = None


def _load_merged(emotions_dir: Path) -> dict:
    """Read every emotions/*.yaml and merge top-level keys. Duplicates raise."""
    if not emotions_dir.is_dir():
        raise FileNotFoundError(
            f"Emotions config directory not found: {emotions_dir}\nThe emotions/ directory ships with the repo."
        )
    files = sorted(emotions_dir.glob("*.yaml"))
    if not files:
        raise FileNotFoundError(f"No yaml files found in {emotions_dir}")
    merged: dict = {}
    origin: dict[str, Path] = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"{path} is not a valid YAML dict")
        for key, value in data.items():
            if key in merged:
                raise ValueError(f"Duplicate top-level key '{key}' in {path} — already defined in {origin[key]}")
            merged[key] = value
            origin[key] = path
    return merged


def _ensure_loaded() -> dict:
    """Load emotions directory on first access."""
    global _data
    if _data is None:
        _data = _load_merged(_EMOTIONS_DIR)
        _log(f"[Emotions] Loaded {_EMOTIONS_DIR} ({len(_data)} sections)")
    return _data


def importance_map() -> dict[str, int]:
    """Get the emotional_weight → importance score mapping. Raises if missing."""
    return _ensure_loaded()["importance"]


def keyword_boosts() -> dict[int, list[str]]:
    """Get keyword boost tiers: {min_score: [keywords]}. Raises if missing."""
    raw = _ensure_loaded()["keyword_boosts"]
    return {int(k): v for k, v in raw.items()}


def disposition_map() -> dict[str, str]:
    """Get disposition normalization map (any label → canonical 5). Raises if missing."""
    return _ensure_loaded()["disposition_map"]


def normalize_disposition(raw: str) -> str:
    """Normalize any AI-generated disposition to one of the 5 canonical values.

    The disposition_map falls back to "neutral" for unknown labels — this is
    AI-output sanitisation (the narrator invents new words), not a domain
    fallback on the yaml config itself.
    """
    return disposition_map().get(raw.lower().strip(), "neutral")
