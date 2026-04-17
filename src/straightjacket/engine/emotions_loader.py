#!/usr/bin/env python3
"""Emotions loader: reads emotions.yaml.

Provides importance scoring data, DE→EN normalization, and disposition
mapping from a YAML file instead of hardcoded Python dicts.
"""

import yaml

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT

_EMOTIONS_PATH = PROJECT_ROOT / "emotions.yaml"

_data: dict | None = None


def _ensure_loaded() -> dict:
    """Load emotions.yaml on first access."""
    global _data
    if _data is None:
        if not _EMOTIONS_PATH.exists():
            raise FileNotFoundError(
                f"Emotions config not found: {_EMOTIONS_PATH}\nThe emotions.yaml file ships with the repo."
            )
        with open(_EMOTIONS_PATH, encoding="utf-8") as f:
            _data = yaml.safe_load(f)
        if not isinstance(_data, dict):
            raise ValueError(f"emotions.yaml is not a valid YAML dict: {_EMOTIONS_PATH}")
        _log(f"[Emotions] Loaded {_EMOTIONS_PATH}")
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
