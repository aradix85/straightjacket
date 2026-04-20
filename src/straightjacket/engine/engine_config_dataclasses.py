"""Subsystem dataclasses that bind engine.yaml sections to typed Python.

Each class maps to one top-level key in engine.yaml. Fields are required;
no defaults, no Optional — missing yaml keys raise at parse time.

EngineSettings composes these into the single entry point; the parse
logic lives in engine_config.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NpcConfig:
    """NPC system limits and thresholds."""

    max_active: int
    max_memory_entries: int
    max_observations: int
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


@dataclass
class ChaosConfig:
    """Chaos factor bounds."""

    min: int
    max: int
    start: int
    interrupt_types: list[str]


@dataclass
class PacingConfig:
    """Pacing thresholds and limits."""

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
    """Character stat rules."""

    target_sum: int
    min: int
    max: int
    names: list[str]
    valid_arrays: list[list[int]]
    prompt_abbreviations: dict[str, str]


@dataclass
class CreationConfig:
    """Character creation rules."""

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
    """Resource track caps and starting values."""

    health_max: int
    spirit_max: int
    supply_max: int
    health_start: int
    spirit_start: int
    supply_start: int


@dataclass
class MomentumGain:
    """Momentum gain values per result."""

    weak_hit: int
    strong_hit: dict[str, int]


@dataclass
class MomentumConfig:
    """Momentum bounds and gain/loss tables."""

    floor: int
    max: int
    start: int
    gain: MomentumGain
    loss: dict[str, int]


@dataclass
class BondsConfig:
    """NPC bond defaults."""

    max: int
    start: int


@dataclass
class ActivationScores:
    """TF-IDF activation scoring weights."""

    target: float
    name_match: float
    name_part: float
    alias_match: float
    location_match: float
    recent_interaction: float
    max_recursive: int


@dataclass
class LocationConfig:
    """Location tracking."""

    history_size: int
    prompt_history_size: int


@dataclass
class PromptDisplayConfig:
    """Text truncation caps for narrator/Brain prompt assembly."""

    insight_chars: int
    recent_event_chars: int
    lore_description_chars: int
    lore_max_aliases: int
    epilogue_log_scenes: int
    recent_events_window: int
    campaign_history_chapters: int


@dataclass
class OpeningConfig:
    """Opening scene defaults."""

    time_of_day: str
    clock_segments: int
    clock_filled: int
    clock_trigger_template: str


@dataclass
class ArchitectConfig:
    """Story architect constraints."""

    forbidden_moods: list[str]


@dataclass
class ThreatConfig:
    """Threat menace system."""

    menace_on_miss: int
    autonomous_tick_chance: float
    menace_high_threshold: float
    forsake_spirit_cost: int


@dataclass
class ImpactConfig:
    """Single impact definition from engine.yaml `impacts` section."""

    key: str
    label: str
    description: str
    blocks_recovery: str  # health / spirit / supply / "" (empty = no block)
    permanent: bool


@dataclass
class LegacyConfig:
    """Legacy tracks and XP mechanics."""

    xp_per_box: int
    starting_rank: str
    threat_overcome_bonus: int
    threat_overcome_threshold: float
    asset_upgrade_cost: int
    new_asset_cost: int
    ticks_by_rank: dict[str, int]


@dataclass
class ProgressTrackType:
    """One track variant's tick-per-mark table, keyed by rank."""

    ticks_per_mark: dict[str, int]


@dataclass
class ProgressConfig:
    """Progress-track mechanics. Extensible per track_type."""

    max_ticks: int  # 10 boxes × 4 ticks per box — Ironsworn convention
    track_types: dict[str, ProgressTrackType]

    def ticks_per_mark(self, rank: str, track_type: str = "default") -> int:
        """Look up ticks per mark for a rank. Strict on both keys."""
        return self.track_types[track_type].ticks_per_mark[rank]


@dataclass
class EngineMove:
    """Engine-defined move (dialog, ask_the_oracle, world_shaping).

    Single source of truth for engine-specific moves. Datasworn-defined moves
    live in the setting yamls; these live in engine.yaml.
    """

    name: str
    stats: list[str]
    roll_type: str


@dataclass
class FlagCondition:
    """Named boolean flag must be true for the move to be available."""

    flag: str


@dataclass
class NotFlagCondition:
    """Named boolean flag must be false for the move to be available."""

    not_flag: str


@dataclass
class CombatPosCondition:
    """combat_position must be one of the listed values for the move to be available."""

    combat_pos_in: list[str]


MoveAvailabilityCondition = FlagCondition | NotFlagCondition | CombatPosCondition


@dataclass
class MoveAvailabilityRule:
    """Availability rule for one move key.

    `never` is the reactive case: suffer and threshold moves are never
    offered to the Brain. Otherwise `available` is a list of conditions — all
    must hold. Empty list means always available.
    """

    never: bool
    available: list[MoveAvailabilityCondition]


@dataclass
class StopwordsConfig:
    """Stopword lists filtered during keyword matching and fuzzy comparison.

    Named sub-lists, each a frozenset for O(1) membership. Consumed by
    npc/lifecycle.py (general), ai/rule_validator.py (consequence), and
    mechanics/world.py (location).
    """

    general: frozenset[str]
    consequence: frozenset[str]
    location: frozenset[str]


@dataclass
class PositionResolverWeights:
    """Weights applied to resource/npc/chaos/momentum/threat factors."""

    resource_critical_below: int
    resource_low_below: int
    resource_critical: int
    resource_low: int
    npc_hostile: int
    npc_distrustful: int
    npc_friendly: int
    npc_loyal: int
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
    """Situational override: evaluated after sum, caps/floors/shifts result."""

    name: str
    conditions: list[str]
    effect: str  # cap_at_risky / floor_at_risky / shift_up_one / etc.


@dataclass
class PositionResolverConfig:
    """Weighted scoring config for resolving action position."""

    desperate_below: int
    controlled_above: int
    weights: PositionResolverWeights
    move_baselines: dict[str, int]
    overrides: list[PositionOverride]


@dataclass
class EffectResolverWeights:
    """Weights applied to position correlation + bond + secured advantage."""

    desperate: int
    controlled: int
    bond_high: int
    bond_low: int
    secured_advantage: int


@dataclass
class EffectResolverConfig:
    """Weighted scoring config for resolving action effect."""

    limited_below: int
    great_above: int
    weights: EffectResolverWeights
    move_baselines: dict[str, int]


@dataclass
class InformationGatePoints:
    """Points awarded per factor for computing information gate level."""

    scenes_known_1: int
    scenes_known_2_3: int
    scenes_known_4_plus: int
    gather_success: int
    bond_1: int
    bond_2_3: int
    bond_4_plus: int


@dataclass
class InformationGateConfig:
    """Information gate: how much NPCs reveal based on scenes/bond/stance."""

    points: InformationGatePoints
    stance_caps: dict[str, int]
    default_cap: int


@dataclass
class NarrativeIntensityThresholds:
    """Resource thresholds for narrative intensity classification."""

    critical_below: int
    high_below: int
    moderate_below: int


@dataclass
class NarrativeDirectionEntry:
    """Tempo + perspective for a single roll result."""

    tempo: str
    perspective: str


@dataclass
class NarrativeDirectionConfig:
    """Narrative writing directions derived from game state."""

    intensity: NarrativeIntensityThresholds
    result_map: dict[str, NarrativeDirectionEntry]

    def entry_for(self, roll_result: str) -> NarrativeDirectionEntry:
        """Get the entry for a roll result. Raises KeyError if missing."""
        return self.result_map[roll_result]


@dataclass
class FateLikelihoodRules:
    """Fate system likelihood resolution rules."""

    disposition_scores: dict[str, int]
    chaos_thresholds: dict[str, int]
    chaos_scores: dict[str, int]
    resource_critical_below: int
    resource_scores: dict[str, int]
    score_to_odds: list[dict[str, Any]]


@dataclass
class FateConfig:
    """Fate system (Mythic GME 2e) config."""

    default_method: str
    odds_modifiers: dict[str, int]
    chaos_modifiers: dict[int, int]
    likelihood_rules: FateLikelihoodRules


@dataclass
class StoryConfig:
    """Story structure config."""

    kishotenketsu_probability: dict[str, float]
    kishotenketsu_fallback_probability: float


@dataclass
class EnumsConfig:
    """Enum value lists used by schemas."""

    time_phases: list[str]
    npc_statuses: list[str]
    dispositions: list[str]
    memory_types: list[str]
    clock_types: list[str]
    thread_types: list[str]
    story_structures: list[str]
    positions: list[str]
    tone_keys: list[str]
    correction_ops: list[str]
    correction_fields: list[str]
    dramatic_weights: list[str]
    odds_levels: list[str]


@dataclass
class MemoryRetrievalWeights:
    """Memory scoring weights."""

    recency: float
    importance: float
    relevance: float


@dataclass
class RecoveryConfig:
    """Recovery move healing amounts."""

    weak_hit: int
    strong_hit: dict[str, int]


@dataclass
class FuzzyMatchConfig:
    """Thresholds for fuzzy string matching (NPC names, aliases)."""

    min_word_length: int
    min_phrase_length: int
    exact_dedup_threshold: float


@dataclass
class NpcMatchingConfig:
    """NPC matching thresholds and bonuses."""

    stt_alias_bonus: int
    stt_phrase_length: int
    alias_min_length: int


@dataclass
class MonologueDetectionConfig:
    """Thresholds for detecting split monologues in parser."""

    min_word_count: int


@dataclass
class ActProgressConfig:
    """Act transition and chapter-summary parameters."""

    filler_max: int
    recap_scene_max: int


@dataclass
class RateLimitConfig:
    """Web server rate limiting."""

    window_seconds: float
    max_requests: int
    warn_probe_max_tries: int
    warn_probe_poll_seconds: float


@dataclass
class RetryConfig:
    """Provider retry policy."""

    constraint_check_max_retries: int
    retryable_http_codes: list[int]
    backoff_base: int


@dataclass
class TfIdfConfig:
    """TF-IDF NPC activation parameters."""

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
    """NPC memory configuration beyond retrieval weights."""

    min_token_length: int
    consolidation_floor: int
    unknown_emotion_importance: int


@dataclass
class ChaosResolverConfig:
    """Chaos factor resolver thresholds."""

    high_threshold: int
    low_threshold: int
    recent_session_window: int
    recent_result_window: int
    clock_pressure_threshold: float
    clock_pressure_cap_multiplier: int


@dataclass
class DescriptionDedupConfig:
    """NPC description deduplication thresholds (lifecycle)."""

    identity_score_delta: int
    bond_multiplier: int
    richness_alias: int
    richness_description: int
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
class RuleValidatorConfig:
    """Rule validator NPC-monologue thresholds and violation-message templates."""

    min_quote_count: int
    max_gap_chars: int
    max_consecutive_short_gaps: int
    violation_dedup_key_length: int
    consequence_sentence_preview: int
    violation_templates: dict[str, str]


@dataclass
class ParserConfig:
    """Parser thresholds for monologue splitting and stripping."""

    max_label_length: int
    min_line_length: int


@dataclass
class StoryStateConfig:
    """Story state intensity and scene offset tuning."""

    intensity_smoothing_current: float
    intensity_smoothing_previous: float
    crisis_scene_offset: int


@dataclass
class ChapterConfig:
    """Chapter transition thresholds."""

    filler_max: int
    open_threads_max: int


@dataclass
class SetupCommonConfig:
    """Shared opening setup thresholds."""

    part_name_min_length: int


@dataclass
class MetadataVotingConfig:
    """Metadata cross-vote thresholds."""

    min_cross_votes: int
    min_total_votes: int


@dataclass
class NamingConfig:
    """NPC naming configuration."""

    callsign_probability: float


@dataclass
class RandomEventsConfig:
    """Random-event pipeline tuning (Mythic GME 2e)."""

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
    """Narrative status descriptors keyed by threshold or state.

    Numeric thresholds (health/spirit/supply/bond/track/legacy/xp/menace) map
    filled-box counts to prose. Clock state and combat_position are keyed by
    string enum.
    """

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
    """All hardcoded English strings that flow into AI prompts, json_schema
    descriptions, narrator-facing consequence labels, and validator correction
    instructions. Strict: every leaf dict is a fixed-shape mapping; missing
    expected keys raise KeyError at the callsite.
    """

    brain_trigger_hints: dict[str, str]
    schema_descriptions: dict[str, dict[str, str]]
    consequence_labels: dict[str, str]
    validator_blocks: dict[str, str]
    narrator_defaults: dict[str, Any]
    architect_labels: dict[str, str]


@dataclass
class ArchitectLimitsConfig:
    """History windows used by architect.py and recap."""

    recap_log_window: int
    recap_narration_window: int
    recap_narration_truncate: int
    recap_campaign_history_window: int
    recap_campaign_summary_truncate: int
    architect_campaign_window: int
    chapter_summary_log_window: int
    drift_words_log_window: int


@dataclass
class TruncationsConfig:
    """Named string-truncation limits used in logs and prompts.

    Centralised so every `[:N]` slice in the codebase reads from a named key
    instead of a magic number. log_* sizes are for log lines (short one-line
    summaries), prompt_* sizes for substrings fed to AI prompts.
    """

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
    narration_max: int
