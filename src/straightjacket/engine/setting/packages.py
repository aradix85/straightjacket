from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar

import yaml

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.logging_util import log
from straightjacket.engine.serialization import build_strict, shaped
from straightjacket.engine.setting.loader import load_setting
from straightjacket.engine.setting.oracle_rolls import PLACEHOLDER_PATTERN, link_owner_and_path

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from _typeshed import DataclassInstance

    from straightjacket.engine.setting.loader import OracleTable, Setting

_D = TypeVar("_D", bound="DataclassInstance")
_S = TypeVar("_S")

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
    action_theme: list[str] | None
    backstory: str | None
    threats: str | None


@dataclass
class _CreationFlowPartial:
    has_truths: bool | None
    has_backstory_oracle: bool | None
    has_name_tables: bool | None
    has_ship_creation: bool | None
    starting_asset_categories: list[str] | None


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


def _require(data: dict[str, object], key: str, shape: type[_S], yaml_path: str) -> _S:
    if key not in data:
        msg = f"Required key '{key}' missing in {yaml_path}"
        raise KeyError(msg)
    value = data[key]
    if not isinstance(value, shape):
        msg = f"Expected {shape.__name__} at '{key}' in {yaml_path}, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _optional(data: dict[str, object], key: str, shape: type[_S], yaml_path: str) -> _S | None:
    return _require(data, key, shape, yaml_path) if data.get(key) is not None else None


def _reject_unknown_keys(
    data: dict[str, object], schema: type[DataclassInstance], section: str, yaml_path: str
) -> None:
    unknown = sorted(set(data) - {f.name for f in fields(schema)})
    if unknown:
        msg = f"Unknown key(s) {unknown} in {section} of {yaml_path}"
        raise KeyError(msg)


def _bind_section(
    schema: type[_D], absent: dict[str, object], data: dict[str, object], section: str, yaml_path: str
) -> _D:
    _reject_unknown_keys(data, schema, section, yaml_path)
    empty = sorted(key for key, value in data.items() if value is None)
    if empty:
        msg = f"Key(s) {empty} have no value in {section} of {yaml_path}"
        raise ValueError(msg)
    return build_strict(schema, absent | data, f"{section} of {yaml_path}")


def _parse_generators(data: dict[str, object], yaml_path: str) -> dict[str, dict[str, str]]:
    generators: dict[str, dict[str, str]] = {}
    for category, tables in data.items():
        if not isinstance(tables, dict) or not tables:
            msg = f"Expected a mapping of roles to oracle paths at generators.{category} in {yaml_path}"
            raise TypeError(msg)
        roles: dict[str, str] = {}
        for role, template in tables.items():
            if not isinstance(template, str):
                msg = f"Expected an oracle path at generators.{category}.{role} in {yaml_path}"
                raise TypeError(msg)
            unknown = [name for name in PLACEHOLDER_PATTERN.findall(template) if name not in roles]
            if unknown:
                msg = f"generators.{category}.{role} in {yaml_path} names {unknown}, which no earlier role of it rolls"
                raise KeyError(msg)
            roles[str(role)] = template
        generators[str(category)] = roles
    return generators


def _parse_setting_config(data: dict[str, object], yaml_path: str) -> _SettingConfig:
    _reject_unknown_keys(data, _SettingConfig, "the setting", yaml_path)
    setting_id = _require(data, "id", str, yaml_path)
    if setting_id != Path(yaml_path).stem:
        msg = f"Setting id '{setting_id}' must equal the file name '{Path(yaml_path).stem}' in {yaml_path}"
        raise ValueError(msg)
    return _SettingConfig(
        id=setting_id,
        title=_require(data, "title", str, yaml_path),
        datasworn_id=_require(data, "datasworn_id", str, yaml_path),
        description=_require(data, "description", str, yaml_path),
        playable=_require(data, "playable", bool, yaml_path),
        default_tone=_optional(data, "default_tone", str, yaml_path),
        oracle_paths=_bind_section(
            _OraclePathsPartial,
            dict.fromkeys(f.name for f in fields(_OraclePathsPartial)),
            _require(data, "oracle_paths", dict, yaml_path),
            "oracle_paths",
            yaml_path,
        ),
        generators=_parse_generators(_require(data, "generators", dict, yaml_path), yaml_path),
        vocabulary=_bind_section(
            VocabularyConfig,
            {"substitutions": {}, "sensory_palette": ""},
            _require(data, "vocabulary", dict, yaml_path),
            "vocabulary",
            yaml_path,
        ),
        creation_flow=_bind_section(
            _CreationFlowPartial,
            dict.fromkeys(f.name for f in fields(_CreationFlowPartial)),
            _optional(data, "creation_flow", dict, yaml_path) or {},
            "creation_flow",
            yaml_path,
        ),
        parent=_optional(data, "parent", str, yaml_path),
    )


def _first(values: Iterable[_S | None], field_path: str, yaml_path: str) -> _S:
    for value in values:
        if value is not None:
            return value
    msg = f"{field_path} missing in setting chain ending at {yaml_path}"
    raise KeyError(msg)


def _resolve_oracle_paths(chain: list[_SettingConfig], yaml_path: str) -> OraclePaths:
    paths = [cfg.oracle_paths for cfg in chain]
    return OraclePaths(
        action_theme=_first((p.action_theme for p in paths), "oracle_paths.action_theme", yaml_path),
        backstory=_first((p.backstory for p in paths), "oracle_paths.backstory", yaml_path),
        threats=_first((p.threats for p in paths), "oracle_paths.threats", yaml_path),
    )


def _resolve_creation_flow(chain: list[_SettingConfig], yaml_path: str) -> CreationFlow:
    flows = [cfg.creation_flow for cfg in chain]
    return CreationFlow(
        has_truths=_first((f.has_truths for f in flows), "creation_flow.has_truths", yaml_path),
        has_backstory_oracle=_first(
            (f.has_backstory_oracle for f in flows), "creation_flow.has_backstory_oracle", yaml_path
        ),
        has_name_tables=_first((f.has_name_tables for f in flows), "creation_flow.has_name_tables", yaml_path),
        has_ship_creation=_first((f.has_ship_creation for f in flows), "creation_flow.has_ship_creation", yaml_path),
        starting_asset_categories=_first(
            (f.starting_asset_categories for f in flows), "creation_flow.starting_asset_categories", yaml_path
        ),
    )


class SettingPackage:
    def __init__(
        self,
        config: _SettingConfig,
        data: Setting,
        parent: SettingPackage | None,
        yaml_path: str,
    ) -> None:
        self._config = config
        self._data = data
        self._parent = parent

        rulesets = {pkg.datasworn_id: pkg.ruleset_id for pkg in self.chain()}
        if len(set(rulesets.values())) > 1:
            msg = f"The setting chain ending at {yaml_path} names more than one ruleset: {rulesets}"
            raise ValueError(msg)

        chain = [pkg.config for pkg in self.chain()]
        self._oracle_paths = _resolve_oracle_paths(chain, yaml_path)
        self._creation_flow = _resolve_creation_flow(chain, yaml_path)
        self._generators: dict[str, dict[str, str]] = {}
        for ancestor_config in reversed(chain):
            self._generators.update(ancestor_config.generators)
        tones = [cfg.default_tone for cfg in chain if cfg.default_tone is not None]
        if not tones:
            msg = f"default_tone missing in setting chain ending at {yaml_path}"
            raise KeyError(msg)
        self._default_tone = tones[0]

        if config.vocabulary.is_empty() and parent is not None:
            self._vocabulary = parent.vocabulary
        else:
            self._vocabulary = config.vocabulary

    @property
    def config(self) -> _SettingConfig:
        return self._config

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
    def datasworn_id(self) -> str:
        return self._config.datasworn_id

    @property
    def ruleset_id(self) -> str:
        return self._data.ruleset_id

    @property
    def data(self) -> Setting:
        return self._data

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
        yield self
        if self._parent is not None:
            yield from self._parent.chain()

    def has_oracle(self, path: str) -> bool:
        return any(pkg.data.oracle(path) is not None for pkg in self.chain())

    def oracle_table(self, path: str) -> OracleTable:
        for pkg in self.chain():
            table = pkg.data.oracle(path)
            if table is not None:
                return table
        msg = f"Oracle table '{path}' not found in the setting chain of {self.id}"
        raise KeyError(msg)

    def table_by_id(self, datasworn_id: str) -> OracleTable | None:
        owner, path = link_owner_and_path(datasworn_id)
        pkg = next((p for p in self.chain() if p.datasworn_id == owner), None)
        if pkg is None:
            return None
        table = pkg.data.oracle(path)
        if table is None:
            msg = f"Oracle '{datasworn_id}' not found in {owner}"
            raise KeyError(msg)
        return table

    def roll_action_theme(self) -> tuple[str, str]:
        action_path, theme_path = self._oracle_paths.action_theme
        return self.oracle_table(action_path).roll().text, self.oracle_table(theme_path).roll().text

    def generator_tables(self, category: str) -> dict[str, str]:
        if category not in self._generators:
            msg = f"No generator tables for {category!r} in the setting chain of {self.id}"
            raise KeyError(msg)
        return dict(self._generators[category])

    def name_tables(self, category: str) -> dict[str, OracleTable]:
        return {role: self.oracle_table(path) for role, path in self.generator_tables(category).items()}


_cache: dict[str, SettingPackage] = {}


def list_packages() -> list[str]:
    return sorted(p.stem for p in _SETTINGS_DIR.glob("*.yaml"))


def _read_yaml(setting_id: str) -> tuple[dict[str, object], Path]:
    yaml_path = _SETTINGS_DIR / f"{setting_id}.yaml"
    if not yaml_path.exists():
        msg = f"Setting package not found: {yaml_path}"
        raise FileNotFoundError(msg)
    with Path(yaml_path).open(encoding="utf-8") as f:
        raw: dict[str, object] = shaped(yaml.safe_load(f), dict, f"{yaml_path}: expected a mapping")
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
