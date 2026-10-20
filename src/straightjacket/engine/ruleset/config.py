from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config_binding import RawSections, build_strict, reject_unknown
from ..config_loader import PROJECT_ROOT
from ..logging_util import log
from ..yaml_merge import load_yaml_dir
from .config_types import (
    ActiveTrackCondition,
    BoastOption,
    BoastsConfig,
    BondedTrackCondition,
    CombatPosCondition,
    ConnectionAidConfig,
    CreationConfig,
    DiceConfig,
    DyingClockConfig,
    EngineMove,
    ForsakeVowConfig,
    InheritanceConfig,
    LegacyConfig,
    MetersConfig,
    MomentumConfig,
    MoveAvailabilityCondition,
    MoveAvailabilityRule,
    NoActiveTrackCondition,
    NpcCarryoverEntry,
    PayThePriceConfig,
    PayThePriceSufferRow,
    ProgressConfig,
    RollBonusesConfig,
    StatsConfig,
    StrainConfig,
    SuccessionConfig,
    SufferConfig,
    SufferRecoveryGain,
    SufferTableRow,
    ThreatConfig,
    ThreatCreationMappingEntry,
)

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
    boasts: BoastsConfig
    succession: SuccessionConfig
    pay_the_price: PayThePriceConfig
    suffer: SufferConfig
    roll_bonuses: RollBonusesConfig
    strain: StrainConfig
    advantage_moves: list[str]
    information_moves: list[str]

    _raw: dict[str, Any] = field(default_factory=dict, repr=False)


_SIMPLE_SECTIONS: dict[str, type] = {
    "dice": DiceConfig,
    "stats": StatsConfig,
    "creation": CreationConfig,
    "meters": MetersConfig,
    "progress": ProgressConfig,
    "strain": StrainConfig,
}


def _known_track_type(track_type: str, track_types: set[str]) -> str:
    if track_type not in track_types:
        raise ValueError(f"move_availability names {track_type!r}, which is no track type of track_types_by_category")
    return track_type


def _parse_move_availability_condition(cond: dict[str, Any], track_types: set[str]) -> MoveAvailabilityCondition:
    keys = set(cond.keys())
    if keys == {"active_track"}:
        return ActiveTrackCondition(active_track=_known_track_type(cond["active_track"], track_types))
    if keys == {"no_active_track"}:
        return NoActiveTrackCondition(no_active_track=_known_track_type(cond["no_active_track"], track_types))
    if keys == {"bonded_track"}:
        return BondedTrackCondition(bonded_track=_known_track_type(cond["bonded_track"], track_types))
    if keys == {"combat_pos_in"}:
        return CombatPosCondition(combat_pos_in=list(cond["combat_pos_in"]))
    raise ValueError(
        f"Invalid move_availability condition: {cond!r}. "
        "Expected exactly one of: active_track, no_active_track, bonded_track, combat_pos_in."
    )


def _parse_move_availability_rule(rule: dict[str, Any], track_types: set[str]) -> MoveAvailabilityRule:
    keys = set(rule.keys())
    if keys == {"never"}:
        if not rule["never"]:
            raise ValueError(f"move_availability rule with never=false is not allowed: {rule!r}")
        return MoveAvailabilityRule(never=True, available=[])
    if keys == {"available"}:
        conds = [_parse_move_availability_condition(dict(c), track_types) for c in rule["available"]]
        return MoveAvailabilityRule(never=False, available=conds)
    raise ValueError(f"Invalid move_availability rule: {rule!r}. Expected exactly one of: never, available.")


def _build_threats(t_raw: dict[str, Any]) -> ThreatConfig:
    reject_unknown(ThreatConfig, t_raw)
    by_origin = {
        origin: build_strict(ThreatCreationMappingEntry, dict(entry)) for origin, entry in t_raw["by_origin"].items()
    }
    return ThreatConfig(**{**t_raw, "by_origin": by_origin})


def _build_pay_the_price(ptp_raw: dict[str, Any]) -> PayThePriceConfig:
    reject_unknown(PayThePriceConfig, ptp_raw)
    return PayThePriceConfig(
        move=ptp_raw["move"],
        table=ptp_raw["table"],
        match_miss_table=ptp_raw["match_miss_table"],
        worse_reroll_prefixes=[str(prefix) for prefix in ptp_raw["worse_reroll_prefixes"]],
        suffer_rows=[build_strict(PayThePriceSufferRow, dict(row)) for row in ptp_raw["suffer_rows"]],
    )


def _build_suffer(s_raw: dict[str, Any]) -> SufferConfig:
    reject_unknown(SufferConfig, s_raw)
    return SufferConfig(
        endure_moves={str(k): str(v) for k, v in dict(s_raw["endure_moves"]).items()},
        exhausted_impacts={str(k): str(v) for k, v in dict(s_raw["exhausted_impacts"]).items()},
        swear_move=s_raw["swear_move"],
        table_rows=[build_strict(SufferTableRow, dict(row)) for row in s_raw["table_rows"]],
        dying_clock=build_strict(DyingClockConfig, dict(s_raw["dying_clock"])),
        forsake_vow=build_strict(ForsakeVowConfig, dict(s_raw["forsake_vow"])),
    )


def _build_roll_bonuses(rb_raw: dict[str, Any]) -> RollBonusesConfig:
    reject_unknown(RollBonusesConfig, rb_raw)
    return RollBonusesConfig(
        condition_chars=rb_raw["condition_chars"],
        connection_aid={
            ruleset: build_strict(ConnectionAidConfig, dict(aid))
            for ruleset, aid in dict(rb_raw["connection_aid"]).items()
        },
    )


def _build_boasts(b_raw: dict[str, Any]) -> BoastsConfig:
    options = {
        name: build_strict(BoastOption, {**spec, "effects": list(spec["effects"])})
        for name, spec in dict(b_raw.pop("options")).items()
    }
    config: BoastsConfig = build_strict(BoastsConfig, {**b_raw, "options": options})
    return config


def _build_succession(succession_raw: dict[str, Any]) -> SuccessionConfig:
    reject_unknown(SuccessionConfig, succession_raw)
    return SuccessionConfig(
        inheritance=build_strict(InheritanceConfig, dict(succession_raw["inheritance"])),
        npc_carryover={
            status: build_strict(NpcCarryoverEntry, dict(entry))
            for status, entry in succession_raw["npc_carryover"].items()
        },
    )


def parse_ruleset_yaml(data: dict[str, Any]) -> RulesetSettings:
    simple: dict[str, Any] = {key: build_strict(cls, data[key]) for key, cls in _SIMPLE_SECTIONS.items()}
    m_data = dict(data["momentum"])
    recovery = build_strict(SufferRecoveryGain, dict(m_data.pop("suffer_recovery")))
    legacy_data = dict(data["legacy"])
    legacy_data["ticks_by_rank"] = dict(legacy_data["ticks_by_rank"])
    gated_track_types = set(data["track_types_by_category"].values())
    return RulesetSettings(
        **simple,
        momentum=MomentumConfig(**m_data, suffer_recovery=recovery),
        threats=_build_threats(dict(data["threats"])),
        legacy=build_strict(LegacyConfig, legacy_data),
        engine_moves={
            key: build_strict(EngineMove, {**m, "stats": list(m["stats"])}) for key, m in data["engine_moves"].items()
        },
        move_availability={
            key: _parse_move_availability_rule(rule, gated_track_types)
            for key, rule in data["move_availability"].items()
        },
        unoffered_roll_types=list(data["unoffered_roll_types"]),
        boasts=_build_boasts(dict(data["boasts"])),
        succession=_build_succession(dict(data["succession"])),
        pay_the_price=_build_pay_the_price(dict(data["pay_the_price"])),
        suffer=_build_suffer(dict(data["suffer"])),
        roll_bonuses=_build_roll_bonuses(dict(data["roll_bonuses"])),
        advantage_moves=list(data["advantage_moves"]),
        information_moves=list(data["information_moves"]),
        _raw=data,
    )


_rules: RulesetSettings | None = None


def rules() -> RulesetSettings:
    global _rules
    if _rules is None:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The ruleset/ directory ships with the repo.")
        _rules = parse_ruleset_yaml(data)
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _rules
