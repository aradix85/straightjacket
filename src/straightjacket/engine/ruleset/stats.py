from __future__ import annotations

from straightjacket.engine.ruleset.config import rules
from straightjacket.engine.ruleset.datasworn import load_ruleset
from straightjacket.engine.serialization import read_key

_cache: dict[str, dict[str, str]] = {}


def stat_descriptions(setting_id: str) -> dict[str, str]:
    if setting_id in _cache:
        return _cache[setting_id]
    found: dict[str, str] = {}
    for rules_file in load_ruleset(setting_id).files:
        for name, raw in rules_file.rule("stats").items():
            found[name] = read_key(raw, "description", str, f"{rules_file.datasworn_id}.rules.stats.{name}")
    _cache[setting_id] = found
    return found


def validate_stats(stats: dict[str, int], setting_id: str) -> None:
    names = list(stat_descriptions(setting_id))
    if sorted(stats) != sorted(names):
        msg = f"Stats must be {', '.join(names)}, got {', '.join(stats)}"
        raise ValueError(msg)
    array = sorted(rules().stats.creation_array, reverse=True)
    values = sorted(stats.values(), reverse=True)
    if values != array:
        msg = f"Stats must take {array} in any order, got {values}"
        raise ValueError(msg)
