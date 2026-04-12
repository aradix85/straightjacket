#!/usr/bin/env python3
"""Typed engine configuration dataclasses.

Replaces _ConfigNode dot-access wrapper for engine.yaml with validated,
type-safe dataclasses. Flexible sections (stance_matrix, move_outcomes,
consequence_templates, etc.) stay as plain dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NpcConfig:
    """NPC system limits and thresholds."""

    max_active: int = 12
    max_memory_entries: int = 25
    max_observations: int = 15
    max_reflections: int = 8
    activation_threshold: float = 0.7
    mention_threshold: float = 0.3
    max_activated: int = 3
    reflection_threshold: int = 30
    memory_recency_decay: float = 0.92
    reflection_importance: int = 8
    death_corroboration_min_importance: int = 9
    seed_importance_floor: int = 3
    reflection_recency_floor: float = 0.6
    about_npc_relevance_boost: float = 0.6
    consolidation_recency_ratio: float = 0.6
    monologue_max_chars: int = 200
    description_max_chars: int = 200
    arc_max_chars: int = 300
    gate_memory_counts: dict[int, int] = field(default_factory=lambda: {0: 0, 1: 0, 2: 3, 3: 5, 4: 5})
    activated_memory_count: int = 2


@dataclass
class ChaosConfig:
    """Chaos factor bounds."""

    min: int = 1
    max: int = 9
    start: int = 5
    interrupt_types: list[str] = field(default_factory=list)


@dataclass
class PacingConfig:
    """Pacing thresholds and limits."""

    director_interval: int = 3
    max_narration_history: int = 3
    max_narration_chars: int = 1500
    max_session_log: int = 50
    window_size: int = 5
    intense_threshold: int = 3
    calm_threshold: int = 2
    autonomous_clock_tick_chance: float = 0.20
    weak_hit_clock_tick_chance: float = 0.50
    fired_clock_keep_scenes: int = 3


@dataclass
class StatsConfig:
    """Character stat rules."""

    target_sum: int = 9
    min: int = 0
    max: int = 3
    names: list[str] = field(default_factory=lambda: ["edge", "heart", "iron", "shadow", "wits", "none"])
    valid_arrays: list[list[int]] = field(default_factory=lambda: [[3, 2, 2, 1, 1]])


@dataclass
class CreationConfig:
    """Character creation rules."""

    max_paths: int = 2
    max_starting_assets: int = 1
    starting_asset_categories: list[str] = field(default_factory=list)
    background_vow_default_rank: str = "extreme"
    chaos_vow_modifiers: dict[str, list[str]] = field(default_factory=dict)
    chaos_modifier_values: dict[str, int] = field(default_factory=dict)
    truth_threads: dict[str, str] = field(default_factory=dict)


@dataclass
class ResourcesConfig:
    """Resource track caps and starting values."""

    health_max: int = 5
    spirit_max: int = 5
    supply_max: int = 5
    health_start: int = 5
    spirit_start: int = 5
    supply_start: int = 5


@dataclass
class MomentumGain:
    """Momentum gain values per result."""

    weak_hit: int = 1
    strong_hit: dict[str, int] = field(default_factory=lambda: {"standard": 2, "great": 3})


@dataclass
class MomentumConfig:
    """Momentum bounds and gain/loss tables."""

    floor: int = -6
    max: int = 10
    start: int = 2
    gain: MomentumGain = field(default_factory=MomentumGain)
    loss: dict[str, int] = field(default_factory=lambda: {"risky": 2, "desperate": 3})


@dataclass
class BondsConfig:
    """NPC bond defaults."""

    max: int = 4
    start: int = 0


@dataclass
class ActivationScores:
    """TF-IDF activation scoring weights."""

    target: float = 1.0
    name_match: float = 0.8
    name_part: float = 0.6
    alias_match: float = 0.7
    location_match: float = 0.3
    recent_interaction: float = 0.2
    max_recursive: int = 1


@dataclass
class LocationConfig:
    """Location tracking."""

    history_size: int = 5


@dataclass
class OpeningConfig:
    """Opening scene defaults."""

    time_of_day: str = "morning"
    clock_segments: int = 6
    clock_filled: int = 1
    clock_fallback_name: str = "Looming threat"
    clock_trigger_template: str = "Threat escalates beyond {player}'s control"


@dataclass
class ArchitectConfig:
    """Story architect constraints."""

    forbidden_moods: list[str] = field(default_factory=list)


@dataclass
class FateLikelihoodRules:
    """Fate system likelihood resolution rules."""

    disposition_scores: dict[str, int] = field(default_factory=dict)
    chaos_thresholds: dict[str, int] = field(default_factory=dict)
    chaos_scores: dict[str, int] = field(default_factory=dict)
    resource_critical_below: int = 2
    resource_scores: dict[str, int] = field(default_factory=dict)
    score_to_odds: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FateConfig:
    """Fate system (Mythic GME 2e) config."""

    default_method: str = "fate_chart"
    likelihood_rules: FateLikelihoodRules = field(default_factory=FateLikelihoodRules)


@dataclass
class StoryConfig:
    """Story structure config."""

    kishotenketsu_probability: dict[str, float] = field(default_factory=dict)
    kishotenketsu_default: float = 0.50


@dataclass
class EnumsConfig:
    """Enum value lists used by schemas."""

    time_phases: list[str] = field(default_factory=list)
    npc_statuses: list[str] = field(default_factory=list)
    dispositions: list[str] = field(default_factory=list)
    memory_types: list[str] = field(default_factory=list)
    clock_types: list[str] = field(default_factory=list)
    thread_types: list[str] = field(default_factory=list)
    story_structures: list[str] = field(default_factory=list)
    positions: list[str] = field(default_factory=list)


@dataclass
class MemoryRetrievalWeights:
    """Memory scoring weights."""

    recency: float = 0.40
    importance: float = 0.35
    relevance: float = 0.25


@dataclass
class RecoveryConfig:
    """Recovery move healing amounts."""

    weak_hit: int = 1
    strong_hit: dict[str, int] = field(default_factory=lambda: {"standard": 1, "great": 2})


@dataclass
class EngineSettings:
    """Complete typed engine configuration.

    Typed sections have dedicated dataclasses with validated fields.
    Flexible sections (stance_matrix, move_outcomes, etc.) are plain dicts
    accessed via get_raw().
    """

    npc: NpcConfig = field(default_factory=NpcConfig)
    chaos: ChaosConfig = field(default_factory=ChaosConfig)
    pacing: PacingConfig = field(default_factory=PacingConfig)
    stats: StatsConfig = field(default_factory=StatsConfig)
    creation: CreationConfig = field(default_factory=CreationConfig)
    resources: ResourcesConfig = field(default_factory=ResourcesConfig)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)
    bonds: BondsConfig = field(default_factory=BondsConfig)
    activation_scores: ActivationScores = field(default_factory=ActivationScores)
    location: LocationConfig = field(default_factory=LocationConfig)
    opening: OpeningConfig = field(default_factory=OpeningConfig)
    architect: ArchitectConfig = field(default_factory=ArchitectConfig)
    fate: FateConfig = field(default_factory=FateConfig)
    story: StoryConfig = field(default_factory=StoryConfig)
    enums: EnumsConfig = field(default_factory=EnumsConfig)
    memory_retrieval_weights: MemoryRetrievalWeights = field(default_factory=MemoryRetrievalWeights)
    recovery: RecoveryConfig = field(default_factory=RecoveryConfig)

    # Scalar top-level fields
    scene_range_default: list[int] = field(default_factory=lambda: [1, 20])
    death_emotions: list[str] = field(default_factory=list)
    creativity_seeds: list[str] = field(default_factory=list)

    # Flexible sections — accessed via get_raw() as plain dicts
    _raw: dict = field(default_factory=dict, repr=False)

    def get_raw(self, key: str, default: Any = None) -> Any:
        """Access flexible sections (stance_matrix, move_outcomes, etc.) as plain dicts."""
        return self._raw.get(key, default)


def _build_nested(cls: type, data: dict) -> Any:
    """Build a dataclass from a dict, ignoring unknown keys."""
    import dataclasses

    known = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


# Sections that map directly: YAML key → EngineSettings field → dataclass type.
# _build_nested handles these without any pre-processing.
_SIMPLE_SECTIONS: dict[str, type] = {
    "chaos": ChaosConfig,
    "pacing": PacingConfig,
    "creation": CreationConfig,
    "resources": ResourcesConfig,
    "bonds": BondsConfig,
    "activation_scores": ActivationScores,
    "location": LocationConfig,
    "opening": OpeningConfig,
    "architect": ArchitectConfig,
    "story": StoryConfig,
    "enums": EnumsConfig,
    "memory_retrieval_weights": MemoryRetrievalWeights,
}


def parse_engine_yaml(data: dict) -> EngineSettings:
    """Parse raw engine.yaml dict into typed EngineSettings."""
    s = EngineSettings()
    s._raw = data

    # Auto-parse simple sections
    for key, cls in _SIMPLE_SECTIONS.items():
        if key in data:
            setattr(s, key, _build_nested(cls, data[key]))

    # Sections with pre-processing
    if "npc" in data:
        npc_data = dict(data["npc"])
        if "gate_memory_counts" in npc_data:
            npc_data["gate_memory_counts"] = {int(k): v for k, v in npc_data["gate_memory_counts"].items()}
        s.npc = _build_nested(NpcConfig, npc_data)
    if "stats" in data:
        d = dict(data["stats"])
        if "valid_arrays" in d:
            d["valid_arrays"] = [list(a) for a in d["valid_arrays"]]
        s.stats = _build_nested(StatsConfig, d)
    if "momentum" in data:
        md = dict(data["momentum"])
        gain_data = md.pop("gain", {})
        loss_data = md.pop("loss", {})
        gain = MomentumGain(
            weak_hit=gain_data.get("weak_hit", 1),
            strong_hit=dict(gain_data.get("strong_hit", {"standard": 2, "great": 3})),
        )
        s.momentum = MomentumConfig(**md, gain=gain, loss=dict(loss_data))
    if "fate" in data:
        fd = dict(data["fate"])
        lr_data = fd.pop("likelihood_rules", {})
        lr = _build_nested(FateLikelihoodRules, lr_data)
        s.fate = FateConfig(default_method=fd.get("default_method", "fate_chart"), likelihood_rules=lr)
    if "recovery" in data:
        rd = dict(data["recovery"])
        sh = rd.pop("strong_hit", {"standard": 1, "great": 2})
        s.recovery = RecoveryConfig(weak_hit=rd.get("weak_hit", 1), strong_hit=dict(sh))

    # Scalar top-level fields
    if "scene_range_default" in data:
        s.scene_range_default = list(data["scene_range_default"])
    if "death_emotions" in data:
        s.death_emotions = list(data["death_emotions"])
    if "creativity_seeds" in data:
        s.creativity_seeds = list(data["creativity_seeds"])

    return s
