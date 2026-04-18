#!/usr/bin/env python3
"""Setting package loader.

Combines a settings.yaml (vocabulary, genre constraints, metadata)
with its Datasworn JSON data (oracles, assets, moves, truths) into
a single SettingPackage object.

Parse model is strict: every required top-level key in the yaml must
be present or parsing raises KeyError. Parent-chain inheritance is
expressed by *omitting* a key in the child yaml; presence of a key
(even with an empty value) is an explicit override.

Top-level required keys per yaml:
    id, title, datasworn_id, description,
    oracle_paths, vocabulary, genre_constraints
Top-level optional keys (inherit from parent when absent):
    parent, creation_flow

Within oracle_paths, genre_constraints, and creation_flow, individual
fields are per-field inheritable: an absent field inherits from parent,
a present field (even if empty) is an explicit override.

Within vocabulary, inheritance is section-level: if both substitutions
and sensory_palette are absent or empty, the whole block inherits.

Usage:
    from straightjacket.engine.datasworn.settings import load_package, list_packages

    packages = list_packages()  # ['classic', 'delve', 'starforged', 'sundered_isles']
    pkg = load_package("starforged")
    pkg.title                   # "Ironsworn: Starforged"
    pkg.vocabulary              # resolved VocabularyConfig
    pkg.genre_constraints       # resolved GenreConstraints
    pkg.oracle_paths            # resolved OraclePaths
    pkg.creation_flow           # resolved CreationFlow
    pkg.data                    # Datasworn Setting object (oracles, assets, etc.)
    pkg.roll_action_theme()     # ("Distract", "Path") — meaning pair
"""

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


# ── Resolved, fully-specified dataclasses (what callers see) ──


@dataclass
class GenreConstraints:
    """Resolved genre constraints. Every field explicit after parent-chain walk."""

    forbidden_terms: list[str]
    forbidden_concepts: list[str]
    genre_test: str
    atmospheric_drift: list[str]
    atmospheric_drift_threshold: int


@dataclass
class VocabularyConfig:
    """Resolved world-specific vocabulary substitutions and sensory palette."""

    substitutions: dict[str, str]
    sensory_palette: str

    def is_empty(self) -> bool:
        return not self.substitutions and not self.sensory_palette


@dataclass
class OraclePaths:
    """Resolved oracle path mappings for character creation."""

    action_theme: list[str]
    descriptor_focus: list[str]
    names: list[str]
    backstory: str
    factions: str


@dataclass
class CreationFlow:
    """Resolved character creation flow flags for the client UI."""

    has_truths: bool
    has_backstory_oracle: bool
    has_name_tables: bool
    has_ship_creation: bool
    starting_asset_categories: list[str]


# ── Partial config dataclasses (parse output, None = inherit) ──


@dataclass
class _GenreConstraintsPartial:
    """Parsed genre_constraints block. None per field = key absent in yaml."""

    forbidden_terms: list[str] | None = None
    forbidden_concepts: list[str] | None = None
    genre_test: str | None = None
    atmospheric_drift: list[str] | None = None
    atmospheric_drift_threshold: int | None = None


@dataclass
class _OraclePathsPartial:
    """Parsed oracle_paths block. None per field = key absent in yaml."""

    action_theme: list[str] | None = None
    descriptor_focus: list[str] | None = None
    names: list[str] | None = None
    backstory: str | None = None
    factions: str | None = None


@dataclass
class _CreationFlowPartial:
    """Parsed creation_flow block. None per field = key absent in yaml.

    Used when the whole creation_flow key is absent as well: all fields None.
    """

    has_truths: bool | None = None
    has_backstory_oracle: bool | None = None
    has_name_tables: bool | None = None
    has_ship_creation: bool | None = None
    starting_asset_categories: list[str] | None = None


@dataclass
class _SettingConfig:
    """Strictly-parsed settings.yaml. All required fields non-None.

    `parent` is optional (None when absent). Sub-blocks are partial dataclasses
    that carry per-field None to signal inheritance.
    """

    id: str
    title: str
    datasworn_id: str
    description: str
    oracle_paths: _OraclePathsPartial
    vocabulary: VocabularyConfig
    genre_constraints: _GenreConstraintsPartial
    creation_flow: _CreationFlowPartial
    parent: str | None


# ── Parsing: strict on top-level keys, partial on inheritable sub-fields ──


def _require(data: dict, key: str, yaml_path: str) -> object:
    """Read a required yaml key. Raise KeyError with context if missing."""
    if key not in data:
        raise KeyError(f"Required key '{key}' missing in {yaml_path}")
    return data[key]


def _parse_oracle_paths_partial(data: dict) -> _OraclePathsPartial:
    """Parse oracle_paths block. Each field optional; absence means inherit."""
    partial = _OraclePathsPartial()
    if "action_theme" in data:
        partial.action_theme = list(data["action_theme"])
    if "descriptor_focus" in data:
        partial.descriptor_focus = list(data["descriptor_focus"])
    if "names" in data:
        partial.names = list(data["names"])
    if "backstory" in data:
        partial.backstory = data["backstory"]
    if "factions" in data:
        partial.factions = data["factions"]
    return partial


def _parse_vocabulary(data: dict) -> VocabularyConfig:
    """Parse vocabulary block. Uses section-level inheritance via is_empty()."""
    return VocabularyConfig(
        substitutions=dict(data.get("substitutions", {})),
        sensory_palette=data.get("sensory_palette", ""),
    )


def _parse_genre_constraints_partial(data: dict) -> _GenreConstraintsPartial:
    """Parse genre_constraints block. Each field optional; absence means inherit."""
    partial = _GenreConstraintsPartial()
    if "forbidden_terms" in data:
        partial.forbidden_terms = list(data["forbidden_terms"])
    if "forbidden_concepts" in data:
        partial.forbidden_concepts = list(data["forbidden_concepts"])
    if "genre_test" in data:
        partial.genre_test = data["genre_test"]
    if "atmospheric_drift" in data:
        partial.atmospheric_drift = list(data["atmospheric_drift"])
    if "atmospheric_drift_threshold" in data:
        partial.atmospheric_drift_threshold = int(data["atmospheric_drift_threshold"])
    return partial


def _parse_creation_flow_partial(data: dict | None) -> _CreationFlowPartial:
    """Parse creation_flow block. Whole block may be absent (all fields None)."""
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
    """Parse raw settings.yaml dict into strictly-typed _SettingConfig.

    Raises KeyError on missing required top-level keys.
    """
    parent_raw = data.get("parent")
    return _SettingConfig(
        id=str(_require(data, "id", yaml_path)),
        title=str(_require(data, "title", yaml_path)),
        datasworn_id=str(_require(data, "datasworn_id", yaml_path)),
        description=str(_require(data, "description", yaml_path)),
        oracle_paths=_parse_oracle_paths_partial(_require(data, "oracle_paths", yaml_path)),  # type: ignore[arg-type]
        vocabulary=_parse_vocabulary(_require(data, "vocabulary", yaml_path)),  # type: ignore[arg-type]
        genre_constraints=_parse_genre_constraints_partial(_require(data, "genre_constraints", yaml_path)),  # type: ignore[arg-type]
        creation_flow=_parse_creation_flow_partial(data.get("creation_flow")),
        parent=str(parent_raw) if parent_raw else None,
    )


# ── Per-field parent-chain resolution ─────────────────────────


def _resolve_genre_constraints(chain: list[_SettingConfig], yaml_path: str) -> GenreConstraints:
    """Walk chain (child → root) and pick first non-None for each field."""

    def pick(attr: str) -> object:
        for cfg in chain:
            val = getattr(cfg.genre_constraints, attr)
            if val is not None:
                return val
        raise KeyError(f"genre_constraints.{attr} missing in setting chain ending at {yaml_path}")

    return GenreConstraints(
        forbidden_terms=pick("forbidden_terms"),  # type: ignore[arg-type]
        forbidden_concepts=pick("forbidden_concepts"),  # type: ignore[arg-type]
        genre_test=pick("genre_test"),  # type: ignore[arg-type]
        atmospheric_drift=pick("atmospheric_drift"),  # type: ignore[arg-type]
        atmospheric_drift_threshold=pick("atmospheric_drift_threshold"),  # type: ignore[arg-type]
    )


def _resolve_oracle_paths(chain: list[_SettingConfig], yaml_path: str) -> OraclePaths:
    """Walk chain (child → root) and pick first non-None for each field."""

    def pick(attr: str) -> object:
        for cfg in chain:
            val = getattr(cfg.oracle_paths, attr)
            if val is not None:
                return val
        raise KeyError(f"oracle_paths.{attr} missing in setting chain ending at {yaml_path}")

    return OraclePaths(
        action_theme=pick("action_theme"),  # type: ignore[arg-type]
        descriptor_focus=pick("descriptor_focus"),  # type: ignore[arg-type]
        names=pick("names"),  # type: ignore[arg-type]
        backstory=pick("backstory"),  # type: ignore[arg-type]
        factions=pick("factions"),  # type: ignore[arg-type]
    )


def _resolve_creation_flow(chain: list[_SettingConfig], yaml_path: str) -> CreationFlow:
    """Walk chain (child → root) and pick first non-None for each field."""

    def pick(attr: str) -> object:
        for cfg in chain:
            val = getattr(cfg.creation_flow, attr)
            if val is not None:
                return val
        raise KeyError(f"creation_flow.{attr} missing in setting chain ending at {yaml_path}")

    return CreationFlow(
        has_truths=pick("has_truths"),  # type: ignore[arg-type]
        has_backstory_oracle=pick("has_backstory_oracle"),  # type: ignore[arg-type]
        has_name_tables=pick("has_name_tables"),  # type: ignore[arg-type]
        has_ship_creation=pick("has_ship_creation"),  # type: ignore[arg-type]
        starting_asset_categories=pick("starting_asset_categories"),  # type: ignore[arg-type]
    )


# ── Setting package ───────────────────────────────────────────


class SettingPackage:
    """A complete setting: resolved typed config + Datasworn data.

    Inheritance is resolved eagerly at construction time using a chain
    built from the parent pointer in each setting's yaml. The chain walks
    child first, root last; the first non-None value wins per field.
    """

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

        # Vocabulary: section-level inheritance. Empty local block → parent's resolved vocab.
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
        """The Datasworn Setting object (oracles, assets, moves, truths)."""
        return self._data

    @property
    def parent(self) -> SettingPackage | None:
        """Parent package in the inheritance chain, or None for a root setting."""
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

    # ── Convenience: meaning pair rolls ───────────────────────

    def roll_action_theme(self) -> tuple[str, str]:
        """Roll action + theme meaning pair. Empty strings if pair not configured."""
        paths = self._oracle_paths.action_theme
        if len(paths) >= 2:
            action = self._data.roll_oracle(paths[0])
            theme = self._data.roll_oracle(paths[1])
            return action, theme
        return "", ""

    def roll_descriptor_focus(self) -> tuple[str, str]:
        """Roll descriptor + focus meaning pair. Empty strings if not configured."""
        paths = self._oracle_paths.descriptor_focus
        if len(paths) >= 2:
            desc = self._data.roll_oracle(paths[0])
            focus = self._data.roll_oracle(paths[1])
            return desc, focus
        return "", ""

    # ── Character creation data (walk parent chain for oracle data) ──

    def oracle_data_for(self, oracle_path: str) -> Setting | None:
        """Find the Datasworn data in this chain that contains the given oracle path."""
        pkg: SettingPackage | None = self
        while pkg is not None:
            if pkg._data.oracle(oracle_path) is not None:
                return pkg._data
            pkg = pkg._parent
        return None

    def backstory_prompts(self) -> OracleTable | None:
        """Backstory prompts oracle, read from oracle_paths.backstory.

        Walks the parent chain to find the package whose Datasworn data
        actually holds the oracle (paths may be declared in an expansion
        while data lives in the parent).
        """
        path = self._oracle_paths.backstory
        if not path:
            return None
        data = self.oracle_data_for(path)
        if data is None:
            return None
        return data.oracle(path)

    def name_tables(self) -> dict[str, OracleTable]:
        """Character name oracle tables keyed by the last path segment.

        Reads oracle_paths.names and resolves each path against the chain's
        Datasworn data.
        """
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


# ── Discovery and caching ─────────────────────────────────────

_cache: dict[str, SettingPackage] = {}


def list_packages() -> list[str]:
    """List available setting package IDs by scanning the settings directory."""
    if not _SETTINGS_DIR.exists():
        return []
    return sorted(p.stem for p in _SETTINGS_DIR.glob("*.yaml"))


def _read_yaml(setting_id: str) -> tuple[dict, Path]:
    """Load a setting yaml as raw dict. Used by lightweight accessors."""
    yaml_path = _SETTINGS_DIR / f"{setting_id}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Setting package not found: {yaml_path}")
    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw, yaml_path


def parent_of(setting_id: str) -> str | None:
    """Read the parent setting id from a settings.yaml without loading the full package."""
    raw, _ = _read_yaml(setting_id)
    parent = raw.get("parent")
    return str(parent) if parent else None


def datasworn_id_of(setting_id: str) -> str:
    """Read the datasworn_id from a settings.yaml without loading the full package."""
    raw, yaml_path = _read_yaml(setting_id)
    if "datasworn_id" not in raw:
        raise KeyError(f"Required key 'datasworn_id' missing in {yaml_path}")
    return str(raw["datasworn_id"])


def load_package(setting_id: str) -> SettingPackage:
    """Load a setting package by ID. Cached after first load.

    Loads settings.yaml and Datasworn JSON. If the setting has a parent,
    the parent is loaded first and inheritance is resolved per field.

    Raises:
        FileNotFoundError: if the settings.yaml or Datasworn JSON is missing.
        KeyError: if required yaml keys are absent or the inheritance chain
                  does not cover every required field.
    """
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
    """Clear the package cache."""
    _cache.clear()


def active_package(game: GameState) -> SettingPackage | None:
    """Get the active setting package for a game.

    Returns None only when the game has no setting_id set (a legitimate
    state during setup). An invalid setting_id raises FileNotFoundError —
    a running game must never point at a nonexistent setting.
    """
    if not game.setting_id:
        return None
    return load_package(game.setting_id)
