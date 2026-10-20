from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatsConfig:
    creation_array: list[int]
    prompt_abbreviations: dict[str, str]


@dataclass
class CreationConfig:
    max_paths: int
    max_starting_assets: int
    background_vow_default_rank: str
    pronoun_options: list[str]
    chaos_vow_modifiers: dict[str, list[str]]
    chaos_modifier_values: dict[str, int]


@dataclass
class MetersConfig:
    heavy_loss_amount: int
    crisis_at_zero: list[str]


@dataclass
class SufferRecoveryGain:
    strong_hit_gain: int
    weak_hit_exchange_cost: int


@dataclass
class MomentumConfig:
    floor: int
    max: int
    start: int
    reset_floor: int
    suffer_recovery: SufferRecoveryGain


@dataclass
class StrainConfig:
    meters: list[str]
    below: dict[str, int]
    otherwise: str


@dataclass
class ThreatConfig:
    menace_on_miss: int
    menace_on_random_event: int
    autonomous_tick_chance: float
    autonomous_tick_marks: int
    menace_high_threshold: float
    category_oracle_collection: str
    max_open_emergent: int
    by_origin: dict[str, ThreatCreationMappingEntry]


@dataclass
class LegacyConfig:
    experience_tag: str
    xp_per_box: int
    xp_per_box_after_clear: int
    starting_rank: str
    threat_overcome_bonus: int
    threat_overcome_threshold: float
    asset_upgrade_cost: int
    new_asset_cost: int
    ticks_by_rank: dict[str, int]
    experience_by_rank: dict[str, int]


@dataclass
class ProgressConfig:
    max_ticks: int
    ticks_per_box: int
    ticks_per_mark: dict[str, int]

    @property
    def boxes(self) -> int:
        return self.max_ticks // self.ticks_per_box


@dataclass
class DiceConfig:
    action_die: int
    challenge_die: int
    action_score_max: int
    results_by_dice_beaten: list[str]

    @property
    def hit_results(self) -> list[str]:
        return self.results_by_dice_beaten[1:]


@dataclass
class EngineMove:
    name: str
    stats: list[str]
    roll_type: str

    @property
    def is_action_roll(self) -> bool:
        return self.roll_type == "action_roll"


@dataclass
class ActiveTrackCondition:
    active_track: str


@dataclass
class NoActiveTrackCondition:
    no_active_track: str


@dataclass
class BondedTrackCondition:
    bonded_track: str


@dataclass
class CombatPosCondition:
    combat_pos_in: list[str]


@dataclass
class MoveAvailabilityRule:
    never: bool
    available: list[MoveAvailabilityCondition]


@dataclass
class BoastOption:
    description: str
    effects: list[str]


@dataclass
class BoastsConfig:
    momentum_per_boast: int
    max_per_roll: int
    options: dict[str, BoastOption]


@dataclass
class ThreatCreationMappingEntry:
    rank: str
    category: str


@dataclass
class InheritanceConfig:
    move_name: str
    fraction_by_result: dict[str, float]


@dataclass
class NpcCarryoverEntry:
    keep: bool
    track_fraction: float


@dataclass
class SuccessionConfig:
    inheritance: InheritanceConfig
    npc_carryover: dict[str, NpcCarryoverEntry]


@dataclass
class PayThePriceSufferRow:
    prefix: str
    effect: str


@dataclass
class PayThePriceConfig:
    move: str
    table: str
    match_miss_table: str
    worse_reroll_prefixes: list[str]
    suffer_rows: list[PayThePriceSufferRow]


@dataclass
class SufferTableRow:
    prefix: str
    trigger: str


@dataclass
class DyingClockConfig:
    name: str
    clock_type: str
    segments: int
    trigger_description: str
    meter: str


@dataclass
class ForsakeVowConfig:
    meter: str
    cost: int


@dataclass
class SufferConfig:
    endure_moves: dict[str, str]
    exhausted_impacts: dict[str, str]
    swear_move: str
    table_rows: list[SufferTableRow]
    dying_clock: DyingClockConfig
    forsake_vow: ForsakeVowConfig


@dataclass
class ConnectionAidConfig:
    add: int
    bonded_add: int
    momentum_on_hit: int
    condition: str


@dataclass
class RollBonusesConfig:
    condition_chars: int
    connection_aid: dict[str, ConnectionAidConfig]


MoveAvailabilityCondition = ActiveTrackCondition | NoActiveTrackCondition | BondedTrackCondition | CombatPosCondition
