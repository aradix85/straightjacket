from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Any

from .engine_config_dataclasses import (
    ActProgressConfig,
    ActivationScores,
    AdventureCrafterConfig,
    AiTextConfig,
    RecapLimitsConfig,
    BlueprintConfig,
    BondsConfig,
    ChaosConfig,
    ChaosResolverConfig,
    ChapterConfig,
    ClockKeyedSceneEntry,
    ClockKeyedScenesConfig,
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
    KeyedSceneMappingEntry,
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
    PatternGrammar,
    PersistenceConfig,
    PlotPointRanges,
    MetaHandlerConfig,
    PositionOverride,
    PositionResolverConfig,
    PositionResolverWeights,
    ProgressConfig,
    ProgressTrackType,
    PromptDisplayConfig,
    RandomEventsConfig,
    RandomEventKeyedSceneMappingEntry,
    RateLimitConfig,
    ResourcesConfig,
    RetryConfig,
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
    ThreatCreationMappingEntry,
    TimeProgressionSteps,
    TruncationsConfig,
)


@dataclass
class EngineSettings:
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
    parser: ParserConfig
    story_state: StoryStateConfig
    chapter: ChapterConfig
    setup_common: SetupCommonConfig
    metadata_voting: MetadataVotingConfig
    naming: NamingConfig
    random_events: RandomEventsConfig
    ai_text: AiTextConfig
    recap_limits: RecapLimitsConfig
    status_descriptions: StatusDescriptionsConfig
    truncations: TruncationsConfig
    persistence: PersistenceConfig
    correction: CorrectionConfig
    succession: SuccessionConfig
    keyed_scenes: KeyedScenesConfig
    adventure_crafter: AdventureCrafterConfig
    clock_keyed_scenes: ClockKeyedScenesConfig

    scene_range_default: list[int]
    death_emotions: list[str]
    creativity_seeds: list[str]

    _raw: dict[str, Any] = field(default_factory=dict, repr=False)

    _compiled_patterns: dict[str, Any] = field(default_factory=dict, repr=False)

    def get_raw(self, key: str) -> Any:
        return self._raw[key]

    def compiled_patterns(self, section: str, key: str) -> list[Any]:
        cache_key = f"patterns:{section}.{key}"
        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]
        raw_patterns = self._raw[section][key]
        compiled = [re.compile(p, re.IGNORECASE) for p in raw_patterns]
        self._compiled_patterns[cache_key] = compiled
        return compiled

    def compiled_labeled_patterns(self, section: str, key: str) -> list[tuple[Any, str]]:
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
        cache_key = f"single:{section}.{key}.{subkey}"
        if cache_key in self._compiled_patterns:
            return self._compiled_patterns[cache_key]
        raw = self._raw[section][key][subkey]
        compiled = re.compile(raw)
        self._compiled_patterns[cache_key] = compiled
        return compiled


def _build_strict(cls: type, data: dict[str, Any]) -> Any:
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data.keys()) - known
    if unknown:
        raise ValueError(f"Unknown keys for {cls.__name__}: {sorted(unknown)}")
    return cls(**data)


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
    "parser": ParserConfig,
    "story_state": StoryStateConfig,
    "chapter": ChapterConfig,
    "setup_common": SetupCommonConfig,
    "metadata_voting": MetadataVotingConfig,
    "naming": NamingConfig,
    "ai_text": AiTextConfig,
    "recap_limits": RecapLimitsConfig,
    "status_descriptions": StatusDescriptionsConfig,
    "truncations": TruncationsConfig,
    "persistence": PersistenceConfig,
    "correction": CorrectionConfig,
}


def _parse_move_availability_condition(cond: dict[str, Any]) -> MoveAvailabilityCondition:
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
    keys = set(rule.keys())
    if keys == {"never"}:
        if not rule["never"]:
            raise ValueError(f"move_availability rule with never=false is not allowed: {rule!r}")
        return MoveAvailabilityRule(never=True, available=[])
    if keys == {"available"}:
        conds = [_parse_move_availability_condition(dict(c)) for c in rule["available"]]
        return MoveAvailabilityRule(never=False, available=conds)
    raise ValueError(f"Invalid move_availability rule: {rule!r}. Expected exactly one of: never, available.")


def _build_keyed_scenes(keyed_raw: dict[str, Any]) -> KeyedScenesConfig:
    pattern_grammars_raw = dict(keyed_raw["pattern_grammars"])
    pattern_grammars = {
        trigger_name: PatternGrammar(
            pattern_prefixes=list(spec["pattern_prefixes"]),
            matcher_strategy=spec["matcher_strategy"],
        )
        for trigger_name, spec in pattern_grammars_raw.items()
    }
    return KeyedScenesConfig(
        triggers=frozenset(keyed_raw["triggers"]),
        prompt_wrapper=keyed_raw["prompt_wrapper"],
        pattern_grammars=pattern_grammars,
    )


def _build_adventure_crafter(ac_raw: dict[str, Any]) -> AdventureCrafterConfig:
    ac_special = _build_strict(PlotPointRanges, dict(ac_raw["special_ranges"]))
    ac_meta_handlers = _build_strict(MetaHandlerConfig, dict(ac_raw["meta_handlers"]))
    ac_blueprint_raw = dict(ac_raw["blueprint"])
    ac_blueprint = BlueprintConfig(
        turning_points_pre_rolled=ac_blueprint_raw["turning_points_pre_rolled"],
        acts_three_act=ac_blueprint_raw["acts_three_act"],
        acts_kishotenketsu=ac_blueprint_raw["acts_kishotenketsu"],
        revelations_per_blueprint=ac_blueprint_raw["revelations_per_blueprint"],
        possible_endings_per_blueprint=ac_blueprint_raw["possible_endings_per_blueprint"],
        three_act_phases=list(ac_blueprint_raw["three_act_phases"]),
        kishotenketsu_phases=list(ac_blueprint_raw["kishotenketsu_phases"]),
    )
    ac_keyed_mapping = {
        name: KeyedSceneMappingEntry(
            trigger_type=entry["trigger_type"],
            trigger_value=entry["trigger_value"],
            priority=entry["priority"],
            narrative_hint=entry["narrative_hint"],
        )
        for name, entry in dict(ac_raw["keyed_scene_mapping"]).items()
    }
    ac_threat_creation = {
        name: ThreatCreationMappingEntry(
            rank=entry["rank"],
            category=entry["category"],
        )
        for name, entry in dict(ac_raw["threat_creation_mapping"]).items()
    }
    return AdventureCrafterConfig(
        themes=list(ac_raw["themes"]),
        theme_slots=ac_raw["theme_slots"],
        theme_die_table={int(k): v for k, v in ac_raw["theme_die_table"].items()},
        special_ranges=ac_special,
        meta_handlers=ac_meta_handlers,
        blueprint=ac_blueprint,
        max_keyed_scenes_per_chapter=ac_raw["max_keyed_scenes_per_chapter"],
        keyed_scene_mapping=ac_keyed_mapping,
        max_threats_per_chapter=ac_raw["max_threats_per_chapter"],
        threat_creation_mapping=ac_threat_creation,
    )


def _build_clock_keyed_scenes(cks_raw: dict[str, Any]) -> ClockKeyedScenesConfig:
    by_type = {
        clock_type: ClockKeyedSceneEntry(
            fractions=[float(f) for f in spec["fractions"]],
            priority=spec["priority"],
            narrative_hint_template=spec["narrative_hint_template"],
        )
        for clock_type, spec in cks_raw.items()
    }
    return ClockKeyedScenesConfig(by_clock_type=by_type)


def _build_random_events(re_raw: dict[str, Any]) -> RandomEventsConfig:
    re_keyed_mapping = {
        focus: RandomEventKeyedSceneMappingEntry(
            trigger_type=entry["trigger_type"],
            threshold=entry["threshold"],
            priority=entry["priority"],
            narrative_hint=entry["narrative_hint"],
        )
        for focus, entry in dict(re_raw["keyed_scene_mapping"]).items()
    }
    re_threat_creation = {
        focus: ThreatCreationMappingEntry(
            rank=entry["rank"],
            category=entry["category"],
        )
        for focus, entry in dict(re_raw["threat_creation_mapping"]).items()
    }
    return RandomEventsConfig(
        threat_target_probability=re_raw["threat_target_probability"],
        description_focus_categories=list(re_raw["description_focus_categories"]),
        npc_focus_categories=list(re_raw["npc_focus_categories"]),
        thread_focus_categories=list(re_raw["thread_focus_categories"]),
        threat_eligible_focus_categories=list(re_raw["threat_eligible_focus_categories"]),
        list_weight_max=re_raw["list_weight_max"],
        consolidation_threshold=re_raw["consolidation_threshold"],
        consolidation_weight_high=re_raw["consolidation_weight_high"],
        consolidation_weight_low=re_raw["consolidation_weight_low"],
        consolidation_weight_default=re_raw["consolidation_weight_default"],
        keyed_scene_mapping=re_keyed_mapping,
        threat_creation_mapping=re_threat_creation,
    )


def parse_engine_yaml(data: dict[str, Any]) -> EngineSettings:
    simple_parsed: dict[str, Any] = {key: _build_strict(cls, data[key]) for key, cls in _SIMPLE_SECTIONS.items()}

    npc_data = dict(data["npc"])
    npc_data["gate_memory_counts"] = {int(k): v for k, v in npc_data["gate_memory_counts"].items()}
    npc = _build_strict(NpcConfig, npc_data)

    stats_data = dict(data["stats"])
    stats_data["valid_arrays"] = [list(a) for a in stats_data["valid_arrays"]]
    stats = _build_strict(StatsConfig, stats_data)

    m_data = dict(data["momentum"])
    suffer = _build_strict(SufferRecoveryGain, dict(m_data.pop("suffer_recovery")))
    momentum = MomentumConfig(**m_data, suffer_recovery=suffer)

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

    impacts = {
        key: _build_strict(ImpactConfig, {**impact_data, "key": key}) for key, impact_data in data["impacts"].items()
    }

    legacy_data = dict(data["legacy"])
    legacy_data["ticks_by_rank"] = dict(legacy_data["ticks_by_rank"])
    legacy = _build_strict(LegacyConfig, legacy_data)

    progress_raw = data["progress"]
    track_types = {
        name: _build_strict(ProgressTrackType, {"ticks_per_mark": dict(tt["ticks_per_mark"])})
        for name, tt in progress_raw["track_types"].items()
    }
    progress = ProgressConfig(max_ticks=progress_raw["max_ticks"], track_types=track_types)

    engine_moves = {
        key: _build_strict(EngineMove, {"name": m["name"], "stats": list(m["stats"]), "roll_type": m["roll_type"]})
        for key, m in data["engine_moves"].items()
    }

    move_availability = {key: _parse_move_availability_rule(rule) for key, rule in data["move_availability"].items()}

    sw_raw = data["stopwords"]
    stopwords = StopwordsConfig(
        general=frozenset(sw_raw["general"]),
        location=frozenset(sw_raw["location"]),
    )

    name_titles = frozenset(data["name_titles"])

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

    ig = dict(data["information_gate"])
    ig_points = _build_strict(InformationGatePoints, dict(ig.pop("points")))
    ig_buckets = _build_strict(InformationGateBuckets, dict(ig.pop("buckets")))
    information_gate = InformationGateConfig(
        points=ig_points,
        buckets=ig_buckets,
        gate_min=ig["gate_min"],
        gate_max=ig["gate_max"],
        stance_caps=dict(ig["stance_caps"]),
        fact_budget_by_gate={int(k): int(v) for k, v in ig["fact_budget_by_gate"].items()},
    )

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

    nd = dict(data["narrative_direction"])
    nd_intensity = _build_strict(NarrativeIntensityThresholds, dict(nd.pop("intensity")))
    nd_result_map = {
        key: _build_strict(NarrativeDirectionEntry, dict(entry)) for key, entry in nd["result_map"].items()
    }
    narrative_direction = NarrativeDirectionConfig(intensity=nd_intensity, result_map=nd_result_map)

    succession_raw = dict(data["succession"])
    inheritance = _build_strict(InheritanceConfig, dict(succession_raw["inheritance"]))
    npc_carryover = {
        status: _build_strict(NpcCarryoverEntry, dict(entry))
        for status, entry in succession_raw["npc_carryover"].items()
    }
    succession = SuccessionConfig(
        inheritance=inheritance,
        npc_carryover=npc_carryover,
    )

    keyed_scenes = _build_keyed_scenes(dict(data["keyed_scenes"]))
    adventure_crafter = _build_adventure_crafter(dict(data["adventure_crafter"]))
    clock_keyed_scenes = _build_clock_keyed_scenes(dict(data["clock_keyed_scenes"]))
    random_events = _build_random_events(dict(data["random_events"]))

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
        parser=simple_parsed["parser"],
        story_state=simple_parsed["story_state"],
        chapter=simple_parsed["chapter"],
        setup_common=simple_parsed["setup_common"],
        metadata_voting=simple_parsed["metadata_voting"],
        naming=simple_parsed["naming"],
        random_events=random_events,
        ai_text=simple_parsed["ai_text"],
        recap_limits=simple_parsed["recap_limits"],
        status_descriptions=simple_parsed["status_descriptions"],
        truncations=simple_parsed["truncations"],
        persistence=simple_parsed["persistence"],
        correction=simple_parsed["correction"],
        succession=succession,
        keyed_scenes=keyed_scenes,
        adventure_crafter=adventure_crafter,
        clock_keyed_scenes=clock_keyed_scenes,
        scene_range_default=list(data["scene_range_default"]),
        death_emotions=list(data["death_emotions"]),
        creativity_seeds=list(data["creativity_seeds"]),
        _raw=data,
    )
