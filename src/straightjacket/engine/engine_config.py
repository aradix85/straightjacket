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
    npc_agency_interval: int = 5
    max_tool_rounds: int = 3


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
class ThreatConfig:
    """Threat menace system."""

    menace_on_miss: int = 1
    autonomous_tick_chance: float = 0.15
    menace_high_threshold: float = 0.75
    forsake_spirit_cost: int = 2


@dataclass
class ImpactConfig:
    """Single impact definition from engine.yaml `impacts` section."""

    key: str = ""
    label: str = ""
    description: str = ""
    blocks_recovery: str = ""  # health / spirit / supply / "" (empty = no block)
    permanent: bool = False


@dataclass
class LegacyConfig:
    """Legacy tracks and XP mechanics."""

    xp_per_box: int = 2  # XP granted per filled box (Ironsworn default)
    starting_rank: str = "epic"  # All legacy tracks start at epic rank (1 tick/mark)
    threat_overcome_bonus: int = 2  # Extra XP when vow completes with overcome threat at high menace
    threat_overcome_threshold: float = 0.5  # Menace >= this fraction to earn bonus
    asset_upgrade_cost: int = 2  # XP per asset ability upgrade
    new_asset_cost: int = 3  # XP for a new asset


@dataclass
class PositionResolverWeights:
    """Weights applied to resource/npc/chaos/momentum/threat factors."""

    resource_critical_below: int = 2
    resource_low_below: int = 3
    resource_critical: int = -2
    resource_low: int = -1
    npc_hostile: int = -2
    npc_distrustful: int = -1
    npc_friendly: int = 1
    npc_loyal: int = 2
    npc_bond_high: int = 1
    npc_bond_low: int = -1
    chaos_high: int = -1
    chaos_low: int = 1
    consecutive_misses: int = -2
    consecutive_strong: int = 1
    threat_clock_critical: int = -1
    secured_advantage: int = 2


@dataclass
class PositionOverride:
    """Situational override: evaluated after sum, caps/floors/shifts result."""

    name: str = ""
    conditions: list[str] = field(default_factory=list)
    effect: str = ""  # cap_at_risky / floor_at_risky / shift_up_one / etc.


@dataclass
class PositionResolverConfig:
    """Weighted scoring config for resolving action position."""

    desperate_below: int = -3
    controlled_above: int = 3
    weights: PositionResolverWeights = field(default_factory=PositionResolverWeights)
    move_baselines: dict[str, int] = field(default_factory=dict)
    overrides: list[PositionOverride] = field(default_factory=list)


@dataclass
class EffectResolverWeights:
    """Weights applied to position correlation + bond + secured advantage."""

    desperate: int = -1
    controlled: int = 1
    bond_high: int = 1
    bond_low: int = -1
    secured_advantage: int = 1


@dataclass
class EffectResolverConfig:
    """Weighted scoring config for resolving action effect."""

    limited_below: int = -2
    great_above: int = 2
    weights: EffectResolverWeights = field(default_factory=EffectResolverWeights)
    move_baselines: dict[str, int] = field(default_factory=dict)


@dataclass
class InformationGatePoints:
    """Points awarded per factor for computing information gate level."""

    scenes_known_1: int = 0
    scenes_known_2_3: int = 1
    scenes_known_4_plus: int = 2
    gather_success: int = 1
    bond_1: int = 0
    bond_2_3: int = 1
    bond_4_plus: int = 2


@dataclass
class InformationGateConfig:
    """Information gate: how much NPCs reveal based on scenes/bond/stance."""

    points: InformationGatePoints = field(default_factory=InformationGatePoints)
    stance_caps: dict[str, int] = field(default_factory=dict)
    default_cap: int = 4


@dataclass
class NarrativeIntensityThresholds:
    """Resource thresholds for narrative intensity classification."""

    critical_below: int = 1
    high_below: int = 3
    moderate_below: int = 4


@dataclass
class NarrativeDirectionEntry:
    """Tempo + perspective for a single roll result."""

    tempo: str = "moderate"
    perspective: str = "action_detail"


@dataclass
class NarrativeDirectionConfig:
    """Narrative writing directions derived from game state."""

    intensity: NarrativeIntensityThresholds = field(default_factory=NarrativeIntensityThresholds)
    result_map: dict[str, NarrativeDirectionEntry] = field(default_factory=dict)

    def entry_for(self, roll_result: str) -> NarrativeDirectionEntry:
        """Get the entry for a roll result, falling back to _default."""
        return self.result_map.get(roll_result, self.result_map.get("_default", NarrativeDirectionEntry()))


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
    threats: ThreatConfig = field(default_factory=ThreatConfig)
    impacts: dict[str, ImpactConfig] = field(default_factory=dict)
    legacy: LegacyConfig = field(default_factory=LegacyConfig)
    position_resolver: PositionResolverConfig = field(default_factory=PositionResolverConfig)
    effect_resolver: EffectResolverConfig = field(default_factory=EffectResolverConfig)
    information_gate: InformationGateConfig = field(default_factory=InformationGateConfig)
    narrative_direction: NarrativeDirectionConfig = field(default_factory=NarrativeDirectionConfig)
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

    # Lazy cache for compiled regex pattern lists. Lives with the settings
    # instance: reload_engine() builds a fresh instance, so the cache resets
    # automatically. No manual invalidation needed.
    _compiled_patterns: dict[str, Any] = field(default_factory=dict, repr=False)

    def get_raw(self, key: str, default: Any = None) -> Any:
        """Access flexible sections (stance_matrix, move_outcomes, etc.) as plain dicts."""
        return self._raw.get(key, default)

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
    "threats": ThreatConfig,
    "legacy": LegacyConfig,
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
    if "impacts" in data:
        s.impacts = {
            key: _build_nested(ImpactConfig, {**impact_data, "key": key})
            for key, impact_data in data["impacts"].items()
        }
    if "position_resolver" in data:
        pr = dict(data["position_resolver"])
        weights = _build_nested(PositionResolverWeights, pr.pop("weights", {}))
        overrides = [_build_nested(PositionOverride, o) for o in pr.pop("overrides", [])]
        s.position_resolver = PositionResolverConfig(
            desperate_below=pr.get("desperate_below", -3),
            controlled_above=pr.get("controlled_above", 3),
            weights=weights,
            move_baselines=dict(pr.get("move_baselines", {})),
            overrides=overrides,
        )
    if "effect_resolver" in data:
        er = dict(data["effect_resolver"])
        weights = _build_nested(EffectResolverWeights, er.pop("weights", {}))
        s.effect_resolver = EffectResolverConfig(
            limited_below=er.get("limited_below", -2),
            great_above=er.get("great_above", 2),
            weights=weights,
            move_baselines=dict(er.get("move_baselines", {})),
        )
    if "information_gate" in data:
        ig = dict(data["information_gate"])
        points = _build_nested(InformationGatePoints, ig.pop("points", {}))
        s.information_gate = InformationGateConfig(
            points=points,
            stance_caps=dict(ig.get("stance_caps", {})),
            default_cap=ig.get("default_cap", 4),
        )
    if "narrative_direction" in data:
        nd = dict(data["narrative_direction"])
        intensity = _build_nested(NarrativeIntensityThresholds, nd.pop("intensity", {}))
        result_map = {
            key: _build_nested(NarrativeDirectionEntry, entry) for key, entry in nd.pop("result_map", {}).items()
        }
        s.narrative_direction = NarrativeDirectionConfig(intensity=intensity, result_map=result_map)

    # Scalar top-level fields
    if "scene_range_default" in data:
        s.scene_range_default = list(data["scene_range_default"])
    if "death_emotions" in data:
        s.death_emotions = list(data["death_emotions"])
    if "creativity_seeds" in data:
        s.creativity_seeds = list(data["creativity_seeds"])

    return s
