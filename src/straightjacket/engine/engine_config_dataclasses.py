from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NpcConfig:
    max_active: int
    max_memory_entries: int
    max_reflections: int
    activation_threshold: float
    mention_threshold: float
    max_activated: int
    reflection_threshold: int
    memory_recency_decay: float
    reflection_importance: int
    death_corroboration_min_importance: int
    seed_importance_floor: int
    reflection_recency_floor: float
    about_npc_relevance_boost: float
    consolidation_recency_ratio: float
    gate_memory_counts: dict[int, int]
    activated_memory_count: int
    default_new_npc_disposition: str


@dataclass
class ChaosConfig:
    min: int
    max: int
    start: int
    adjust_miss: int
    adjust_strong: int
    adjust_dialog_hostile: int
    adjust_dialog_friendly: int


@dataclass
class PacingConfig:
    director_interval: int
    max_narration_history: int
    max_narration_chars: int
    max_session_log: int
    window_size: int
    intense_threshold: int
    calm_threshold: int
    autonomous_clock_tick_chance: float
    weak_hit_clock_tick_chance: float
    fired_clock_keep_scenes: int
    npc_agency_interval: int
    max_tool_rounds: int


@dataclass
class StatsConfig:
    target_sum: int
    min: int
    max: int
    names: list[str]
    valid_arrays: list[list[int]]
    prompt_abbreviations: dict[str, str]


@dataclass
class CreationConfig:
    max_paths: int
    max_starting_assets: int
    starting_asset_categories: list[str]
    background_vow_default_rank: str
    brain_track_rank_fallback: str
    brain_track_name_max_length: int
    chaos_vow_modifiers: dict[str, list[str]]
    chaos_modifier_values: dict[str, int]
    truth_threads: dict[str, str]


@dataclass
class ResourcesConfig:
    health_max: int
    spirit_max: int
    supply_max: int
    health_start: int
    spirit_start: int
    supply_start: int


@dataclass
class SufferRecoveryGain:
    strong_hit_gain: int
    weak_hit_exchange_cost: int


@dataclass
class MomentumConfig:
    floor: int
    max: int
    start: int
    suffer_recovery: SufferRecoveryGain


@dataclass
class BondsConfig:
    max: int
    start: int


@dataclass
class ActivationScores:
    target: float
    name_match: float
    name_part: float
    alias_match: float
    location_match: float
    recent_interaction: float
    max_recursive: int


@dataclass
class LocationConfig:
    history_size: int
    prompt_history_size: int


@dataclass
class PromptDisplayConfig:
    insight_chars: int
    recent_event_chars: int
    lore_description_chars: int
    lore_max_aliases: int
    epilogue_log_scenes: int
    recent_events_window: int
    campaign_history_chapters: int
    memory_consequences_max: int
    memory_npcs_max: int
    creativity_seed_count: int


@dataclass
class OpeningConfig:
    time_of_day: str
    clock_segments: int
    clock_filled: int
    clock_trigger_template: str


@dataclass
class ArchitectConfig:
    forbidden_moods: list[str]


@dataclass
class ThreatConfig:
    menace_on_miss: int
    autonomous_tick_chance: float
    autonomous_tick_marks: int
    menace_high_threshold: float
    forsake_spirit_cost: int


@dataclass
class ImpactConfig:
    key: str
    label: str
    description: str
    blocks_recovery: str
    permanent: bool


@dataclass
class LegacyConfig:
    xp_per_box: int
    starting_rank: str
    threat_overcome_bonus: int
    threat_overcome_threshold: float
    asset_upgrade_cost: int
    new_asset_cost: int
    ticks_by_rank: dict[str, int]


@dataclass
class ProgressTrackType:
    ticks_per_mark: dict[str, int]


@dataclass
class ProgressConfig:
    max_ticks: int
    track_types: dict[str, ProgressTrackType]

    def ticks_per_mark(self, rank: str, track_type: str = "default") -> int:
        return self.track_types[track_type].ticks_per_mark[rank]


@dataclass
class EngineMove:
    name: str
    stats: list[str]
    roll_type: str


@dataclass
class FlagCondition:
    flag: str


@dataclass
class NotFlagCondition:
    not_flag: str


@dataclass
class CombatPosCondition:
    combat_pos_in: list[str]


MoveAvailabilityCondition = FlagCondition | NotFlagCondition | CombatPosCondition


@dataclass
class MoveAvailabilityRule:
    never: bool
    available: list[MoveAvailabilityCondition]


@dataclass
class StopwordsConfig:
    general: frozenset[str]
    location: frozenset[str]


@dataclass
class PositionResolverWeights:
    resource_critical_below: int
    resource_low_below: int
    resource_critical: int
    resource_low: int
    npc_bond_high: int
    npc_bond_low: int
    chaos_high: int
    chaos_low: int
    consecutive_misses: int
    consecutive_strong: int
    threat_clock_critical: int
    secured_advantage: int


@dataclass
class PositionOverride:
    name: str
    conditions: list[str]
    effect: str


@dataclass
class PositionResolverConfig:
    desperate_below: int
    controlled_above: int
    npc_bond_high_min: int
    npc_bond_low_max: int
    disposition_weights: dict[str, int]
    weights: PositionResolverWeights
    move_baselines: dict[str, int]
    overrides: list[PositionOverride]


@dataclass
class EffectResolverWeights:
    bond_high: int
    bond_low: int
    secured_advantage: int


@dataclass
class EffectResolverConfig:
    limited_below: int
    great_above: int
    bond_high_min: int
    bond_low_max: int
    position_weights: dict[str, int]
    weights: EffectResolverWeights
    move_baselines: dict[str, int]


@dataclass
class InformationGatePoints:
    scenes_known_1: int
    scenes_known_2_3: int
    scenes_known_4_plus: int
    gather_success: int
    bond_1: int
    bond_2_3: int
    bond_4_plus: int


@dataclass
class InformationGateBuckets:
    scenes_known_mid_min: int
    scenes_known_high_min: int
    bond_mid_min: int
    bond_high_min: int


@dataclass
class StanceBondBuckets:
    low_max: int
    mid_max: int


@dataclass
class StanceMoveBuckets:
    mapping: dict[str, str]


@dataclass
class TimeProgressionSteps:
    mapping: dict[str, int]


@dataclass
class NarratorStatusDescriptions:
    health: dict[int, str]
    spirit: dict[int, str]
    supply: dict[int, str]


@dataclass
class CorrectionConfig:
    npc_edit_allowed_fields: list[str]


@dataclass
class StanceMatrixEntry:
    stance: str
    constraint: str


@dataclass
class MemoryEmotions:
    base: dict[str, str]
    disposition_suffix: dict[str, str]


@dataclass
class MemoryTemplates:
    action: str
    action_targeted: str
    dialog: str
    dialog_no_target: str


@dataclass
class SceneContextTemplates:
    template: str
    dialog: str


@dataclass
class SceneAdjustments:
    mapping: dict[str, str]


@dataclass
class InformationGateConfig:
    points: InformationGatePoints
    buckets: InformationGateBuckets
    gate_min: int
    gate_max: int
    stance_caps: dict[str, int]
    fact_budget_by_gate: dict[int, int]


@dataclass
class NarrativeIntensityThresholds:
    critical_below: int
    high_below: int
    moderate_below: int


@dataclass
class NarrativeDirectionEntry:
    tempo: str
    perspective: str


@dataclass
class NarrativeDirectionConfig:
    intensity: NarrativeIntensityThresholds
    result_map: dict[str, NarrativeDirectionEntry]

    def entry_for(self, roll_result: str) -> NarrativeDirectionEntry:
        return self.result_map[roll_result]


@dataclass
class FateLikelihoodRules:
    disposition_scores: dict[str, int]
    chaos_thresholds: dict[str, int]
    chaos_scores: dict[str, int]
    resource_critical_below: int
    resource_scores: dict[str, int]
    score_to_odds: list[dict[str, Any]]


@dataclass
class FateConfig:
    default_method: str
    odds_modifiers: dict[str, int]
    chaos_modifiers: dict[int, int]
    likelihood_rules: FateLikelihoodRules


@dataclass
class StoryConfig:
    kishotenketsu_probability: dict[str, float]
    kishotenketsu_fallback_probability: float


@dataclass
class EnumsConfig:
    time_phases: list[str]
    dispositions: list[str]
    clock_types: list[str]
    tone_keys: list[str]
    correction_ops: list[str]
    correction_fields: list[str]
    dramatic_weights: list[str]
    odds_levels: list[str]


@dataclass
class MemoryRetrievalWeights:
    recency: float
    importance: float
    relevance: float


@dataclass
class FuzzyMatchConfig:
    min_word_length: int
    exact_dedup_threshold: float
    description_match_min_length: int
    description_word_min_length: int
    npc_name_min_length: int


@dataclass
class NpcMatchingConfig:
    stt_alias_bonus: int


@dataclass
class ActProgressConfig:
    filler_max: int


@dataclass
class RateLimitConfig:
    window_seconds: float
    max_requests: int
    warn_probe_max_tries: int
    warn_probe_poll_seconds: float


@dataclass
class RetryConfig:
    constraint_check_max_retries: int
    retryable_http_codes: list[int]
    backoff_base: int


@dataclass
class TfIdfConfig:
    token_min_length: int
    memory_window: int
    session_window: int
    score_floor: float
    memory_score_cap: float
    memory_score_multiplier: float
    recency_window: int
    recency_offset: int


@dataclass
class MemoryConfig:
    min_token_length: int
    consolidation_floor: int
    unknown_emotion_importance: int
    overlap_scale: int


@dataclass
class ChaosResolverConfig:
    high_threshold: int
    low_threshold: int
    recent_session_window: int
    recent_result_window: int
    clock_pressure_threshold: float
    clock_pressure_cap_multiplier: int


@dataclass
class DescriptionDedupConfig:
    identity_score_delta: int
    bond_multiplier: int
    richness_aim: int
    richness_memory: int
    richness_other: int
    max_alias_word_count: int
    min_desc_chars: int
    min_word_chars_for_match: int
    min_new_word_count: int
    min_substring_match_len: int
    long_word_chars: int
    partial_match_weight: float
    effective_overlap_min: float
    min_overlap_ratio: float


@dataclass
class ParserConfig:
    max_label_length: int
    min_line_length: int


@dataclass
class StoryStateConfig:
    intensity_smoothing_current: float
    intensity_smoothing_previous: float
    crisis_scene_offset: int


@dataclass
class ChapterConfig:
    filler_max: int
    filler_bond_max: int
    open_threads_max: int
    scene_context_threads_max: int


@dataclass
class SetupCommonConfig:
    part_name_min_length: int


@dataclass
class MetadataVotingConfig:
    min_cross_votes: int
    min_total_votes: int


@dataclass
class NamingConfig:
    callsign_probability: float


@dataclass
class RandomEventsConfig:
    threat_target_probability: float
    description_focus_categories: list[str]
    npc_focus_categories: list[str]
    thread_focus_categories: list[str]
    threat_eligible_focus_categories: list[str]
    list_weight_max: int
    consolidation_threshold: int
    consolidation_weight_high: int
    consolidation_weight_low: int
    consolidation_weight_default: int


@dataclass
class StatusDescriptionsConfig:
    health: dict[int, str]
    spirit: dict[int, str]
    supply: dict[int, str]
    bond: dict[int, str]
    clock: dict[str, str]
    track: dict[int, str]
    legacy: dict[int, str]
    xp: dict[int, str]
    combat_position: dict[str, str]
    menace: dict[int, str]


@dataclass
class AiTextConfig:
    schema_titles: dict[str, str]
    brain_trigger_hints: dict[str, str]
    schema_descriptions: dict[str, dict[str, str]]
    consequence_labels: dict[str, str]
    narrator_defaults: dict[str, Any]


@dataclass
class ArchitectLimitsConfig:
    recap_log_window: int
    recap_narration_window: int
    recap_narration_truncate: int
    recap_campaign_history_window: int
    recap_campaign_summary_truncate: int
    architect_campaign_window: int
    chapter_summary_log_window: int


@dataclass
class TruncationsConfig:
    log_xshort: int
    log_short: int
    log_medium: int
    log_long: int
    log_xlong: int
    prompt_xshort: int
    prompt_short: int
    prompt_medium: int
    prompt_long: int
    prompt_xlong: int
    prompt_xxlong: int
    narration_preview: int


@dataclass
class PersistenceConfig:
    default_save_name: str


@dataclass
class InheritanceConfig:
    move_name: str
    strong_hit_fraction: float
    weak_hit_fraction: float
    miss_fraction: float


@dataclass
class NpcCarryoverEntry:
    keep: bool
    track_fraction: float


@dataclass
class SuccessionConfig:
    inheritance: InheritanceConfig
    npc_carryover: dict[str, NpcCarryoverEntry]


@dataclass
class KeyedScenesConfig:
    triggers: frozenset[str]
    prompt_wrapper: str


@dataclass
class PlotPointRanges:
    conclusion_min: int
    conclusion_max: int
    none_min: int
    none_max: int
    meta_min: int
    meta_max: int


@dataclass
class AdventureCrafterConfig:
    themes: list[str]
    theme_slots: int
    theme_die_table: dict[int, str]
    special_ranges: PlotPointRanges
