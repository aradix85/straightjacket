from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config_binding import RawSections, build_strict, reject_unknown
from .engine_config_dataclasses import (
    AiTextConfig,
    CorrectionConfig,
    MetadataVotingConfig,
    NarrativeDirectionConfig,
    NarrativeDirectionEntry,
    NarrativeIntensityThresholds,
    NarratorStatusDescriptions,
    ParserConfig,
    PersistenceConfig,
    PromptDisplayConfig,
    RateLimitConfig,
    RecapLimitsConfig,
    RetryConfig,
    SetupCommonConfig,
    StatusDescriptionsConfig,
    TruncationsConfig,
)


@dataclass
class EngineSettings(RawSections):
    ai_text: AiTextConfig
    correction: CorrectionConfig
    metadata_voting: MetadataVotingConfig
    narrative_direction: NarrativeDirectionConfig
    narrator_status_descriptions: NarratorStatusDescriptions
    parser: ParserConfig
    persistence: PersistenceConfig
    prompt_display: PromptDisplayConfig
    rate_limit: RateLimitConfig
    recap_limits: RecapLimitsConfig
    retry: RetryConfig
    setup_common: SetupCommonConfig
    status_descriptions: StatusDescriptionsConfig
    truncations: TruncationsConfig
    scene_range_default: list[int]
    creativity_seeds: list[str]

    _raw: dict[str, Any] = field(default_factory=dict, repr=False)


_SIMPLE_SECTIONS: dict[str, type] = {
    "ai_text": AiTextConfig,
    "correction": CorrectionConfig,
    "metadata_voting": MetadataVotingConfig,
    "narrator_status_descriptions": NarratorStatusDescriptions,
    "parser": ParserConfig,
    "persistence": PersistenceConfig,
    "prompt_display": PromptDisplayConfig,
    "rate_limit": RateLimitConfig,
    "recap_limits": RecapLimitsConfig,
    "retry": RetryConfig,
    "setup_common": SetupCommonConfig,
    "status_descriptions": StatusDescriptionsConfig,
    "truncations": TruncationsConfig,
}


def _build_narrative_direction(nd: dict[str, Any]) -> NarrativeDirectionConfig:
    reject_unknown(NarrativeDirectionConfig, nd)
    return NarrativeDirectionConfig(
        intensity=build_strict(NarrativeIntensityThresholds, dict(nd["intensity"])),
        result_map={key: build_strict(NarrativeDirectionEntry, dict(entry)) for key, entry in nd["result_map"].items()},
    )


def parse_engine_yaml(data: dict[str, Any]) -> EngineSettings:
    simple: dict[str, Any] = {key: build_strict(cls, data[key]) for key, cls in _SIMPLE_SECTIONS.items()}
    return EngineSettings(
        **simple,
        narrative_direction=_build_narrative_direction(dict(data["narrative_direction"])),
        scene_range_default=list(data["scene_range_default"]),
        creativity_seeds=list(data["creativity_seeds"]),
        _raw=data,
    )
