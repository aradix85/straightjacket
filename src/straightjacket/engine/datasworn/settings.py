from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from collections.abc import Iterator
from typing import Any

import yaml

from ..config_loader import PROJECT_ROOT
from ..logging_util import log
from .loader import OracleTable, Setting, load_setting
from .oracle_rolls import PLACEHOLDER_PATTERN

_SETTINGS_DIR = PROJECT_ROOT / "data" / "settings"


@dataclass
class VocabularyConfig:
    substitutions: dict[str, str]
    sensory_palette: str

    def is_empty(self) -> bool:
        return not self.substitutions and not self.sensory_palette


@dataclass
class OraclePaths:
    action_theme: list[str]
    backstory: str
    threats: str


@dataclass
class CreationFlow:
    has_truths: bool
    has_backstory_oracle: bool
    has_name_tables: bool
    has_ship_creation: bool
    starting_asset_categories: list[str]


@dataclass
class _OraclePathsPartial:
    action_theme: list[str] | None = None
    backstory: str | None = None
    threats: str | None = None


@dataclass
class _CreationFlowPartial:
    has_truths: bool | None = None
    has_backstory_oracle: bool | None = None
    has_name_tables: bool | None = None
    has_ship_creation: bool | None = None
    starting_asset_categories: list[str] | None = None


@dataclass
class _SettingConfig:
    id: str
    title: str
    datasworn_id: str
    description: str
    playable: bool
    default_tone: str | None
    oracle_paths: _OraclePathsPartial
    generators: dict[str, dict[str, str]]
    vocabulary: VocabularyConfig
    creation_flow: _CreationFlowPartial
    parent: str | None


def _require_dict(data: dict[str, Any], key: str, yaml_path: str) -> dict[str, Any]:
    if key not in data:
        raise KeyError(f"Required key '{key}' missing in {yaml_path}")
    value = data[key]
    if not isinstance(value, dict):
        raise TypeError(f"Expected dict at '{key}' in {yaml_path}, got {type(value).__name__}")
    return value


def _require_str(data: dict[str, Any], key: str, yaml_path: str) -> str:
    if key not in data:
        raise KeyError(f"Required key '{key}' missing in {yaml_path}")
    value = data[key]
    if not isinstance(value, str):
        raise TypeError(f"Expected str at '{key}' in {yaml_path}, got {type(value).__name__}")
    return value


def _require_bool(data: dict[str, Any], key: str, yaml_path: str) -> bool:
    if key not in data:
        raise KeyError(f"Required key '{key}' missing in {yaml_path}")
    value = data[key]
    if not isinstance(value, bool):
        raise TypeError(f"Expected bool at '{key}' in {yaml_path}, got {type(value).__name__}")
    return value


def _reject_unknown_keys(data: dict[str, Any], schema: type, section: str, yaml_path: str) -> None:
    unknown = sorted(set(data) - {f.name for f in fields(schema)})
    if unknown:
        raise KeyError(f"Unknown key(s) {unknown} in {section} of {yaml_path}")


def _parse_oracle_paths_partial(data: dict[str, Any], yaml_path: str) -> _OraclePathsPartial:
    _reject_unknown_keys(data, _OraclePathsPartial, "oracle_paths", yaml_path)
    partial = _OraclePathsPartial()
    if "action_theme" in data:
        partial.action_theme = list(data["action_theme"])
    if "backstory" in data:
        partial.backstory = data["backstory"]
    if "threats" in data:
        partial.threats = data["threats"]
    return partial


def _parse_generators(data: dict[str, Any], yaml_path: str) -> dict[str, dict[str, str]]:
    generators: dict[str, dict[str, str]] = {}
    for category, tables in data.items():
        if not isinstance(tables, dict) or not tables:
            raise TypeError(f"Expected a mapping of roles to oracle paths at generators.{category} in {yaml_path}")
        roles: dict[str, str] = {}
        for role, template in tables.items():
            if not isinstance(template, str):
                raise TypeError(f"Expected an oracle path at generators.{category}.{role} in {yaml_path}")
            unknown = [name for name in PLACEHOLDER_PATTERN.findall(template) if name not in roles]
            if unknown:
                raise KeyError(
                    f"generators.{category}.{role} in {yaml_path} names {unknown}, which no earlier role of it rolls"
                )
            roles[str(role)] = template
        generators[str(category)] = roles
    return generators


def _parse_vocabulary(data: dict[str, Any], yaml_path: str) -> VocabularyConfig:
    _reject_unknown_keys(data, VocabularyConfig, "vocabulary", yaml_path)
    return VocabularyConfig(
        substitutions=dict(data.get("substitutions", {})),
        sensory_palette=data.get("sensory_palette", ""),
    )


def _parse_creation_flow_partial(data: dict[str, Any] | None, yaml_path: str) -> _CreationFlowPartial:
    partial = _CreationFlowPartial()
    if data is None:
        return partial
    _reject_unknown_keys(data, _CreationFlowPartial, "creation_flow", yaml_path)
    if "has_truths" in data:
        partial.has_truths = bool(data["has_truths"])
    if "has_backstory_oracle" in data:
        partial.has_backstory_oracle = bool(data["has_backstory_oracle"])
    if "has_name_tables" in data:
        partial.has_name_tables = bool(data["has_name_tables"])
    if "has_ship_creation" in data:
        partial.has_ship_creation = bool(data["has_ship_creation"])
    if "starting_asset_categories" in data:
        partial.starting_asset_categories = list(data["starting_asset_categories"])
    return partial


def _parse_setting_config(data: dict[str, Any], yaml_path: str) -> _SettingConfig:
    _reject_unknown_keys(data, _SettingConfig, "the setting", yaml_path)
    setting_id = _require_str(data, "id", yaml_path)
    if setting_id != Path(yaml_path).stem:
        raise ValueError(f"Setting id '{setting_id}' must equal the file name '{Path(yaml_path).stem}' in {yaml_path}")
    parent_raw = data.get("parent")
    return _SettingConfig(
        id=setting_id,
        title=_require_str(data, "title", yaml_path),
        datasworn_id=_require_str(data, "datasworn_id", yaml_path),
        description=_require_str(data, "description", yaml_path),
        playable=_require_bool(data, "playable", yaml_path),
        default_tone=_require_str(data, "default_tone", yaml_path) if "default_tone" in data else None,
        oracle_paths=_parse_oracle_paths_partial(_require_dict(data, "oracle_paths", yaml_path), yaml_path),
        generators=_parse_generators(_require_dict(data, "generators", yaml_path), yaml_path),
        vocabulary=_parse_vocabulary(_require_dict(data, "vocabulary", yaml_path), yaml_path),
        creation_flow=_parse_creation_flow_partial(data.get("creation_flow"), yaml_path),
        parent=str(parent_raw) if parent_raw else None,
    )


def _resolve_oracle_paths(chain: list[_SettingConfig], yaml_path: str) -> OraclePaths:
    def pick_str(attr: str) -> str:
        for cfg in chain:
            val = getattr(cfg.oracle_paths, attr)
            if val is not None:
                return str(val)
        raise KeyError(f"oracle_paths.{attr} missing in setting chain ending at {yaml_path}")

    def pick_str_list(attr: str) -> list[str]:
        for cfg in chain:
            val = getattr(cfg.oracle_paths, attr)
            if val is not None:
                return [str(item) for item in val]
        raise KeyError(f"oracle_paths.{attr} missing in setting chain ending at {yaml_path}")

    return OraclePaths(
        action_theme=pick_str_list("action_theme"),
        backstory=pick_str("backstory"),
        threats=pick_str("threats"),
    )


def _resolve_creation_flow(chain: list[_SettingConfig], yaml_path: str) -> CreationFlow:
    def pick_bool(attr: str) -> bool:
        for cfg in chain:
            val = getattr(cfg.creation_flow, attr)
            if val is not None:
                return bool(val)
        raise KeyError(f"creation_flow.{attr} missing in setting chain ending at {yaml_path}")

    def pick_str_list(attr: str) -> list[str]:
        for cfg in chain:
            val = getattr(cfg.creation_flow, attr)
            if val is not None:
                return [str(item) for item in val]
        raise KeyError(f"creation_flow.{attr} missing in setting chain ending at {yaml_path}")

    return CreationFlow(
        has_truths=pick_bool("has_truths"),
        has_backstory_oracle=pick_bool("has_backstory_oracle"),
        has_name_tables=pick_bool("has_name_tables"),
        has_ship_creation=pick_bool("has_ship_creation"),
        starting_asset_categories=pick_str_list("starting_asset_categories"),
    )


class SettingPackage:
    def __init__(
        self,
        config: _SettingConfig,
        data: Setting,
        parent: SettingPackage | None,
        yaml_path: str,
    ):
        self._config = config
        self._data = data
        self._parent = parent

        chain = [pkg._config for pkg in self.chain()]
        self._oracle_paths = _resolve_oracle_paths(chain, yaml_path)
        self._creation_flow = _resolve_creation_flow(chain, yaml_path)
        self._generators: dict[str, dict[str, str]] = {}
        for ancestor_config in reversed(chain):
            self._generators.update(ancestor_config.generators)
        tones = [cfg.default_tone for cfg in chain if cfg.default_tone is not None]
        if not tones:
            raise KeyError(f"default_tone missing in setting chain ending at {yaml_path}")
        self._default_tone = tones[0]

        if config.vocabulary.is_empty() and parent is not None:
            self._vocabulary = parent.vocabulary
        else:
            self._vocabulary = config.vocabulary

    @property
    def id(self) -> str:
        return self._config.id

    @property
    def title(self) -> str:
        return self._config.title

    @property
    def playable(self) -> bool:
        return self._config.playable

    @property
    def default_tone(self) -> str:
        return self._default_tone

    @property
    def description(self) -> str:
        return self._config.description

    @property
    def data(self) -> Setting:
        return self._data

    @property
    def parent(self) -> SettingPackage | None:
        return self._parent

    @property
    def vocabulary(self) -> VocabularyConfig:
        return self._vocabulary

    @property
    def oracle_paths(self) -> OraclePaths:
        return self._oracle_paths

    @property
    def creation_flow(self) -> CreationFlow:
        return self._creation_flow

    def chain(self) -> Iterator[SettingPackage]:
        pkg: SettingPackage | None = self
        while pkg is not None:
            yield pkg
            pkg = pkg._parent

    def has_oracle(self, path: str) -> bool:
        return any(pkg._data.oracle(path) is not None for pkg in self.chain())

    def oracle_table(self, path: str) -> OracleTable:
        for pkg in self.chain():
            table = pkg._data.oracle(path)
            if table is not None:
                return table
        raise KeyError(f"Oracle table '{path}' not found in the setting chain of {self.id}")

    def roll_action_theme(self) -> tuple[str, str]:
        action_path, theme_path = self._oracle_paths.action_theme
        return self.oracle_table(action_path).roll().value, self.oracle_table(theme_path).roll().value

    def generator_tables(self, category: str) -> dict[str, str]:
        if category not in self._generators:
            raise KeyError(f"No generator tables for {category!r} in the setting chain of {self.id}")
        return dict(self._generators[category])

    def name_tables(self, category: str) -> dict[str, OracleTable]:
        return {role: self.oracle_table(path) for role, path in self.generator_tables(category).items()}


_cache: dict[str, SettingPackage] = {}


def list_packages() -> list[str]:
    return sorted(p.stem for p in _SETTINGS_DIR.glob("*.yaml"))


def _read_yaml(setting_id: str) -> tuple[dict[str, Any], Path]:
    yaml_path = _SETTINGS_DIR / f"{setting_id}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Setting package not found: {yaml_path}")
    with Path(yaml_path).open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw, yaml_path


def load_package(setting_id: str) -> SettingPackage:
    if setting_id in _cache:
        return _cache[setting_id]

    raw, yaml_path = _read_yaml(setting_id)
    config = _parse_setting_config(raw, str(yaml_path))
    data = load_setting(config.datasworn_id)

    parent: SettingPackage | None = None
    if config.parent:
        parent = load_package(config.parent)

    pkg = SettingPackage(config, data, parent, str(yaml_path))
    _cache[setting_id] = pkg

    log(f"[Setting] Loaded {setting_id}: {pkg.title}{f' (parent: {config.parent})' if config.parent else ''}")
    return pkg


def clear_cache() -> None:
    _cache.clear()
