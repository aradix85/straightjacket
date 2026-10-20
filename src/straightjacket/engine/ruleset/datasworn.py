from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..logging_util import log
from ..setting.loader import read_datasworn
from ..setting.packages import load_package


@dataclass(frozen=True)
class RulesFile:
    datasworn_id: str
    rules: dict[str, Any]
    moves: dict[str, Any]
    assets: dict[str, Any]

    def assets_of(self, category: str) -> list[dict[str, Any]]:
        return list(self.assets[category]["contents"].values())

    def asset(self, category: str, asset_id: str) -> dict[str, Any] | None:
        if category not in self.assets:
            return None
        found: dict[str, Any] | None = self.assets[category]["contents"].get(asset_id)
        return found


@dataclass(frozen=True)
class Ruleset:
    id: str
    files: list[RulesFile]
    setting_file: RulesFile


def rules_file(datasworn_id: str) -> RulesFile:
    raw = read_datasworn(datasworn_id)
    return RulesFile(datasworn_id=datasworn_id, rules=raw["rules"], moves=raw["moves"], assets=raw["assets"])


_cache: dict[str, Ruleset] = {}


def load_ruleset(setting_id: str) -> Ruleset:
    if setting_id in _cache:
        return _cache[setting_id]
    pkg = load_package(setting_id)
    expansions = [p.datasworn_id for p in reversed(list(pkg.chain())) if p.datasworn_id != pkg.ruleset_id]
    files = [rules_file(datasworn_id) for datasworn_id in [pkg.ruleset_id, *expansions]]
    ruleset = Ruleset(
        id=pkg.ruleset_id,
        files=files,
        setting_file=next(f for f in files if f.datasworn_id == pkg.datasworn_id),
    )
    _cache[setting_id] = ruleset
    log(f"[Ruleset] {setting_id} plays {ruleset.id}: {', '.join(f.datasworn_id for f in files)}")
    return ruleset
