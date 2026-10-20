from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GameMasterMove:
    name: str
    time: str


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
    reflection_observation_window: int


@dataclass
class ChaosConfig:
    min: int
    max: int
    start: int
    adjust_by_outcome: dict[str, int]
    adjust_dialog_hostile: int
    adjust_dialog_friendly: int
    dialog_raising_dispositions: list[str]
    dialog_lowering_dispositions: list[str]


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
    npc_agency_clock_types: list[str]
    intense_scene_types: list[str]
    director_phases: list[str]


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
    word_match_min_words: int
    change_time: str


@dataclass
class OutcomesConfig:
    gained: list[str]
    unrolled: list[str]


@dataclass
class OpeningConfig:
    time_of_day: str
    clock_segments: int
    clock_filled: int
    clock_trigger_template: str


@dataclass
class MythicDiceConfig:
    fate_chart_die: int
    fate_check_die: int
    scene_test_die: int
    scene_adjustment_die: int
    event_focus_die: int


@dataclass
class StopwordsConfig:
    general: frozenset[str]
    location: frozenset[str]


@dataclass
class PositionResolverWeights:
    npc_bond_high: int
    npc_bond_low: int
    chaos_high: int
    chaos_low: int
    consecutive_failures: int
    consecutive_successes: int
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
    strain_weights: dict[str, int]
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
    miss_stance: StanceMatrixEntry
    hit_stance: StanceMatrixEntry
    refusing_stances: list[str]


@dataclass
class FateLikelihoodRules:
    disposition_scores: dict[str, int]
    score_to_odds: list[dict[str, Any]]


@dataclass
class FateConfig:
    default_method: str
    likelihood_rules: FateLikelihoodRules


@dataclass
class FactTypeConfig:
    subject: str
    description: str
    base_score: int
    inputs: dict[str, int]
    cleared_by_hit: bool
    no_releases_target: bool


@dataclass
class FactResolutionConfig:
    place_reference: str
    max_per_turn: int
    types: dict[str, FactTypeConfig]
    information_miss_settles: dict[str, str]


@dataclass
class GenerationConfig:
    categories: list[str]
    place_categories: list[str]


@dataclass
class StoryConfig:
    tones: list[str]


@dataclass
class EnumsConfig:
    time_phases: list[str]
    dispositions: list[str]
    npc_statuses: list[str]
    tone_keys: list[str]
    dramatic_weights: list[str]


@dataclass
class NpcStatusGroups:
    in_play: list[str]
    reactivatable: list[str]
    description_matchable: list[str]


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
    named_in_min_word_length: int


@dataclass
class NpcMatchingConfig:
    stt_alias_bonus: int


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
    relevance_min_context_words: int
    importance_max: int
    emotion_split_pattern: str


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
class StoryStateConfig:
    act_early_share: float
    act_mid_share: float
    completion_overrun_scenes: int
    approaching_end_progress: list[str]
    revelation_outcomes: list[str]


@dataclass
class ChapterConfig:
    filler_max: int
    filler_bond_max: int
    npc_memories_kept: int
    scene_context_threads_max: int


@dataclass
class NamingConfig:
    category: str
    callsign_role: str
    callsign_probability: float


@dataclass
class RandomEventKeyedSceneMappingEntry:
    trigger_type: str
    threshold: int
    priority: int
    narrative_hint: str


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
    seeded_list_weight: int
    keyed_scene_mapping: dict[str, RandomEventKeyedSceneMappingEntry]
    danger_foci: list[str]
    clock_creation_mapping: dict[str, ClockCreationMappingEntry]


@dataclass
class PatternGrammar:
    pattern_prefixes: list[str]
    matcher_strategy: str


@dataclass
class ClockKeyedSceneEntry:
    fractions: list[float]
    priority: int
    narrative_hint_template: str


@dataclass
class ClockKeyedScenesConfig:
    by_clock_type: dict[str, ClockKeyedSceneEntry]


@dataclass
class KeyedScenesConfig:
    triggers: frozenset[str]
    prompt_wrapper: str
    pattern_grammars: dict[str, PatternGrammar]


@dataclass
class ClockCreationMappingEntry:
    clock_type: str


@dataclass
class ClockFillConsequenceEntry:
    tag_template: str


@dataclass
class ComplicationClockConfig:
    segments: int
    tick_chance: float
    max_open: int
    name_oracle_path: str


@dataclass
class ClocksConfig:
    default_owner_kind: str
    default_segments: int
    max_open_emergent: int
    miss_ticks_by_position: dict[str, int]
    fill_consequences: dict[str, ClockFillConsequenceEntry]
    complication: ComplicationClockConfig
    duplicate_name_template: str
