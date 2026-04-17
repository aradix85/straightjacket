#!/usr/bin/env python3
"""Setting package loader.

Combines a settings.yaml (vocabulary, genre constraints, metadata)
with its Datasworn JSON data (oracles, assets, moves, truths) into
a single SettingPackage object.

Usage:
    from straightjacket.engine.datasworn.settings import load_package, list_packages

    packages = list_packages()  # ['classic', 'delve', 'starforged', 'sundered_isles']
    pkg = load_package("starforged")
    pkg.title                   # "Ironsworn: Starforged"
    pkg.vocabulary              # typed VocabularyConfig
    pkg.genre_constraints       # typed GenreConstraints
    pkg.data                    # Datasworn Setting object (oracles, assets, etc.)
    pkg.roll_action_theme()     # ("Distract", "Path") — meaning pair
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import yaml

from ..config_loader import PROJECT_ROOT
from ..logging_util import log
from .loader import Setting, load_setting

if TYPE_CHECKING:
    from ..models import GameState

_SETTINGS_DIR = PROJECT_ROOT / "data" / "settings"


# ── Typed config dataclasses ─────────────────────────────────


@dataclass
class GenreConstraints:
    """Genre constraints for validator integration."""

    forbidden_terms: list[str] = field(default_factory=list)
    forbidden_concepts: list[str] = field(default_factory=list)
    genre_test: str = ""
    atmospheric_drift: list[str] = field(default_factory=list)
    atmospheric_drift_threshold: int = 3

    def is_empty(self) -> bool:
        """True if all constraint fields are empty — signals 'inherit from parent'."""
        return (
            not self.forbidden_terms
            and not self.forbidden_concepts
            and not self.genre_test
            and not self.atmospheric_drift
        )


@dataclass
class VocabularyConfig:
    """World-specific vocabulary substitutions and sensory palette."""

    substitutions: dict[str, str] = field(default_factory=dict)
    sensory_palette: str = ""

    def is_empty(self) -> bool:
        return not self.substitutions and not self.sensory_palette


@dataclass
class OraclePaths:
    """Oracle path mappings for character creation."""

    action_theme: list[str] = field(default_factory=list)
    descriptor_focus: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    backstory: str = ""
    factions: str = ""


@dataclass
class CreationFlow:
    """Character creation flow flags for the client UI."""

    has_truths: bool = False
    has_backstory_oracle: bool = False
    has_name_tables: bool = False
    has_ship_creation: bool = False
    starting_asset_categories: list[str] = field(default_factory=list)


@dataclass
class SettingConfig:
    """Parsed settings.yaml — complete typed config for a setting package."""

    id: str = ""
    title: str = ""
    datasworn_id: str = ""
    description: str = ""
    parent: str = ""
    oracle_paths: OraclePaths = field(default_factory=OraclePaths)
    vocabulary: VocabularyConfig = field(default_factory=VocabularyConfig)
    genre_constraints: GenreConstraints = field(default_factory=GenreConstraints)
    creation_flow: CreationFlow = field(default_factory=CreationFlow)


def _parse_setting_config(data: dict) -> SettingConfig:
    """Parse raw settings.yaml dict into typed SettingConfig."""
    cfg = SettingConfig(
        id=data.get("id", ""),
        title=data.get("title", ""),
        datasworn_id=data.get("datasworn_id", ""),
        description=data.get("description", ""),
        parent=data.get("parent", ""),
    )

    op = data.get("oracle_paths", {})
    cfg.oracle_paths = OraclePaths(
        action_theme=list(op.get("action_theme", [])),
        descriptor_focus=list(op.get("descriptor_focus", [])),
        names=list(op.get("names", [])),
        backstory=op.get("backstory", ""),
        factions=op.get("factions", ""),
    )

    vd = data.get("vocabulary", {})
    cfg.vocabulary = VocabularyConfig(
        substitutions=dict(vd.get("substitutions", {})),
        sensory_palette=vd.get("sensory_palette", ""),
    )

    gc = data.get("genre_constraints", {})
    cfg.genre_constraints = GenreConstraints(
        forbidden_terms=list(gc.get("forbidden_terms", [])),
        forbidden_concepts=list(gc.get("forbidden_concepts", [])),
        genre_test=gc.get("genre_test", ""),
        atmospheric_drift=list(gc.get("atmospheric_drift", [])),
        # TODO tranche 2: atmospheric_drift_threshold default is a Python-literal
        # fallback. The parent-chain resolver should inject it from the parent
        # setting's yaml, not hardcode 3 here.
        atmospheric_drift_threshold=gc.get("atmospheric_drift_threshold", 3),
    )

    flow = data.get("creation_flow", {})
    cfg.creation_flow = CreationFlow(
        has_truths=flow.get("has_truths", False),
        has_backstory_oracle=flow.get("has_backstory_oracle", False),
        has_name_tables=flow.get("has_name_tables", False),
        has_ship_creation=flow.get("has_ship_creation", False),
        starting_asset_categories=list(flow.get("starting_asset_categories", [])),
    )

    return cfg


# ── Setting package ───────────────────────────────────────────


class SettingPackage:
    """A complete setting: typed config + Datasworn data."""

    def __init__(self, config: SettingConfig, data: Setting, parent: SettingPackage | None = None):
        self._config = config
        self._data = data
        self._parent = parent

    @property
    def id(self) -> str:
        return self._config.id

    @property
    def title(self) -> str:
        return self._config.title or self._data.title

    @property
    def description(self) -> str:
        return self._config.description

    @property
    def data(self) -> Setting:
        """The Datasworn Setting object (oracles, assets, moves, truths)."""
        return self._data

    @property
    def vocabulary(self) -> VocabularyConfig:
        """Vocabulary. Inherits from parent if empty."""
        if self._config.vocabulary.is_empty() and self._parent:
            return self._parent.vocabulary
        return self._config.vocabulary

    @property
    def genre_constraints(self) -> GenreConstraints:
        """Genre constraints. Inherits from parent if empty."""
        if self._config.genre_constraints.is_empty() and self._parent:
            return self._parent.genre_constraints
        return self._config.genre_constraints

    @property
    def oracle_paths(self) -> OraclePaths:
        """Oracle path mappings for character creation."""
        return self._config.oracle_paths

    @property
    def creation_flow(self) -> CreationFlow:
        """Creation flow flags for the client UI."""
        return self._config.creation_flow

    # ── Convenience: meaning pair rolls ───────────────────────

    def roll_action_theme(self) -> tuple[str, str]:
        """Roll action + theme meaning pair."""
        paths = self._config.oracle_paths.action_theme
        if len(paths) >= 2:
            action = self._data.roll_oracle(paths[0])
            theme = self._data.roll_oracle(paths[1])
            return action, theme
        return "", ""

    def roll_descriptor_focus(self) -> tuple[str, str]:
        """Roll descriptor + focus meaning pair."""
        paths = self._config.oracle_paths.descriptor_focus
        if len(paths) >= 2:
            desc = self._data.roll_oracle(paths[0])
            focus = self._data.roll_oracle(paths[1])
            return desc, focus
        return "", ""


_cache: dict[str, SettingPackage] = {}


def list_packages() -> list[str]:
    """List available setting package IDs (those with a settings.yaml)."""
    if not _SETTINGS_DIR.exists():
        return []
    return sorted(p.stem for p in _SETTINGS_DIR.glob("*.yaml"))


def load_package(setting_id: str) -> SettingPackage:
    """Load a setting package by ID. Cached after first load.

    Loads the settings.yaml and its Datasworn JSON data. If the setting
    has a parent (e.g. Delve → Classic), the parent is loaded first and
    vocabulary/constraints inherit from it.

    Raises:
        FileNotFoundError: if the settings.yaml or Datasworn JSON is missing.
    """
    if setting_id in _cache:
        return _cache[setting_id]

    yaml_path = _SETTINGS_DIR / f"{setting_id}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Setting package not found: {yaml_path}\nAvailable: {list_packages()}")

    with open(yaml_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    config = _parse_setting_config(raw)
    datasworn_id = config.datasworn_id or setting_id
    data = load_setting(datasworn_id)

    # Load parent if specified (e.g. Delve inherits from Classic)
    parent = None
    if config.parent:
        parent = load_package(config.parent)

    pkg = SettingPackage(config, data, parent)
    _cache[setting_id] = pkg

    log(f"[Setting] Loaded {setting_id}: {pkg.title}{f' (parent: {config.parent})' if config.parent else ''}")
    return pkg


def clear_cache() -> None:
    """Clear the package cache."""
    _cache.clear()


def active_package(game: GameState) -> SettingPackage | None:
    """Get the active setting package for a game. Returns None if not set or not found."""
    if not game.setting_id:
        return None
    try:
        return load_package(game.setting_id)
    except (FileNotFoundError, KeyError):
        return None
