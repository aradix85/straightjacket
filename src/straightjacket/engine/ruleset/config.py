from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.config_binding import RawSections, bind_sections, build_strict
from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.logging_util import log
from straightjacket.engine.ruleset.config_types import (
    ActiveTrackCondition,
    BoastsConfig,
    BondedTrackCondition,
    CombatPosCondition,
    CreationConfig,
    DiceConfig,
    EngineMove,
    LegacyConfig,
    MetersConfig,
    MomentumConfig,
    MoveAvailabilityRule,
    NoActiveTrackCondition,
    PayThePriceConfig,
    ProgressConfig,
    RollBonusesConfig,
    StatsConfig,
    StrainConfig,
    SuccessionConfig,
    SufferConfig,
    ThreatConfig,
)
from straightjacket.engine.serialization import shaped
from straightjacket.engine.yaml_merge import load_yaml_dir

if TYPE_CHECKING:
    from pathlib import Path

    from straightjacket.engine.ruleset.config_types import MoveAvailabilityCondition

_CONFIG_DIR = PROJECT_ROOT / "ruleset"


@dataclass
class RulesetSettings(RawSections):
    dice: DiceConfig
    stats: StatsConfig
    creation: CreationConfig
    meters: MetersConfig
    momentum: MomentumConfig
    threats: ThreatConfig
    legacy: LegacyConfig
    progress: ProgressConfig
    engine_moves: dict[str, EngineMove]
    move_availability: dict[str, MoveAvailabilityRule]
    unoffered_roll_types: list[str]
    offered_without_roll: list[str]
    boasts: BoastsConfig
    succession: SuccessionConfig
    pay_the_price: PayThePriceConfig
    suffer: SufferConfig
    roll_bonuses: RollBonusesConfig
    strain: StrainConfig
    advantage_moves: list[str]
    information_moves: list[str]


_TRACK_CONDITIONS: dict[str, type[ActiveTrackCondition | NoActiveTrackCondition | BondedTrackCondition]] = {
    "active_track": ActiveTrackCondition,
    "no_active_track": NoActiveTrackCondition,
    "bonded_track": BondedTrackCondition,
}


def _parse_move_availability_condition(cond: dict[str, object], track_types: set[str]) -> MoveAvailabilityCondition:
    keys = set(cond)
    if keys == {"combat_pos_in"}:
        return build_strict(CombatPosCondition, cond)
    for key, condition_type in _TRACK_CONDITIONS.items():
        if keys == {key}:
            condition = build_strict(condition_type, cond)
            if cond[key] not in track_types:
                msg = f"move_availability names {cond[key]!r}, which is no track type of track_types_by_category"
                raise ValueError(msg)
            return condition
    msg = (
        f"Invalid move_availability condition: {cond!r}. "
        "Expected exactly one of: active_track, no_active_track, bonded_track, combat_pos_in."
    )
    raise ValueError(msg)


def _parse_move_availability_rule(rule: dict[str, object], track_types: set[str]) -> MoveAvailabilityRule:
    keys = set(rule)
    if keys == {"never"}:
        if rule["never"] is not True:
            msg = f"move_availability rule with never other than true is not allowed: {rule!r}"
            raise ValueError(msg)
        return MoveAvailabilityRule(never=True, available=[])
    if keys == {"available"}:
        conditions = shaped(rule["available"], list, "move_availability: expected list")
        conds = [
            _parse_move_availability_condition(
                shaped(c, dict, "a move_availability condition: expected dict"), track_types
            )
            for c in conditions
        ]
        return MoveAvailabilityRule(never=False, available=conds)
    msg = f"Invalid move_availability rule: {rule!r}. Expected exactly one of: never, available."
    raise ValueError(msg)


def parse_ruleset_yaml(data: dict[str, object]) -> RulesetSettings:
    track_types = set(shaped(data["track_types_by_category"], dict, "track_types_by_category: expected dict").values())
    move_availability = {
        key: _parse_move_availability_rule(shaped(rule, dict, f"move_availability.{key}: expected dict"), track_types)
        for key, rule in shaped(data["move_availability"], dict, "move_availability: expected dict").items()
    }
    return bind_sections(RulesetSettings, data, move_availability=move_availability)


_cache: dict[Path, RulesetSettings] = {}


def rules() -> RulesetSettings:
    if _CONFIG_DIR not in _cache:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The ruleset/ directory ships with the repo.")
        _cache[_CONFIG_DIR] = parse_ruleset_yaml(data)
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _cache[_CONFIG_DIR]
