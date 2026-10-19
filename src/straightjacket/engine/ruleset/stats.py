from __future__ import annotations

from .config import rules
from .datasworn import load_ruleset

_cache: dict[str, dict[str, str]] = {}


def stat_descriptions(setting_id: str) -> dict[str, str]:
    if setting_id in _cache:
        return _cache[setting_id]
    found: dict[str, str] = {}
    for rules_file in load_ruleset(setting_id).files:
        for name, raw in (rules_file.rules.get("stats") or {}).items():
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
