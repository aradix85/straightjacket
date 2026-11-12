from __future__ import annotations

from dataclasses import dataclass

from straightjacket.engine.logging_util import log
from straightjacket.engine.serialization import read_key, read_optional_key
from straightjacket.engine.setting.loader import read_datasworn
from straightjacket.engine.setting.packages import load_package


@dataclass(frozen=True)
class AssetAbility:
    text: str
    enabled: bool


@dataclass(frozen=True)
class Asset:
    id: str
    name: str
    abilities: list[AssetAbility]


@dataclass(frozen=True)
class AssetCategory:
    name: str
    contents: dict[str, Asset]


@dataclass(frozen=True)
class RulesFile:
    datasworn_id: str
    rules: dict[str, object]
    moves: dict[str, object]
    assets: dict[str, AssetCategory]

    def rule(self, name: str) -> dict[str, object]:
        return read_optional_key(self.rules, name, dict, f"{self.datasworn_id}.rules") or {}

    def assets_of(self, category: str) -> list[Asset]:
        return list(self.assets[category].contents.values())

    def asset(self, category: str, asset_id: str) -> Asset | None:
        return self.assets[category].contents.get(asset_id) if category in self.assets else None


@dataclass(frozen=True)
class Ruleset:
    id: str
    files: list[RulesFile]
    setting_file: RulesFile


def _parse_asset(raw: object, where: str) -> Asset:
    return Asset(
        id=read_key(raw, "_id", str, where),
        name=read_key(raw, "name", str, where),
        abilities=[
            AssetAbility(
                text=read_key(ability, "text", str, f"{where}.abilities[{index}]"),
                enabled=read_key(ability, "enabled", bool, f"{where}.abilities[{index}]"),
            )
            for index, ability in enumerate(read_key(raw, "abilities", list, where))
        ],
    )


def _parse_asset_category(raw: object, where: str) -> AssetCategory:
    return AssetCategory(
        name=read_key(raw, "name", str, where),
        contents={
            key: _parse_asset(asset, f"{where}.{key}") for key, asset in read_key(raw, "contents", dict, where).items()
        },
    )


def rules_file(datasworn_id: str) -> RulesFile:
    raw = read_datasworn(datasworn_id)
    return RulesFile(
        datasworn_id=datasworn_id,
        rules=read_key(raw, "rules", dict, datasworn_id),
        moves=read_key(raw, "moves", dict, datasworn_id),
        assets={
            key: _parse_asset_category(category, f"{datasworn_id}.assets.{key}")
            for key, category in read_key(raw, "assets", dict, datasworn_id).items()
        },
    )


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
