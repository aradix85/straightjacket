"""Engine configuration: the EngineSettings composition and yaml-parse logic.

The individual subsystem dataclasses live in engine_config_dataclasses.py;
they are re-exported here so consumers can keep importing from engine_config.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Any

from .engine_config_dataclasses import (
    ActProgressConfig,
    ActivationScores,
    AiTextConfig,
    ArchitectConfig,
    ArchitectLimitsConfig,
    BondsConfig,
    ChaosConfig,
    ChaosResolverConfig,
    ChapterConfig,
    ChapterValidatorConfig,
    CombatPosCondition,
    CorrectionConfig,
    CreationConfig,
    DescriptionDedupConfig,
    EffectResolverConfig,
    EffectResolverWeights,
    EngineMove,
    EnumsConfig,
    FateConfig,
    FateLikelihoodRules,
    FlagCondition,
    FuzzyMatchConfig,
    ImpactConfig,
    InformationGateConfig,
    InformationGatePoints,
    InformationGateBuckets,
    KeyedScenesConfig,
    KeyedSceneTrigger,
    LegacyConfig,
    LocationConfig,
    MemoryConfig,
    MemoryEmotions,
    MemoryRetrievalWeights,
    MemoryTemplates,
    MetadataVotingConfig,
    MomentumConfig,
    MoveAvailabilityCondition,
    MoveAvailabilityRule,
    NamingConfig,
    NarrativeDirectionConfig,
    NarrativeDirectionEntry,
    NarrativeIntensityThresholds,
    NarratorStatusDescriptions,
    NotFlagCondition,
    NpcConfig,
    NpcMatchingConfig,
    OpeningConfig,
    PacingConfig,
    ParserConfig,
    PersistenceConfig,
    PositionOverride,
    PositionResolverConfig,
    PositionResolverWeights,
    ProgressConfig,
    ProgressTrackType,
    PromptDisplayConfig,
    RandomEventsConfig,
    RateLimitConfig,
    ResourcesConfig,
    RetryConfig,
    RuleValidatorConfig,
    SceneAdjustments,
    SceneContextTemplates,
    SetupCommonConfig,
    StanceBondBuckets,
    StanceMatrixEntry,
    StanceMoveBuckets,
    StatsConfig,
    StatusDescriptionsConfig,
    StopwordsConfig,
    StoryConfig,
    StoryStateConfig,
    SufferRecoveryGain,
    SuccessionConfig,
    InheritanceConfig,
    NpcCarryoverEntry,
    TfIdfConfig,
    ThreatConfig,
    TimeProgressionSteps,
    TruncationsConfig,
    ValidatorConfig,
)


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
    move_availability: dict[str, MoveAvailabilityRule]
    stopwords: StopwordsConfig
    name_titles: frozenset[str]
    position_resolver: PositionResolverConfig
    effect_resolver: EffectResolverConfig
    information_gate: InformationGateConfig
    stance_bond_buckets: StanceBondBuckets
    stance_move_buckets: StanceMoveBuckets
    stance_matrix: dict[str, dict[str, dict[str, StanceMatrixEntry]]]
    time_progression_steps: TimeProgressionSteps
    narrator_status_descriptions: NarratorStatusDescriptions
    scene_adjustments: SceneAdjustments
    scene_context: SceneContextTemplates
    memory_emotions: MemoryEmotions
    memory_templates: MemoryTemplates
    narrative_direction: NarrativeDirectionConfig
    fate: FateConfig
    story: StoryConfig
    enums: EnumsConfig
    memory_retrieval_weights: MemoryRetrievalWeights
    fuzzy_match: FuzzyMatchConfig
    npc_matching: NpcMatchingConfig
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
    ai_text: AiTextConfig
    architect_limits: ArchitectLimitsConfig
    status_descriptions: StatusDescriptionsConfig
    truncations: TruncationsConfig
    persistence: PersistenceConfig
    validator: ValidatorConfig
    correction: CorrectionConfig
    chapter_validator: ChapterValidatorConfig
    succession: SuccessionConfig
    keyed_scenes: KeyedScenesConfig

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

        cache_key = f"patterns:{section}.{key}"
        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]
        raw_patterns = self._raw[section][key]
        compiled = [re.compile(p, re.IGNORECASE) for p in raw_patterns]
        self._compiled_patterns[cache_key] = compiled
        return compiled

    def compiled_labeled_patterns(self, section: str, key: str) -> list[tuple[Any, str]]:
        """Compile and cache a list of {pattern, label, flags} dicts.

        Each entry produces (compiled_regex, label). flags is a space-separated
        string of flag names (currently only 'multiline'); empty string means
        no flags. flags is required on every entry — the yaml author opts out
        of flags by writing `flags: ""`, not by omitting the key.
        Raises KeyError if section, key, or any per-entry field is missing.
        """

        cache_key = f"labeled:{section}.{key}"
        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]
        entries = self._raw[section][key]
        flag_map = {"multiline": re.MULTILINE}
        compiled: list[tuple[Any, str]] = []
        for entry in entries:
            flags = 0
            for flag_name in entry["flags"].split():
                flags |= flag_map[flag_name]
            compiled.append((re.compile(entry["pattern"], flags), entry["label"]))
        self._compiled_patterns[cache_key] = compiled
        return compiled

    def compiled_pattern(self, section: str, key: str, subkey: str) -> Any:
        """Compile and cache a single regex from `_raw[section][key][subkey]`.

        Raises KeyError if the path is missing.
        """

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
    "ai_text": AiTextConfig,
    "architect_limits": ArchitectLimitsConfig,
    "status_descriptions": StatusDescriptionsConfig,
    "truncations": TruncationsConfig,
    "persistence": PersistenceConfig,
    "validator": ValidatorConfig,
    "correction": CorrectionConfig,
    "chapter_validator": ChapterValidatorConfig,
}


def _parse_move_availability_condition(cond: dict[str, Any]) -> MoveAvailabilityCondition:
    """Parse a single condition dict into the matching dataclass.

    Exactly one of `flag`, `not_flag`, `combat_pos_in` must be set.
    """
    keys = set(cond.keys())
    if keys == {"flag"}:
        return FlagCondition(flag=cond["flag"])
    if keys == {"not_flag"}:
        return NotFlagCondition(not_flag=cond["not_flag"])
    if keys == {"combat_pos_in"}:
        return CombatPosCondition(combat_pos_in=list(cond["combat_pos_in"]))
    raise ValueError(
        f"Invalid move_availability condition: {cond!r}. Expected exactly one of: flag, not_flag, combat_pos_in."
    )


def _parse_move_availability_rule(rule: dict[str, Any]) -> MoveAvailabilityRule:
    """Parse a rule dict into a MoveAvailabilityRule.

    Accepts either {"never": true} or {"available": [<conditions>]}.
    """
    keys = set(rule.keys())
    if keys == {"never"}:
        if not rule["never"]:
            raise ValueError(f"move_availability rule with never=false is not allowed: {rule!r}")
        return MoveAvailabilityRule(never=True, available=[])
    if keys == {"available"}:
        conds = [_parse_move_availability_condition(dict(c)) for c in rule["available"]]
        return MoveAvailabilityRule(never=False, available=conds)
    raise ValueError(f"Invalid move_availability rule: {rule!r}. Expected exactly one of: never, available.")


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

    # momentum: nested SufferRecoveryGain
    m_data = dict(data["momentum"])
    suffer = _build_strict(SufferRecoveryGain, dict(m_data.pop("suffer_recovery")))
    momentum = MomentumConfig(**m_data, suffer_recovery=suffer)

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
    progress = ProgressConfig(max_ticks=progress_raw["max_ticks"], track_types=track_types)

    # engine_moves: keyed by move id, each with name/stats/roll_type
    engine_moves = {
        key: _build_strict(EngineMove, {"name": m["name"], "stats": list(m["stats"]), "roll_type": m["roll_type"]})
        for key, m in data["engine_moves"].items()
    }

    # move_availability: keyed by datasworn move id, each is either
    # {"never": true} or {"available": [<conditions>]}. Conditions are
    # dicts with exactly one of: flag, not_flag, combat_pos_in.
    move_availability = {key: _parse_move_availability_rule(rule) for key, rule in data["move_availability"].items()}

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
        npc_bond_high_min=pr["npc_bond_high_min"],
        npc_bond_low_max=pr["npc_bond_low_max"],
        disposition_weights=dict(pr["disposition_weights"]),
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
        bond_high_min=er["bond_high_min"],
        bond_low_max=er["bond_low_max"],
        position_weights=dict(er["position_weights"]),
        weights=er_weights,
        move_baselines=dict(er["move_baselines"]),
    )

    # information_gate: nested points + buckets
    ig = dict(data["information_gate"])
    ig_points = _build_strict(InformationGatePoints, dict(ig.pop("points")))
    ig_buckets = _build_strict(InformationGateBuckets, dict(ig.pop("buckets")))
    information_gate = InformationGateConfig(
        points=ig_points,
        buckets=ig_buckets,
        gate_min=ig["gate_min"],
        gate_max=ig["gate_max"],
        stance_caps=dict(ig["stance_caps"]),
    )

    # stance_bond_buckets and stance_move_buckets: flat dicts
    stance_bond_buckets = _build_strict(StanceBondBuckets, dict(data["stance_bond_buckets"]))
    stance_move_buckets = _build_strict(StanceMoveBuckets, dict(data["stance_move_buckets"]))
    stance_matrix: dict[str, dict[str, dict[str, StanceMatrixEntry]]] = {
        disp: {
            bond: {cat: _build_strict(StanceMatrixEntry, dict(entry)) for cat, entry in cats.items()}
            for bond, cats in bonds.items()
        }
        for disp, bonds in data["stance_matrix"].items()
    }
    time_progression_steps = _build_strict(TimeProgressionSteps, dict(data["time_progression_steps"]))
    narrator_status_descriptions = _build_strict(NarratorStatusDescriptions, dict(data["narrator_status_descriptions"]))
    scene_adjustments = _build_strict(SceneAdjustments, dict(data["scene_adjustments"]))
    scene_context = _build_strict(SceneContextTemplates, dict(data["scene_context"]))
    memory_emotions = _build_strict(MemoryEmotions, dict(data["memory_emotions"]))
    memory_templates = _build_strict(MemoryTemplates, dict(data["memory_templates"]))

    # narrative_direction: nested intensity + result_map of NarrativeDirectionEntry
    nd = dict(data["narrative_direction"])
    nd_intensity = _build_strict(NarrativeIntensityThresholds, dict(nd.pop("intensity")))
    nd_result_map = {
        key: _build_strict(NarrativeDirectionEntry, dict(entry)) for key, entry in nd["result_map"].items()
    }
    narrative_direction = NarrativeDirectionConfig(intensity=nd_intensity, result_map=nd_result_map)

    # succession: nested InheritanceConfig + dict of NpcCarryoverEntry per status
    succession_raw = dict(data["succession"])
    inheritance = _build_strict(InheritanceConfig, dict(succession_raw["inheritance"]))
    npc_carryover = {
        status: _build_strict(NpcCarryoverEntry, dict(entry))
        for status, entry in succession_raw["npc_carryover"].items()
    }
    succession = SuccessionConfig(
        inheritance=inheritance,
        npc_carryover=npc_carryover,
        retire_command=succession_raw["retire_command"],
    )

    # keyed_scenes: nested dict[str, KeyedSceneTrigger] + scalar prompt_wrapper.
    keyed_raw = dict(data["keyed_scenes"])
    triggers = {name: _build_strict(KeyedSceneTrigger, dict(entry)) for name, entry in keyed_raw["triggers"].items()}
    keyed_scenes = KeyedScenesConfig(
        triggers=triggers,
        prompt_wrapper=keyed_raw["prompt_wrapper"],
    )

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
        move_availability=move_availability,
        stopwords=stopwords,
        name_titles=name_titles,
        position_resolver=position_resolver,
        effect_resolver=effect_resolver,
        information_gate=information_gate,
        stance_bond_buckets=stance_bond_buckets,
        stance_move_buckets=stance_move_buckets,
        stance_matrix=stance_matrix,
        time_progression_steps=time_progression_steps,
        narrator_status_descriptions=narrator_status_descriptions,
        scene_adjustments=scene_adjustments,
        scene_context=scene_context,
        memory_emotions=memory_emotions,
        memory_templates=memory_templates,
        narrative_direction=narrative_direction,
        fate=fate,
        story=simple_parsed["story"],
        enums=simple_parsed["enums"],
        memory_retrieval_weights=simple_parsed["memory_retrieval_weights"],
        fuzzy_match=simple_parsed["fuzzy_match"],
        npc_matching=simple_parsed["npc_matching"],
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
        ai_text=simple_parsed["ai_text"],
        architect_limits=simple_parsed["architect_limits"],
        status_descriptions=simple_parsed["status_descriptions"],
        truncations=simple_parsed["truncations"],
        persistence=simple_parsed["persistence"],
        validator=simple_parsed["validator"],
        correction=simple_parsed["correction"],
        chapter_validator=simple_parsed["chapter_validator"],
        succession=succession,
        keyed_scenes=keyed_scenes,
        scene_range_default=list(data["scene_range_default"]),
        death_emotions=list(data["death_emotions"]),
        creativity_seeds=list(data["creativity_seeds"]),
        _raw=data,
    )
