#!/usr/bin/env python3
"""Typed engine configuration dataclasses.

Replaces _ConfigNode dot-access wrapper for engine.yaml with validated,
type-safe dataclasses. Flexible sections (stance_matrix, move_outcomes,
consequence_templates, etc.) stay as plain dicts.

Strict contract: every domain field is required. Missing yaml keys raise
KeyError — no hidden Python defaults for domain config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class CreationConfig:
    """Character creation rules."""

    max_paths: int
    max_starting_assets: int
    starting_asset_categories: list[str]
    background_vow_default_rank: str
    brain_track_rank_fallback: str
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

    max_retries: int
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
    """Rule validator NPC-monologue thresholds."""

    min_quote_count: int
    max_gap_chars: int
    max_consecutive_short_gaps: int


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
class EngineSettings:
    """Complete typed engine configuration.

    Every domain field is required — missing yaml keys raise KeyError.
    Flexible sections (stance_matrix, move_outcomes, etc.) are plain dicts
    accessed via get_raw() which is also strict.
    """

    npc: NpcConfig
    chaos: ChaosConfig
    pacing: PacingConfig
    stats: StatsConfig
    creation: CreationConfig
    resources: ResourcesConfig
    momentum: MomentumConfig
    bonds: BondsConfig
    activation_scores: ActivationScores
    location: LocationConfig
    prompt_display: PromptDisplayConfig
    opening: OpeningConfig
    architect: ArchitectConfig
    threats: ThreatConfig
    impacts: dict[str, ImpactConfig]
    legacy: LegacyConfig
    progress: ProgressConfig
    engine_moves: dict[str, EngineMove]
    stopwords: StopwordsConfig
    name_titles: frozenset[str]
    position_resolver: PositionResolverConfig
    effect_resolver: EffectResolverConfig
    information_gate: InformationGateConfig
    narrative_direction: NarrativeDirectionConfig
    fate: FateConfig
    story: StoryConfig
    enums: EnumsConfig
    memory_retrieval_weights: MemoryRetrievalWeights
    recovery: RecoveryConfig
    fuzzy_match: FuzzyMatchConfig
    npc_matching: NpcMatchingConfig
    monologue_detection: MonologueDetectionConfig
    act_progress: ActProgressConfig
    rate_limit: RateLimitConfig
    retry: RetryConfig
    tf_idf: TfIdfConfig
    memory: MemoryConfig
    chaos_resolver: ChaosResolverConfig
    description_dedup: DescriptionDedupConfig
    rule_validator: RuleValidatorConfig
    parser: ParserConfig
    story_state: StoryStateConfig
    chapter: ChapterConfig
    setup_common: SetupCommonConfig
    metadata_voting: MetadataVotingConfig
    naming: NamingConfig
    random_events: RandomEventsConfig

    # Scalar top-level fields
    scene_range_default: list[int]
    death_emotions: list[str]
    creativity_seeds: list[str]

    # Flexible sections — accessed via get_raw() as plain dicts.
    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    # Lazy cache for compiled regex pattern lists. Lives with the settings
    # instance: reload_engine() builds a fresh instance, so the cache resets
    # automatically. No manual invalidation needed.
    _compiled_patterns: dict[str, Any] = field(default_factory=dict, repr=False)

    def get_raw(self, key: str) -> Any:
        """Access a flexible top-level yaml section (stance_matrix, move_outcomes, etc.).

        Strict: raises KeyError if the key is missing. No fallback for domain data.
        """
        return self._raw[key]

    def compiled_patterns(self, section: str, key: str) -> list[Any]:
        """Compile and cache a regex pattern list from `_raw[section][key]`.

        Patterns are compiled once per EngineSettings instance with re.IGNORECASE.
        Raises KeyError if the section or key is missing — no silent fallback.
        """
        import re

        cache_key = f"patterns:{section}.{key}"
        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]
        raw_patterns = self._raw[section][key]
        compiled = [re.compile(p, re.IGNORECASE) for p in raw_patterns]
        self._compiled_patterns[cache_key] = compiled
        return compiled

    def compiled_labeled_patterns(self, section: str, key: str) -> list[tuple[Any, str]]:
        """Compile and cache a list of {pattern, label, flags?} dicts.

        Each entry produces (compiled_regex, label). Supported flags: 'multiline'.
        Raises KeyError if section or key is missing.
        """
        import re

        cache_key = f"labeled:{section}.{key}"
        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]
        entries = self._raw[section][key]
        flag_map = {"multiline": re.MULTILINE}
        compiled: list[tuple[Any, str]] = []
        for entry in entries:
            flags = 0
            for flag_name in entry.get("flags", "").split():
                flags |= flag_map[flag_name]
            compiled.append((re.compile(entry["pattern"], flags), entry["label"]))
        self._compiled_patterns[cache_key] = compiled
        return compiled

    def compiled_pattern(self, section: str, key: str, subkey: str) -> Any:
        """Compile and cache a single regex from `_raw[section][key][subkey]`.

        Raises KeyError if the path is missing.
        """
        import re

        cache_key = f"single:{section}.{key}.{subkey}"
        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]
        raw = self._raw[section][key][subkey]
        compiled = re.compile(raw)
        self._compiled_patterns[cache_key] = compiled
        return compiled


def _build_strict(cls: type, data: dict[str, Any]) -> Any:
    """Build a dataclass from a dict. Raises KeyError on missing required fields
    and ValueError on unknown keys."""
    import dataclasses

    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data.keys()) - known
    if unknown:
        raise ValueError(f"Unknown keys for {cls.__name__}: {sorted(unknown)}")
    return cls(**data)


# Sections that map directly: YAML key → dataclass type.
_SIMPLE_SECTIONS: dict[str, type] = {
    "chaos": ChaosConfig,
    "pacing": PacingConfig,
    "creation": CreationConfig,
    "resources": ResourcesConfig,
    "bonds": BondsConfig,
    "activation_scores": ActivationScores,
    "location": LocationConfig,
    "prompt_display": PromptDisplayConfig,
    "opening": OpeningConfig,
    "architect": ArchitectConfig,
    "threats": ThreatConfig,
    "story": StoryConfig,
    "enums": EnumsConfig,
    "memory_retrieval_weights": MemoryRetrievalWeights,
    "fuzzy_match": FuzzyMatchConfig,
    "npc_matching": NpcMatchingConfig,
    "monologue_detection": MonologueDetectionConfig,
    "act_progress": ActProgressConfig,
    "rate_limit": RateLimitConfig,
    "retry": RetryConfig,
    "tf_idf": TfIdfConfig,
    "memory": MemoryConfig,
    "chaos_resolver": ChaosResolverConfig,
    "description_dedup": DescriptionDedupConfig,
    "rule_validator": RuleValidatorConfig,
    "parser": ParserConfig,
    "story_state": StoryStateConfig,
    "chapter": ChapterConfig,
    "setup_common": SetupCommonConfig,
    "metadata_voting": MetadataVotingConfig,
    "naming": NamingConfig,
    "random_events": RandomEventsConfig,
}


def parse_engine_yaml(data: dict[str, Any]) -> EngineSettings:
    """Parse raw engine.yaml dict into typed EngineSettings.

    Strict: missing required yaml keys raise KeyError, unknown keys raise ValueError.
    Pre-processing only happens for sections whose yaml shape differs from the
    dataclass shape (nested dataclasses, int coercion for int-keyed dicts, etc.).
    """
    # Auto-parse simple sections (all required)
    simple_parsed: dict[str, Any] = {key: _build_strict(cls, data[key]) for key, cls in _SIMPLE_SECTIONS.items()}

    # npc: gate_memory_counts has int keys — coerce defensively
    npc_data = dict(data["npc"])
    npc_data["gate_memory_counts"] = {int(k): v for k, v in npc_data["gate_memory_counts"].items()}
    npc = _build_strict(NpcConfig, npc_data)

    # stats: valid_arrays may come as tuples from yaml
    stats_data = dict(data["stats"])
    stats_data["valid_arrays"] = [list(a) for a in stats_data["valid_arrays"]]
    stats = _build_strict(StatsConfig, stats_data)

    # momentum: nested MomentumGain
    m_data = dict(data["momentum"])
    gain = _build_strict(MomentumGain, dict(m_data.pop("gain")))
    loss = dict(m_data.pop("loss"))
    momentum = MomentumConfig(**m_data, gain=gain, loss=loss)

    # fate: nested FateLikelihoodRules, plus modifier tables with int-keyed chaos
    f_data = dict(data["fate"])
    lr = _build_strict(FateLikelihoodRules, dict(f_data.pop("likelihood_rules")))
    odds_modifiers = dict(f_data["odds_modifiers"])
    chaos_modifiers = {int(k): int(v) for k, v in f_data["chaos_modifiers"].items()}
    fate = FateConfig(
        default_method=f_data["default_method"],
        odds_modifiers=odds_modifiers,
        chaos_modifiers=chaos_modifiers,
        likelihood_rules=lr,
    )

    # recovery: nested dict for strong_hit
    r_data = dict(data["recovery"])
    recovery = RecoveryConfig(weak_hit=r_data["weak_hit"], strong_hit=dict(r_data["strong_hit"]))

    # impacts: keyed dict of ImpactConfig, key injected from outer key
    impacts = {
        key: _build_strict(ImpactConfig, {**impact_data, "key": key}) for key, impact_data in data["impacts"].items()
    }

    # legacy: ticks_by_rank sub-map
    legacy_data = dict(data["legacy"])
    legacy_data["ticks_by_rank"] = dict(legacy_data["ticks_by_rank"])
    legacy = _build_strict(LegacyConfig, legacy_data)

    # progress: track_types keyed by variant, each holding ticks_per_mark
    progress_raw = data["progress"]
    track_types = {
        name: _build_strict(ProgressTrackType, {"ticks_per_mark": dict(tt["ticks_per_mark"])})
        for name, tt in progress_raw["track_types"].items()
    }
    progress = ProgressConfig(track_types=track_types)

    # engine_moves: keyed by move id, each with name/stats/roll_type
    engine_moves = {
        key: _build_strict(EngineMove, {"name": m["name"], "stats": list(m["stats"]), "roll_type": m["roll_type"]})
        for key, m in data["engine_moves"].items()
    }

    # stopwords: three named frozensets
    sw_raw = data["stopwords"]
    stopwords = StopwordsConfig(
        general=frozenset(sw_raw["general"]),
        consequence=frozenset(sw_raw["consequence"]),
        location=frozenset(sw_raw["location"]),
    )

    # name_titles: single frozenset of honorifics stripped during fuzzy NPC matching
    name_titles = frozenset(data["name_titles"])

    # position_resolver: nested weights + overrides
    pr = dict(data["position_resolver"])
    pr_weights = _build_strict(PositionResolverWeights, dict(pr.pop("weights")))
    pr_overrides = [_build_strict(PositionOverride, dict(o)) for o in pr.pop("overrides")]
    position_resolver = PositionResolverConfig(
        desperate_below=pr["desperate_below"],
        controlled_above=pr["controlled_above"],
        weights=pr_weights,
        move_baselines=dict(pr["move_baselines"]),
        overrides=pr_overrides,
    )

    # effect_resolver: nested weights
    er = dict(data["effect_resolver"])
    er_weights = _build_strict(EffectResolverWeights, dict(er.pop("weights")))
    effect_resolver = EffectResolverConfig(
        limited_below=er["limited_below"],
        great_above=er["great_above"],
        weights=er_weights,
        move_baselines=dict(er["move_baselines"]),
    )

    # information_gate: nested points
    ig = dict(data["information_gate"])
    ig_points = _build_strict(InformationGatePoints, dict(ig.pop("points")))
    information_gate = InformationGateConfig(
        points=ig_points,
        stance_caps=dict(ig["stance_caps"]),
        default_cap=ig["default_cap"],
    )

    # narrative_direction: nested intensity + result_map of NarrativeDirectionEntry
    nd = dict(data["narrative_direction"])
    nd_intensity = _build_strict(NarrativeIntensityThresholds, dict(nd.pop("intensity")))
    nd_result_map = {
        key: _build_strict(NarrativeDirectionEntry, dict(entry)) for key, entry in nd["result_map"].items()
    }
    narrative_direction = NarrativeDirectionConfig(intensity=nd_intensity, result_map=nd_result_map)

    return EngineSettings(
        npc=npc,
        chaos=simple_parsed["chaos"],
        pacing=simple_parsed["pacing"],
        stats=stats,
        creation=simple_parsed["creation"],
        resources=simple_parsed["resources"],
        momentum=momentum,
        bonds=simple_parsed["bonds"],
        activation_scores=simple_parsed["activation_scores"],
        location=simple_parsed["location"],
        prompt_display=simple_parsed["prompt_display"],
        opening=simple_parsed["opening"],
        architect=simple_parsed["architect"],
        threats=simple_parsed["threats"],
        impacts=impacts,
        legacy=legacy,
        progress=progress,
        engine_moves=engine_moves,
        stopwords=stopwords,
        name_titles=name_titles,
        position_resolver=position_resolver,
        effect_resolver=effect_resolver,
        information_gate=information_gate,
        narrative_direction=narrative_direction,
        fate=fate,
        story=simple_parsed["story"],
        enums=simple_parsed["enums"],
        memory_retrieval_weights=simple_parsed["memory_retrieval_weights"],
        recovery=recovery,
        fuzzy_match=simple_parsed["fuzzy_match"],
        npc_matching=simple_parsed["npc_matching"],
        monologue_detection=simple_parsed["monologue_detection"],
        act_progress=simple_parsed["act_progress"],
        rate_limit=simple_parsed["rate_limit"],
        retry=simple_parsed["retry"],
        tf_idf=simple_parsed["tf_idf"],
        memory=simple_parsed["memory"],
        chaos_resolver=simple_parsed["chaos_resolver"],
        description_dedup=simple_parsed["description_dedup"],
        rule_validator=simple_parsed["rule_validator"],
        parser=simple_parsed["parser"],
        story_state=simple_parsed["story_state"],
        chapter=simple_parsed["chapter"],
        setup_common=simple_parsed["setup_common"],
        metadata_voting=simple_parsed["metadata_voting"],
        naming=simple_parsed["naming"],
        random_events=simple_parsed["random_events"],
        scene_range_default=list(data["scene_range_default"]),
        death_emotions=list(data["death_emotions"]),
        creativity_seeds=list(data["creativity_seeds"]),
        _raw=data,
    )
