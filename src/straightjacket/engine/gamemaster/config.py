from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config_binding import RawSections, build_strict, reject_unknown
from ..config_loader import PROJECT_ROOT
from ..logging_util import log
from ..yaml_merge import load_yaml_dir
from .config_types import (
    ActivationScores,
    ChaosConfig,
    ChaosResolverConfig,
    ChapterConfig,
    ClockCreationMappingEntry,
    ClockFillConsequenceEntry,
    ClockKeyedSceneEntry,
    ClockKeyedScenesConfig,
    ClocksConfig,
    ComplicationClockConfig,
    DescriptionDedupConfig,
    EffectResolverConfig,
    EffectResolverWeights,
    EnumsConfig,
    FactResolutionConfig,
    FactTypeConfig,
    FateConfig,
    FateLikelihoodRules,
    FuzzyMatchConfig,
    GameMasterMove,
    GenerationConfig,
    InformationGateBuckets,
    InformationGateConfig,
    InformationGatePoints,
    KeyedScenesConfig,
    LocationConfig,
    MemoryConfig,
    MemoryEmotions,
    MemoryRetrievalWeights,
    MemoryTemplates,
    MythicDiceConfig,
    NamingConfig,
    NpcConfig,
    NpcMatchingConfig,
    NpcStatusGroups,
    OpeningConfig,
    OutcomesConfig,
    PacingConfig,
    PatternGrammar,
    PositionOverride,
    PositionResolverConfig,
    PositionResolverWeights,
    RandomEventKeyedSceneMappingEntry,
    RandomEventsConfig,
    SceneAdjustments,
    SceneContextTemplates,
    StanceBondBuckets,
    StanceMatrixEntry,
    StanceMoveBuckets,
    StopwordsConfig,
    StoryConfig,
    StoryStateConfig,
    TfIdfConfig,
    TimeProgressionSteps,
)

_CONFIG_DIR = PROJECT_ROOT / "gamemaster"


@dataclass
class GameMasterSettings(RawSections):
    npc: NpcConfig
    mythic_dice: MythicDiceConfig
    npc_status_groups: NpcStatusGroups
    chaos: ChaosConfig
    pacing: PacingConfig
    activation_scores: ActivationScores
    location: LocationConfig
    opening: OpeningConfig
    stopwords: StopwordsConfig
    name_titles: frozenset[str]
    position_resolver: PositionResolverConfig
    effect_resolver: EffectResolverConfig
    information_gate: InformationGateConfig
    stance_bond_buckets: StanceBondBuckets
    stance_move_buckets: StanceMoveBuckets
    stance_matrix: dict[str, dict[str, dict[str, StanceMatrixEntry]]]
    time_progression_steps: TimeProgressionSteps
    scene_adjustments: SceneAdjustments
    scene_context: SceneContextTemplates
    memory_emotions: MemoryEmotions
    memory_templates: MemoryTemplates
    fate: FateConfig
    fact_resolution: FactResolutionConfig
    generation: GenerationConfig
    story: StoryConfig
    enums: EnumsConfig
    memory_retrieval_weights: MemoryRetrievalWeights
    fuzzy_match: FuzzyMatchConfig
    npc_matching: NpcMatchingConfig
    tf_idf: TfIdfConfig
    memory: MemoryConfig
    chaos_resolver: ChaosResolverConfig
    description_dedup: DescriptionDedupConfig
    story_state: StoryStateConfig
    chapter: ChapterConfig
    naming: NamingConfig
    random_events: RandomEventsConfig
    keyed_scenes: KeyedScenesConfig
    clock_keyed_scenes: ClockKeyedScenesConfig
    clocks: ClocksConfig
    outcomes: OutcomesConfig
    moves: dict[str, GameMasterMove]

    _raw: dict[str, Any] = field(default_factory=dict, repr=False)


_SIMPLE_SECTIONS: dict[str, type] = {
    "mythic_dice": MythicDiceConfig,
    "npc_status_groups": NpcStatusGroups,
    "chaos": ChaosConfig,
    "pacing": PacingConfig,
    "activation_scores": ActivationScores,
    "location": LocationConfig,
    "opening": OpeningConfig,
    "story": StoryConfig,
    "enums": EnumsConfig,
    "memory_retrieval_weights": MemoryRetrievalWeights,
    "fuzzy_match": FuzzyMatchConfig,
    "npc_matching": NpcMatchingConfig,
    "tf_idf": TfIdfConfig,
    "memory": MemoryConfig,
    "chaos_resolver": ChaosResolverConfig,
    "description_dedup": DescriptionDedupConfig,
    "story_state": StoryStateConfig,
    "chapter": ChapterConfig,
    "naming": NamingConfig,
    "generation": GenerationConfig,
    "outcomes": OutcomesConfig,
    "stance_bond_buckets": StanceBondBuckets,
    "stance_move_buckets": StanceMoveBuckets,
    "time_progression_steps": TimeProgressionSteps,
    "scene_adjustments": SceneAdjustments,
    "scene_context": SceneContextTemplates,
    "memory_emotions": MemoryEmotions,
    "memory_templates": MemoryTemplates,
}


def _build_keyed_scenes(keyed_raw: dict[str, Any]) -> KeyedScenesConfig:
    reject_unknown(KeyedScenesConfig, keyed_raw)
    pattern_grammars_raw = dict(keyed_raw["pattern_grammars"])
    pattern_grammars = {
        trigger_name: PatternGrammar(
            pattern_prefixes=list(reject_unknown(PatternGrammar, spec)["pattern_prefixes"]),
            matcher_strategy=spec["matcher_strategy"],
        )
        for trigger_name, spec in pattern_grammars_raw.items()
    }
    return KeyedScenesConfig(
        triggers=frozenset(keyed_raw["triggers"]),
        prompt_wrapper=keyed_raw["prompt_wrapper"],
        pattern_grammars=pattern_grammars,
    )


def _build_clock_keyed_scenes(cks_raw: dict[str, Any]) -> ClockKeyedScenesConfig:
    by_type = {
        clock_type: ClockKeyedSceneEntry(
            fractions=[float(f) for f in reject_unknown(ClockKeyedSceneEntry, spec)["fractions"]],
            priority=spec["priority"],
            narrative_hint_template=spec["narrative_hint_template"],
        )
        for clock_type, spec in cks_raw.items()
    }
    return ClockKeyedScenesConfig(by_clock_type=by_type)


def _build_random_events(re_raw: dict[str, Any]) -> RandomEventsConfig:
    reject_unknown(RandomEventsConfig, re_raw)
    re_keyed_mapping = {
        focus: build_strict(RandomEventKeyedSceneMappingEntry, dict(entry))
        for focus, entry in dict(re_raw["keyed_scene_mapping"]).items()
    }
    re_clock_creation = {
        focus: build_strict(ClockCreationMappingEntry, dict(entry))
        for focus, entry in dict(re_raw["clock_creation_mapping"]).items()
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
        seeded_list_weight=re_raw["seeded_list_weight"],
        keyed_scene_mapping=re_keyed_mapping,
        danger_foci=list(re_raw["danger_foci"]),
        clock_creation_mapping=re_clock_creation,
    )


def _build_clocks(c_raw: dict[str, Any]) -> ClocksConfig:
    reject_unknown(ClocksConfig, c_raw)
    fill = {
        clock_type: build_strict(ClockFillConsequenceEntry, dict(entry))
        for clock_type, entry in dict(c_raw["fill_consequences"]).items()
    }
    return ClocksConfig(
        default_owner_kind=c_raw["default_owner_kind"],
        default_segments=c_raw["default_segments"],
        max_open_emergent=c_raw["max_open_emergent"],
        miss_ticks_by_position={str(k): int(v) for k, v in dict(c_raw["miss_ticks_by_position"]).items()},
        fill_consequences=fill,
        complication=build_strict(ComplicationClockConfig, dict(c_raw["complication"])),
        duplicate_name_template=c_raw["duplicate_name_template"],
    )


_FACT_SUBJECTS = ("place", "npc")


def _build_fact_resolution(fr_raw: dict[str, Any]) -> FactResolutionConfig:
    types = {
        name: build_strict(FactTypeConfig, {**spec, "inputs": dict(spec["inputs"])})
        for name, spec in dict(fr_raw.pop("types")).items()
    }
    for name, spec in types.items():
        if spec.subject not in _FACT_SUBJECTS:
            raise ValueError(f"fact type {name!r} has subject {spec.subject!r}; valid: {list(_FACT_SUBJECTS)}")
    settles = dict(fr_raw.pop("information_miss_settles"))
    for name in settles:
        if name not in types or types[name].subject != "place":
            raise ValueError(f"information_miss_settles names {name!r}, which is not a place fact type")
    config: FactResolutionConfig = build_strict(
        FactResolutionConfig, {**fr_raw, "types": types, "information_miss_settles": settles}
    )
    return config


def _build_position_resolver(pr: dict[str, Any]) -> PositionResolverConfig:
    reject_unknown(PositionResolverConfig, pr)
    return PositionResolverConfig(
        desperate_below=pr["desperate_below"],
        controlled_above=pr["controlled_above"],
        npc_bond_high_min=pr["npc_bond_high_min"],
        npc_bond_low_max=pr["npc_bond_low_max"],
        strain_weights=dict(pr["strain_weights"]),
        disposition_weights=dict(pr["disposition_weights"]),
        weights=build_strict(PositionResolverWeights, dict(pr["weights"])),
        move_baselines=dict(pr["move_baselines"]),
        overrides=[build_strict(PositionOverride, dict(o)) for o in pr["overrides"]],
    )


def _build_effect_resolver(er: dict[str, Any]) -> EffectResolverConfig:
    reject_unknown(EffectResolverConfig, er)
    return EffectResolverConfig(
        limited_below=er["limited_below"],
        great_above=er["great_above"],
        bond_high_min=er["bond_high_min"],
        bond_low_max=er["bond_low_max"],
        position_weights=dict(er["position_weights"]),
        weights=build_strict(EffectResolverWeights, dict(er["weights"])),
    )


def _build_information_gate(ig: dict[str, Any]) -> InformationGateConfig:
    reject_unknown(InformationGateConfig, ig)
    return InformationGateConfig(
        points=build_strict(InformationGatePoints, dict(ig["points"])),
        buckets=build_strict(InformationGateBuckets, dict(ig["buckets"])),
        gate_min=ig["gate_min"],
        gate_max=ig["gate_max"],
        stance_caps=dict(ig["stance_caps"]),
        fact_budget_by_gate={int(k): int(v) for k, v in ig["fact_budget_by_gate"].items()},
        miss_stance=build_strict(StanceMatrixEntry, dict(ig["miss_stance"])),
        hit_stance=build_strict(StanceMatrixEntry, dict(ig["hit_stance"])),
        refusing_stances=list(ig["refusing_stances"]),
    )


def _build_fate(f_data: dict[str, Any]) -> FateConfig:
    reject_unknown(FateConfig, f_data)
    lr = build_strict(FateLikelihoodRules, dict(f_data["likelihood_rules"]))
    return FateConfig(default_method=f_data["default_method"], likelihood_rules=lr)


def parse_gamemaster_yaml(data: dict[str, Any]) -> GameMasterSettings:
    simple: dict[str, Any] = {key: build_strict(cls, data[key]) for key, cls in _SIMPLE_SECTIONS.items()}
    npc_data = dict(data["npc"])
    npc_data["gate_memory_counts"] = {int(k): v for k, v in npc_data["gate_memory_counts"].items()}
    sw_raw = reject_unknown(StopwordsConfig, dict(data["stopwords"]))
    stance_matrix: dict[str, dict[str, dict[str, StanceMatrixEntry]]] = {
        disp: {
            bond: {cat: build_strict(StanceMatrixEntry, dict(entry)) for cat, entry in cats.items()}
            for bond, cats in bonds.items()
        }
        for disp, bonds in data["stance_matrix"].items()
    }
    return GameMasterSettings(
        **simple,
        npc=build_strict(NpcConfig, npc_data),
        stopwords=StopwordsConfig(general=frozenset(sw_raw["general"]), location=frozenset(sw_raw["location"])),
        name_titles=frozenset(data["name_titles"]),
        position_resolver=_build_position_resolver(dict(data["position_resolver"])),
        effect_resolver=_build_effect_resolver(dict(data["effect_resolver"])),
        information_gate=_build_information_gate(dict(data["information_gate"])),
        stance_matrix=stance_matrix,
        fate=_build_fate(dict(data["fate"])),
        fact_resolution=_build_fact_resolution(dict(data["fact_resolution"])),
        random_events=_build_random_events(dict(data["random_events"])),
        keyed_scenes=_build_keyed_scenes(dict(data["keyed_scenes"])),
        clock_keyed_scenes=_build_clock_keyed_scenes(dict(data["clock_keyed_scenes"])),
        clocks=_build_clocks(dict(data["clocks"])),
        moves={key: build_strict(GameMasterMove, dict(move)) for key, move in data["moves"].items()},
        _raw=data,
    )


_gm: GameMasterSettings | None = None


def gm() -> GameMasterSettings:
    global _gm
    if _gm is None:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The gamemaster/ directory ships with the repo.")
        _gm = parse_gamemaster_yaml(data)
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _gm
