from __future__ import annotations

from ..setting.packages import load_package
from .config import rules

_cache: dict[str, dict[str, str]] = {}


def stat_descriptions(setting_id: str) -> dict[str, str]:
    if setting_id in _cache:
        return _cache[setting_id]
    found: dict[str, str] = {}
    for pkg in reversed(list(load_package(setting_id).chain())):
        for name, raw in pkg.data.stats().items():
            found[name] = raw["description"]
    _cache[setting_id] = found
    return found


def validate_stats(stats: dict[str, int], setting_id: str) -> None:
    names = list(stat_descriptions(setting_id))
    if sorted(stats) != sorted(names):
        raise ValueError(f"Stats must be {', '.join(names)}, got {', '.join(stats)}")
    array = sorted(rules().stats.creation_array, reverse=True)
    values = sorted(stats.values(), reverse=True)
    if values != array:
        raise ValueError(f"Stats must take {array} in any order, got {values}")
