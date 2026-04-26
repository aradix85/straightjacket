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
    """Chaos factor bounds and per-outcome adjustments."""

    min: int
    max: int
    start: int
    adjust_miss: int
    adjust_strong: int
    adjust_dialog_hostile: int
    adjust_dialog_friendly: int


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
class SufferRecoveryGain:
    """Momentum awarded by suffer-move handlers.

    strong_hit_gain: momentum gained on strong hit when track recovery is
        unavailable (track at max, blocking impact, or non-standard track).
    weak_hit_exchange_cost: momentum spent on weak hit to exchange for
        +recovery on the affected track.
    """

    strong_hit_gain: int
    weak_hit_exchange_cost: int


@dataclass
class MomentumConfig:
    """Momentum bounds and suffer-recovery gain table."""

    floor: int
    max: int
    start: int
    suffer_recovery: SufferRecoveryGain


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
    memory_consequences_max: int
    memory_npcs_max: int


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
    autonomous_tick_marks: int
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
    npc_bond_high_min: int
    npc_bond_low_max: int
    disposition_weights: dict[str, int]
    weights: PositionResolverWeights
    move_baselines: dict[str, int]
    overrides: list[PositionOverride]


@dataclass
class EffectResolverWeights:
    """Weights applied to bond + secured advantage."""

    bond_high: int
    bond_low: int
    secured_advantage: int


@dataclass
class EffectResolverConfig:
    """Weighted scoring config for resolving action effect."""

    limited_below: int
    great_above: int
    bond_high_min: int
    bond_low_max: int
    position_weights: dict[str, int]
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
class InformationGateBuckets:
    """Boundaries for bucketing scenes_known and bond into low/mid/high. A
    value `>= *_mid_min` goes into mid; `>= *_high_min` goes into high; else low."""

    scenes_known_mid_min: int
    scenes_known_high_min: int
    bond_mid_min: int
    bond_high_min: int


@dataclass
class StanceBondBuckets:
    """Bond-range buckets used by resolve_npc_stance to look up entries in
    stance_matrix. Bond at or below low_max → "low"; at or below mid_max → "mid";
    else "high".
    """

    low_max: int
    mid_max: int


@dataclass
class StanceMoveBuckets:
    """Maps engine move-category (from move_categories.yaml) to the stance-matrix
    bucket key used in stance_matrix.yaml. gather_information is handled as a
    special case in code because it splits off from the generic social bucket.
    Direct subscript on `mapping`; unknown move-category raises KeyError.
    """

    mapping: dict[str, str]


@dataclass
class TimeProgressionSteps:
    """Number of time-phase steps taken per time-progression label. Callers look
    up by the label resolved from time_progression_map. Direct subscript on
    `mapping`; unknown label raises KeyError.
    """

    mapping: dict[str, int]


@dataclass
class NarratorStatusDescriptions:
    """Narrator-facing resource-level descriptions, injected into the narrator
    prompt via <character_state>. Three fixed resources; each maps an integer
    threshold to a description string.
    """

    health: dict[int, str]
    spirit: dict[int, str]
    supply: dict[int, str]


@dataclass
class ValidatorConfig:
    """Validator yaml block. The regex-pattern fields are still accessed via
    EngineSettings.compiled_patterns / compiled_pattern / compiled_labeled_patterns
    helpers (which read raw yaml and cache compiled regex). They are listed here
    so _build_strict accepts the yaml as-is. The string-template fields
    (rewrite_instructions, retry_strip) are read directly through this dataclass.
    """

    rewrite_instructions: dict[str, str]
    retry_strip: dict[str, str]
    agency_patterns: list[str]
    miss_silver_lining_patterns: list[str]
    miss_annihilation_patterns: list[str]
    format_patterns: list[dict[str, str]]
    quote_patterns: dict[str, str]


@dataclass
class CorrectionConfig:
    """Correction-flow constraints."""

    npc_edit_allowed_fields: list[str]


@dataclass
class StanceMatrixEntry:
    """One leaf in stance_matrix: the (stance, constraint) pair for a given
    disposition × bond-range × move-category combination.
    """

    stance: str
    constraint: str


@dataclass
class MemoryEmotions:
    """Emotion derivation for engine-generated memories. `base` maps move-category
    × roll-result pairs to base emotion keys; `disposition_suffix` adds an NPC-
    disposition-specific suffix when the memory has an associated NPC.
    """

    base: dict[str, str]
    disposition_suffix: dict[str, str]


@dataclass
class MemoryTemplates:
    """Format templates for engine-generated memory text. Four fixed shapes
    cover targeted/untargeted action and dialog turns.
    """

    action: str
    action_targeted: str
    dialog: str
    dialog_no_target: str


@dataclass
class SceneContextTemplates:
    """Format templates for scene-context lines included in narrator prompts.
    Two fixed templates: one for action turns, one for dialog turns.
    """

    template: str
    dialog: str


@dataclass
class SceneAdjustments:
    """AI-facing descriptions for Mythic 2e altered-scene adjustments, injected
    into narrator prompts via <altered_scene> tags. Direct subscript on
    `mapping`; unknown adjustment raises KeyError.
    """

    mapping: dict[str, str]


@dataclass
class InformationGateConfig:
    """Information gate: how much NPCs reveal based on scenes/bond/stance."""

    points: InformationGatePoints
    buckets: InformationGateBuckets
    gate_min: int
    gate_max: int
    stance_caps: dict[str, int]


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
    dispositions: list[str]
    clock_types: list[str]
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
class FuzzyMatchConfig:
    """Thresholds for fuzzy string matching (NPC names, aliases)."""

    min_word_length: int
    exact_dedup_threshold: float
    description_match_min_length: int
    description_word_min_length: int
    label_word_min_length: int
    npc_name_min_length: int


@dataclass
class NpcMatchingConfig:
    """NPC matching thresholds and bonuses."""

    stt_alias_bonus: int


@dataclass
class ActProgressConfig:
    """Act transition and chapter-summary parameters."""

    filler_max: int


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
    overlap_scale: int


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
    agency_violations_cap: int
    atmospheric_examples_cap: int
    correction_violations_cap: int
    threat_name_min_word_length: int
    impact_label_min_word_length: int
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
    filler_bond_max: int
    open_threads_max: int
    scene_context_threads_max: int


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

    schema_titles: dict[str, str]
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


@dataclass
class PersistenceConfig:
    """Save-game filesystem behaviour."""

    default_save_name: str


@dataclass
class ChapterValidatorConfig:
    """Chapter-summary contradiction validator.

    Hybrid check that runs over the AI-written narrative dict before it is
    fused with the engine snapshot. The rule pass scans for named entities
    (NPCs, tracks, threats) paired with status-shift keywords; the LLM pass
    catches euphemisms the keyword pass misses. Both feed the same retry
    loop: violations trigger a re-call of `call_chapter_summary` with a
    correction instruction, up to `max_retries`.
    """

    max_retries: int
    death_keywords: list[str]
    completion_keywords: list[str]
    resolution_keywords: list[str]


@dataclass
class InheritanceConfig:
    """Inheritance roll outcome fractions for character succession.

    A roll_progress against each legacy track (Quests/Bonds/Discoveries) on
    the predecessor produces STRONG_HIT / WEAK_HIT / MISS; the matching
    fraction below is applied to the predecessor's filled_boxes to seed the
    new character's track.
    """

    move_name: str
    strong_hit_fraction: float
    weak_hit_fraction: float
    miss_fraction: float


@dataclass
class NpcCarryoverEntry:
    """How a single NPC status class carries over a character succession.

    keep=False prunes the NPC entirely from the new character's roster.
    track_fraction multiplies the connection track's filled_boxes; the result
    becomes the new track's filled_boxes (converted to ticks via the track's
    ticks_per_mark).
    """

    keep: bool
    track_fraction: float


@dataclass
class SuccessionConfig:
    """Character succession (Continue a Legacy).

    Triggered when game.game_over is True or when the player issues the
    retire command. Both routes feed start_succession(). The predecessor is
    archived; a new character inherits legacy progress per the inheritance
    roll and NPCs carry over per their status.
    """

    inheritance: InheritanceConfig
    npc_carryover: dict[str, NpcCarryoverEntry]
    retire_command: str


@dataclass
class KeyedSceneTrigger:
    """Metadata for one registered keyed-scene trigger type.

    The evaluator function name is implicit: mechanics/keyed_scenes.py owns
    the dispatch table that maps trigger_type names to evaluator functions.
    This config carries only the spec a spawner or a constructor needs to
    validate trigger_value at write time.
    """

    value_format: str
    description: str


@dataclass
class KeyedScenesConfig:
    """Director-pre-defined narrative beats that override chaos at scene start.

    See engine/keyed_scenes.yaml for full prose. The triggers map drives
    KeyedScene.trigger_type validation (unknown type raises on construction)
    and the evaluator dispatch in mechanics/keyed_scenes.py. prompt_wrapper
    is the AI-facing template for the narrative_hint when a keyed scene fires.
    """

    triggers: dict[str, KeyedSceneTrigger]
    prompt_wrapper: str


@dataclass
class PlotPointRanges:
    """Special d100 ranges on Adventure Crafter plot points.

    Each plot point covers a min-max d100 range per theme. Three named ranges
    receive special handling at the engine level: Conclusion (closes the
    plotline), None (no plot point this turn), Meta (route to meta-handler).
    Bounds are inclusive on both ends.
    """

    conclusion_min: int
    conclusion_max: int
    none_min: int
    none_max: int
    meta_min: int
    meta_max: int


@dataclass
class AdventureCrafterConfig:
    """Adventure Crafter primitives: themes, theme assignment, special ranges.

    themes is the canonical ordered list of theme names; theme_slots is the
    number of priority slots assigned at adventure start (one theme per slot,
    rolled via theme_die_table). theme_die_table is the d10 -> theme mapping
    consumed by the theme assigner. special_ranges flags Conclusion / None /
    Meta on plot-point lookup. All four blocks are loaded strict; mismatches
    against data/adventure_crafter.json raise at parse time.
    """

    themes: list[str]
    theme_slots: int
    theme_die_table: dict[int, str]
    special_ranges: PlotPointRanges
