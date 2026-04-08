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
    pkg.vocabulary              # substitution dict
    pkg.genre_constraints       # forbidden terms, concepts, test
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

# SETTING PACKAGE


@dataclass
class GenreConstraints:
    """Genre constraints for validator integration."""

    forbidden_terms: list[str] = field(default_factory=list)
    forbidden_concepts: list[str] = field(default_factory=list)
    genre_test: str = ""


class SettingPackage:
    """A complete setting: metadata + vocabulary + constraints + Datasworn data."""

    def __init__(self, config: dict, data: Setting, parent: SettingPackage | None = None):
        self._config = config
        self._data = data
        self._parent = parent

    @property
    def id(self) -> str:
        return self._config.get("id", "")

    @property
    def title(self) -> str:
        return self._config.get("title", self._data.title)

    @property
    def description(self) -> str:
        return self._config.get("description", "")

    @property
    def data(self) -> Setting:
        """The Datasworn Setting object (oracles, assets, moves, truths)."""
        return self._data

    @property
    def vocabulary(self) -> dict[str, str]:
        """Substitution vocabulary. Inherits from parent if empty."""
        subs = self._config.get("vocabulary", {}).get("substitutions", {})
        if not subs and self._parent:
            return self._parent.vocabulary
        return subs

    @property
    def genre_constraints(self) -> GenreConstraints:
        """Genre constraints for validator. Inherits from parent if empty."""
        gc = self._config.get("genre_constraints", {})
        terms = gc.get("forbidden_terms", [])
        concepts = gc.get("forbidden_concepts", [])
        test = gc.get("genre_test", "")
        if not terms and not concepts and not test and self._parent:
            return self._parent.genre_constraints
        return GenreConstraints(
            forbidden_terms=terms,
            forbidden_concepts=concepts,
            genre_test=test,
        )

    @property
    def oracle_paths(self) -> dict:
        """Oracle path mappings for character creation."""
        return self._config.get("oracle_paths", {})

    @property
    def creation_flow(self) -> dict:
        """Creation flow flags for the client UI."""
        defaults = {
            "has_truths": False,
            "has_backstory_oracle": False,
            "has_name_tables": False,
            "has_ship_creation": False,
            "starting_asset_categories": [],
        }
        flow = self._config.get("creation_flow", {})
        return {**defaults, **flow}

    # ── Convenience: meaning pair rolls ───────────────────────

    def roll_action_theme(self) -> tuple[str, str]:
        """Roll action + theme meaning pair."""
        paths = self.oracle_paths.get("action_theme", [])
        if len(paths) >= 2:
            action = self._data.roll_oracle(paths[0])
            theme = self._data.roll_oracle(paths[1])
            return action, theme
        return "", ""

    def roll_descriptor_focus(self) -> tuple[str, str]:
        """Roll descriptor + focus meaning pair."""
        paths = self.oracle_paths.get("descriptor_focus", [])
        if len(paths) >= 2:
            desc = self._data.roll_oracle(paths[0])
            focus = self._data.roll_oracle(paths[1])
            return desc, focus
        return "", ""

    @property
    def raw_config(self) -> dict:
        """Raw settings.yaml dict."""
        return self._config


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
        config = yaml.safe_load(f)

    datasworn_id = config.get("datasworn_id", setting_id)
    data = load_setting(datasworn_id)

    # Load parent if specified (e.g. Delve inherits from Classic)
    parent = None
    parent_id = config.get("parent")
    if parent_id:
        parent = load_package(parent_id)

    pkg = SettingPackage(config, data, parent)
    _cache[setting_id] = pkg

    log(f"[Setting] Loaded {setting_id}: {pkg.title}{f' (parent: {parent_id})' if parent_id else ''}")
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
