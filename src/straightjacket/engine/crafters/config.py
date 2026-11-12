from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.gamemaster.config_types import ClockCreationMappingEntry
from straightjacket.engine.logging_util import log
from straightjacket.engine.serialization import build_strict
from straightjacket.engine.yaml_merge import load_yaml_dir

if TYPE_CHECKING:
    from pathlib import Path

_CONFIG_DIR = PROJECT_ROOT / "crafters"


@dataclass
class AdventureCrafterDiceConfig:
    table_die: int
    theme_die: int


@dataclass
class PlotPointRanges:
    conclusion_min: int
    conclusion_max: int
    none_min: int
    none_max: int
    meta_min: int
    meta_max: int


@dataclass
class MetaHandlerConfig:
    weight_delta_step_up: int
    weight_delta_step_down: int
    weight_delta_upgrade: int
    weight_delta_downgrade: int
    weight_floor: int


@dataclass
class BlueprintConfig:
    possible_endings_per_blueprint: int
    voicing_count_retries: int
    act_phases: list[str]


@dataclass
class KeyedSceneMappingEntry:
    trigger_type: str
    trigger_value: str
    priority: int
    narrative_hint: str


@dataclass
class AdventureCrafterConfig:
    themes: list[str]
    theme_slots: int
    theme_die_table: dict[int, str]
    special_ranges: PlotPointRanges
    meta_handlers: MetaHandlerConfig
    blueprint: BlueprintConfig
    max_keyed_scenes_per_chapter: int
    keyed_scene_mapping: dict[str, KeyedSceneMappingEntry]
    danger_plot_points: list[str]
    clock_creation_mapping: dict[str, ClockCreationMappingEntry]
    plotline_name_template: str
    returning_character_name_template: str
    identity_roll_twice_row: str
    descriptor_roll_twice_row: str
    present_character_statuses: list[str]


@dataclass
class CrafterSettings:
    adventure_crafter: AdventureCrafterConfig
    adventure_crafter_dice: AdventureCrafterDiceConfig


_cache: dict[Path, CrafterSettings] = {}


def crafter() -> CrafterSettings:
    if _CONFIG_DIR not in _cache:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The crafters/ directory ships with the repo.")
        _cache[_CONFIG_DIR] = build_strict(CrafterSettings, data, "crafters")
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _cache[_CONFIG_DIR]
