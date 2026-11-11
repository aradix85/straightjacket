from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from straightjacket.engine.config_binding import RawSections, bind_sections
from straightjacket.engine.config_loader import PROJECT_ROOT
from straightjacket.engine.gamemaster.config_types import (
    ActivationScores,
    ChaosConfig,
    ChaosResolverConfig,
    ChapterConfig,
    ClockKeyedSceneEntry,
    ClocksConfig,
    DescriptionDedupConfig,
    EffectResolverConfig,
    EnumsConfig,
    FactResolutionConfig,
    FateConfig,
    FuzzyMatchConfig,
    GameMasterMove,
    GenerationConfig,
    InformationGateConfig,
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
    PositionResolverConfig,
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
from straightjacket.engine.logging_util import log
from straightjacket.engine.yaml_merge import load_yaml_dir

if TYPE_CHECKING:
    from pathlib import Path

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
    clock_keyed_scenes: dict[str, ClockKeyedSceneEntry]
    clocks: ClocksConfig
    outcomes: OutcomesConfig
    moves: dict[str, GameMasterMove]


_FACT_SUBJECTS = ("place", "npc")


def _check_fact_resolution(facts: FactResolutionConfig) -> None:
    for name, spec in facts.types.items():
        if spec.subject not in _FACT_SUBJECTS:
            msg = f"fact type {name!r} has subject {spec.subject!r}; valid: {list(_FACT_SUBJECTS)}"
            raise ValueError(msg)
    for name in facts.information_miss_settles:
        if name not in facts.types or facts.types[name].subject != "place":
            msg = f"information_miss_settles names {name!r}, which is not a place fact type"
            raise ValueError(msg)


def parse_gamemaster_yaml(data: dict[str, object]) -> GameMasterSettings:
    settings = bind_sections(GameMasterSettings, data)
    _check_fact_resolution(settings.fact_resolution)
    return settings


_cache: dict[Path, GameMasterSettings] = {}


def gm() -> GameMasterSettings:
    if _CONFIG_DIR not in _cache:
        data = load_yaml_dir(_CONFIG_DIR, missing_dir_hint="The gamemaster/ directory ships with the repo.")
        _cache[_CONFIG_DIR] = parse_gamemaster_yaml(data)
        log(f"[Config] Loaded {_CONFIG_DIR} ({len(data)} sections)")
    return _cache[_CONFIG_DIR]
