from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from ..config_loader import PROJECT_ROOT
from ..logging_util import log
from .loader import OracleTable, Setting, load_setting

if TYPE_CHECKING:
    from ..models import GameState

_SETTINGS_DIR = PROJECT_ROOT / "data" / "settings"


@dataclass
class GenreConstraints:
    forbidden_terms: list[str]
    forbidden_concepts: list[str]
    genre_test: str
    atmospheric_drift_universal: list[str]
    atmospheric_drift_overlays: dict[str, list[str]]
    atmospheric_drift_threshold: int

    def atmospheric_drift_for(self, family: str) -> list[str]:
        overlay = self.atmospheric_drift_overlays.get(family, [])
        return list(self.atmospheric_drift_universal) + list(overlay)


@dataclass
class VocabularyConfig:
    substitutions: dict[str, str]
    sensory_palette: str

    def is_empty(self) -> bool:
        return not self.substitutions and not self.sensory_palette


@dataclass
class OraclePaths:
    action_theme: list[str]
    names: list[str]
    backstory: str
    factions: str


@dataclass
class CreationFlow:
    has_truths: bool
    has_backstory_oracle: bool
    has_name_tables: bool
    has_ship_creation: bool
    starting_asset_categories: list[str]


@dataclass
class _GenreConstraintsPartial:
    forbidden_terms: list[str] | None = None
    forbidden_concepts: list[str] | None = None
    genre_test: str | None = None
    atmospheric_drift_universal: list[str] | None = None
    atmospheric_drift_overlays: dict[str, list[str]] | None = None
    atmospheric_drift_threshold: int | None = None


@dataclass
class _OraclePathsPartial:
    action_theme: list[str] | None = None
    names: list[str] | None = None
    backstory: str | None = None
    factions: str | None = None


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
    oracle_paths: _OraclePathsPartial
    vocabulary: VocabularyConfig
    genre_constraints: _GenreConstraintsPartial
    creation_flow: _CreationFlowPartial
    parent: str | None


def _require_dict(data: dict, key: str, yaml_path: str) -> dict:
    if key not in data:
        raise KeyError(f"Required key '{key}' missing in {yaml_path}")
    value = data[key]
    if not isinstance(value, dict):
        raise TypeError(f"Expected dict at '{key}' in {yaml_path}, got {type(value).__name__}")
    return value


def _require_str(data: dict, key: str, yaml_path: str) -> str:
    if key not in data:
        raise KeyError(f"Required key '{key}' missing in {yaml_path}")
    value = data[key]
    if not isinstance(value, str):
        raise TypeError(f"Expected str at '{key}' in {yaml_path}, got {type(value).__name__}")
    return value


def _parse_oracle_paths_partial(data: dict) -> _OraclePathsPartial:
    partial = _OraclePathsPartial()
    if "action_theme" in data:
        partial.action_theme = list(data["action_theme"])
    if "names" in data:
        partial.names = list(data["names"])
    if "backstory" in data:
        partial.backstory = data["backstory"]
    if "factions" in data:
        partial.factions = data["factions"]
    return partial


def _parse_vocabulary(data: dict) -> VocabularyConfig:
    return VocabularyConfig(
        substitutions=dict(data.get("substitutions", {})),
        sensory_palette=data.get("sensory_palette", ""),
    )


def _parse_genre_constraints_partial(data: dict) -> _GenreConstraintsPartial:
    partial = _GenreConstraintsPartial()
    if "forbidden_terms" in data:
        partial.forbidden_terms = list(data["forbidden_terms"])
    if "forbidden_concepts" in data:
        partial.forbidden_concepts = list(data["forbidden_concepts"])
    if "genre_test" in data:
        partial.genre_test = data["genre_test"]
    if "atmospheric_drift_universal" in data:
        partial.atmospheric_drift_universal = list(data["atmospheric_drift_universal"])
    if "atmospheric_drift_overlays" in data:
        partial.atmospheric_drift_overlays = {
            family: list(words) for family, words in data["atmospheric_drift_overlays"].items()
        }
    if "atmospheric_drift_threshold" in data:
        partial.atmospheric_drift_threshold = int(data["atmospheric_drift_threshold"])
    return partial


def _parse_creation_flow_partial(data: dict | None) -> _CreationFlowPartial:
    partial = _CreationFlowPartial()
    if data is None:
        return partial
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


def _parse_setting_config(data: dict, yaml_path: str) -> _SettingConfig:
    parent_raw = data.get("parent")
    return _SettingConfig(
        id=_require_str(data, "id", yaml_path),
        title=_require_str(data, "title", yaml_path),
        datasworn_id=_require_str(data, "datasworn_id", yaml_path),
        description=_require_str(data, "description", yaml_path),
        oracle_paths=_parse_oracle_paths_partial(_require_dict(data, "oracle_paths", yaml_path)),
        vocabulary=_parse_vocabulary(_require_dict(data, "vocabulary", yaml_path)),
        genre_constraints=_parse_genre_constraints_partial(_require_dict(data, "genre_constraints", yaml_path)),
        creation_flow=_parse_creation_flow_partial(data.get("creation_flow")),
        parent=str(parent_raw) if parent_raw else None,
    )


def _resolve_genre_constraints(chain: list[_SettingConfig], yaml_path: str) -> GenreConstraints:
    def pick_str(attr: str) -> str:
        for cfg in chain:
            val = getattr(cfg.genre_constraints, attr)
            if val is not None:
                return str(val)
        raise KeyError(f"genre_constraints.{attr} missing in setting chain ending at {yaml_path}")

    def pick_int(attr: str) -> int:
        for cfg in chain:
            val = getattr(cfg.genre_constraints, attr)
            if val is not None:
                return int(val)
        raise KeyError(f"genre_constraints.{attr} missing in setting chain ending at {yaml_path}")

    def pick_str_list(attr: str) -> list[str]:
        for cfg in chain:
            val = getattr(cfg.genre_constraints, attr)
            if val is not None:
                return [str(item) for item in val]
        raise KeyError(f"genre_constraints.{attr} missing in setting chain ending at {yaml_path}")

    def pick_optional_dict(attr: str) -> dict[str, list[str]]:
        for cfg in chain:
            val = getattr(cfg.genre_constraints, attr)
            if val is not None:
                return {str(k): [str(item) for item in v] for k, v in val.items()}
        return {}

    return GenreConstraints(
        forbidden_terms=pick_str_list("forbidden_terms"),
        forbidden_concepts=pick_str_list("forbidden_concepts"),
        genre_test=pick_str("genre_test"),
        atmospheric_drift_universal=pick_str_list("atmospheric_drift_universal"),
        atmospheric_drift_overlays=pick_optional_dict("atmospheric_drift_overlays"),
        atmospheric_drift_threshold=pick_int("atmospheric_drift_threshold"),
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
        names=pick_str_list("names"),
        backstory=pick_str("backstory"),
        factions=pick_str("factions"),
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

        chain: list[_SettingConfig] = [config]
        ancestor = parent
        while ancestor is not None:
            chain.append(ancestor._config)
            ancestor = ancestor._parent

        self._oracle_paths = _resolve_oracle_paths(chain, yaml_path)
        self._genre_constraints = _resolve_genre_constraints(chain, yaml_path)
        self._creation_flow = _resolve_creation_flow(chain, yaml_path)

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
    def genre_constraints(self) -> GenreConstraints:
        return self._genre_constraints

    @property
    def oracle_paths(self) -> OraclePaths:
        return self._oracle_paths

    @property
    def creation_flow(self) -> CreationFlow:
        return self._creation_flow

    def roll_action_theme(self) -> tuple[str, str]:
        paths = self._oracle_paths.action_theme
        if len(paths) >= 2:
            action = self._data.roll_oracle(paths[0])
            theme = self._data.roll_oracle(paths[1])
            return action, theme
        return "", ""

    def oracle_data_for(self, oracle_path: str) -> Setting | None:
        pkg: SettingPackage | None = self
        while pkg is not None:
            if pkg._data.oracle(oracle_path) is not None:
                return pkg._data
            pkg = pkg._parent
        return None

    def backstory_prompts(self) -> OracleTable | None:
        path = self._oracle_paths.backstory
        if not path:
            return None
        data = self.oracle_data_for(path)
        if data is None:
            return None
        return data.oracle(path)

    def name_tables(self) -> dict[str, OracleTable]:
        result: dict[str, OracleTable] = {}
        for path in self._oracle_paths.names:
            data = self.oracle_data_for(path)
            if data is None:
                continue
            table = data.oracle(path)
            if table is None:
                continue
            short_id = path.rsplit("/", 1)[-1]
            result[short_id] = table
        return result


_cache: dict[str, SettingPackage] = {}


def list_packages() -> list[str]:
    if not _SETTINGS_DIR.exists():
        return []
    return sorted(p.stem for p in _SETTINGS_DIR.glob("*.yaml"))


def _read_yaml(setting_id: str) -> tuple[dict, Path]:
    yaml_path = _SETTINGS_DIR / f"{setting_id}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Setting package not found: {yaml_path}")
    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw, yaml_path


def parent_of(setting_id: str) -> str | None:
    raw, _ = _read_yaml(setting_id)
    parent = raw.get("parent")
    return str(parent) if parent else None


def datasworn_id_of(setting_id: str) -> str:
    raw, yaml_path = _read_yaml(setting_id)
    if "datasworn_id" not in raw:
        raise KeyError(f"Required key 'datasworn_id' missing in {yaml_path}")
    return str(raw["datasworn_id"])


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


def active_package(game: GameState) -> SettingPackage | None:
    if not game.setting_id:
        return None
    return load_package(game.setting_id)
