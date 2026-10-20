from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config_binding import RawSections, build_strict, reject_unknown
from ..config_loader import PROJECT_ROOT
from ..gamemaster.config_types import ClockCreationMappingEntry
from ..logging_util import log
from ..yaml_merge import load_yaml_dir

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
class CrafterSettings(RawSections):
    adventure_crafter: AdventureCrafterConfig
    adventure_crafter_dice: AdventureCrafterDiceConfig

    _raw: dict[str, Any] = field(default_factory=dict, repr=False)


def _build_adventure_crafter(ac_raw: dict[str, Any]) -> AdventureCrafterConfig:
    reject_unknown(AdventureCrafterConfig, ac_raw)
    ac_special = build_strict(PlotPointRanges, dict(ac_raw["special_ranges"]))
    ac_meta_handlers = build_strict(MetaHandlerConfig, dict(ac_raw["meta_handlers"]))
    ac_blueprint_raw = reject_unknown(BlueprintConfig, dict(ac_raw["blueprint"]))
    ac_blueprint = BlueprintConfig(
        possible_endings_per_blueprint=ac_blueprint_raw["possible_endings_per_blueprint"],
        voicing_count_retries=ac_blueprint_raw["voicing_count_retries"],
        act_phases=list(ac_blueprint_raw["act_phases"]),
    )
    ac_keyed_mapping = {
        name: KeyedSceneMappingEntry(
            trigger_type=reject_unknown(KeyedSceneMappingEntry, entry)["trigger_type"],
            trigger_value=entry["trigger_value"],
            priority=entry["priority"],
            narrative_hint=entry["narrative_hint"],
        )
        for name, entry in dict(ac_raw["keyed_scene_mapping"]).items()
    }
    ac_clock_creation = {
        name: build_strict(ClockCreationMappingEntry, dict(entry))
        for name, entry in dict(ac_raw["clock_creation_mapping"]).items()
    }
    return AdventureCrafterConfig(
        themes=list(ac_raw["themes"]),
        theme_slots=ac_raw["theme_slots"],
        theme_die_table={int(k): v for k, v in ac_raw["theme_die_table"].items()},
        special_ranges=ac_special,
        meta_handlers=ac_meta_handlers,
        blueprint=ac_blueprint,
        max_keyed_scenes_per_chapter=ac_raw["max_keyed_scenes_per_chapter"],
        keyed_scene_mapping=ac_keyed_mapping,
        danger_plot_points=list(ac_raw["danger_plot_points"]),
        clock_creation_mapping=ac_clock_creation,
        plotline_name_template=ac_raw["plotline_name_template"],
        returning_character_name_template=ac_raw["returning_character_name_template"],
        identity_roll_twice_row=ac_raw["identity_roll_twice_row"],
        descriptor_roll_twice_row=ac_raw["descriptor_roll_twice_row"],
        present_character_statuses=list(ac_raw["present_character_statuses"]),
    )


def parse_crafters_yaml(data: dict[str, Any]) -> CrafterSettings:
    return CrafterSettings(
        adventure_crafter=_build_adventure_crafter(dict(data["adventure_crafter"])),
        adventure_crafter_dice=build_strict(AdventureCrafterDiceConfig, dict(data["adventure_crafter_dice"])),
        _raw=data,
    )


_crafter: CrafterSettings | None = None


def crafter() -> CrafterSettings:
    global _crafter
    if _crafter is None:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The crafters/ directory ships with the repo.")
        _crafter = parse_crafters_yaml(data)
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _crafter
