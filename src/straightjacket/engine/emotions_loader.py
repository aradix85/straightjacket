"""Emotions loader: reads and merges emotions/*.yaml.

Provides importance scoring data, DE→EN normalization, and disposition
mapping from a directory of yaml files instead of hardcoded Python dicts.
One file per subsystem: importance.yaml, keyword_boosts.yaml, disposition_map.yaml.
"""

from .bootstrap_log import bootstrap_log as _log
from .config_loader import PROJECT_ROOT
from .yaml_merge import load_yaml_dir

_EMOTIONS_DIR = PROJECT_ROOT / "emotions"

_data: dict | None = None


def _ensure_loaded() -> dict:
    """Load emotions directory on first access."""
    global _data
    if _data is None:
        _data = load_yaml_dir(
            _EMOTIONS_DIR,
            missing_dir_hint="The emotions/ directory ships with the repo.",
        )
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
