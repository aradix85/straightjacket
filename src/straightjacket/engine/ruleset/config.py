from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    HandlerParams,
    LegacyConfig,
    MetersConfig,
    MomentumConfig,
    MoveAvailabilityRule,
    MoveOutcomeConfig,
    MoveTableRow,
    NoActiveTrackCondition,
    OracleMove,
    PayThePriceConfig,
    ProgressConfig,
    RecoveryParams,
    RollBonusesConfig,
    SojournParams,
    StatsConfig,
    StrainConfig,
    SuccessionConfig,
    SufferConfig,
    SufferParams,
    ThreatConfig,
    ThresholdParams,
)
from straightjacket.engine.serialization import build_strict, shaped
from straightjacket.engine.yaml_merge import load_yaml_dir

if TYPE_CHECKING:
    from pathlib import Path

    from straightjacket.engine.ruleset.config_types import MoveAvailabilityCondition

_CONFIG_DIR = PROJECT_ROOT / "ruleset"


@dataclass
class RulesetSettings:
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
    result_outcomes: dict[str, str]
    effect_bonus_moves: dict[str, int]
    action_phrases: dict[str, str]
    move_categories: dict[str, list[str]]
    move_outcomes: dict[str, MoveOutcomeConfig]
    move_outcome_overrides: dict[str, dict[str, MoveOutcomeConfig]]
    oracle_moves: dict[str, OracleMove]
    move_table_rows: dict[str, list[MoveTableRow]]
    time_progression_map: dict[str, str]
    track_creating_moves: dict[str, str]
    tracks_started_on_a_hit: list[str]
    tracks_bonded_on_a_hit: list[str]
    track_types_by_category: dict[str, str]
    progress_mark_categories: dict[str, str]


_TRACK_CONDITIONS: dict[str, type[ActiveTrackCondition | NoActiveTrackCondition | BondedTrackCondition]] = {
    "active_track": ActiveTrackCondition,
    "no_active_track": NoActiveTrackCondition,
    "bonded_track": BondedTrackCondition,
}


def _mapping(section: object, where: str) -> dict[str, object]:
    entries = shaped(section, dict, f"{where}: expected dict")
    return {shaped(key, str, f"{where} key: expected str"): value for key, value in entries.items()}


def _availability_condition(cond: dict[str, object], track_types: set[object], where: str) -> MoveAvailabilityCondition:
    keys = set(cond)
    if keys == {"combat_pos_in"}:
        return build_strict(CombatPosCondition, cond, where)
    for key, condition_type in _TRACK_CONDITIONS.items():
        if keys == {key}:
            condition = build_strict(condition_type, cond, where)
            if cond[key] not in track_types:
                msg = f"move_availability names {cond[key]!r}, which is no track type of track_types_by_category"
                raise ValueError(msg)
            return condition
    msg = (
        f"Invalid move_availability condition: {cond!r}. "
        "Expected exactly one of: active_track, no_active_track, bonded_track, combat_pos_in."
    )
    raise ValueError(msg)


def _availability_rule(rule: dict[str, object], track_types: set[object], where: str) -> MoveAvailabilityRule:
    keys = set(rule)
    if keys == {"never"}:
        if rule["never"] is not True:
            msg = f"move_availability rule with never other than true is not allowed: {rule!r}"
            raise ValueError(msg)
        return MoveAvailabilityRule(never=True, available=[])
    if keys == {"available"}:
        conditions = shaped(rule["available"], list, f"{where}.available: expected list")
        conds = [
            _availability_condition(_mapping(cond, f"{where}.available[{i}]"), track_types, f"{where}.available[{i}]")
            for i, cond in enumerate(conditions)
        ]
        return MoveAvailabilityRule(never=False, available=conds)
    msg = f"Invalid move_availability rule: {rule!r}. Expected exactly one of: never, available."
    raise ValueError(msg)


def _move_availability(section: object, types_by_category: object, where: str) -> dict[str, MoveAvailabilityRule]:
    track_types = set(_mapping(types_by_category, "ruleset.track_types_by_category").values())
    return {
        move: _availability_rule(_mapping(rule, f"{where}.{move}"), track_types, f"{where}.{move}")
        for move, rule in _mapping(section, where).items()
    }


_HANDLER_PARAMS: dict[str, type[HandlerParams]] = {
    "suffer": SufferParams,
    "threshold": ThresholdParams,
    "recovery": RecoveryParams,
    "sojourn": SojournParams,
}
_OUTCOME_TEXTS = ("recommit_on_miss", "downgrade_in")


def _handled_outcome(entry: dict[str, object], where: str) -> MoveOutcomeConfig:
    if set(entry) != {"handler", "params"}:
        msg = f"{where}: a move with a handler holds handler and params, not {sorted(entry)}"
        raise ValueError(msg)
    handler = shaped(entry["handler"], str, f"{where}.handler: expected str")
    if handler not in _HANDLER_PARAMS:
        msg = f"{where}: unknown move-outcome handler {handler!r}. Valid: {sorted(_HANDLER_PARAMS)}."
        raise ValueError(msg)
    params = build_strict(_HANDLER_PARAMS[handler], entry["params"], f"{where}.params")
    return MoveOutcomeConfig(effects={}, recommit_on_miss=None, downgrade_in=None, params=params)


def _move_outcome(entry: dict[str, object], where: str) -> MoveOutcomeConfig:
    if "handler" in entry:
        return _handled_outcome(entry, where)
    texts = {
        key: shaped(entry[key], str, f"{where}.{key}: expected str") if key in entry else None for key in _OUTCOME_TEXTS
    }
    effects = {key: value for key, value in entry.items() if key not in _OUTCOME_TEXTS}
    return build_strict(MoveOutcomeConfig, {"effects": effects, **texts, "params": None}, where)


def _move_outcomes(section: object, where: str) -> dict[str, MoveOutcomeConfig]:
    return {
        move: _move_outcome(_mapping(entry, f"{where}.{move}"), f"{where}.{move}")
        for move, entry in _mapping(section, where).items()
    }


def _move_outcome_overrides(section: object, where: str) -> dict[str, dict[str, MoveOutcomeConfig]]:
    return {
        ruleset: _move_outcomes(outcomes, f"{where}.{ruleset}")
        for ruleset, outcomes in _mapping(section, where).items()
    }


def parse_ruleset_yaml(data: dict[str, object]) -> RulesetSettings:
    return build_strict(
        RulesetSettings,
        data,
        "ruleset",
        move_availability=lambda section, where: _move_availability(section, data["track_types_by_category"], where),
        move_outcomes=_move_outcomes,
        move_outcome_overrides=_move_outcome_overrides,
    )


_cache: dict[Path, RulesetSettings] = {}


def rules() -> RulesetSettings:
    if _CONFIG_DIR not in _cache:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The ruleset/ directory ships with the repo.")
        _cache[_CONFIG_DIR] = parse_ruleset_yaml(data)
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _cache[_CONFIG_DIR]
