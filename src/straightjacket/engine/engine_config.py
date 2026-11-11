from __future__ import annotations

from dataclasses import dataclass

from straightjacket.engine.config_binding import RawSections
from straightjacket.engine.engine_config_dataclasses import (
    AiTextConfig,
    CorrectionConfig,
    NarrativeDirectionConfig,
    NarratorMeterDescription,
    ParserConfig,
    PersistenceConfig,
    PromptDisplayConfig,
    RateLimitConfig,
    RecapLimitsConfig,
    RetryConfig,
    StatusDescriptionsConfig,
    TruncationsConfig,
)


@dataclass
class EngineSettings(RawSections):
    ai_text: AiTextConfig
    correction: CorrectionConfig
    narrative_direction: NarrativeDirectionConfig
    narrator_status_descriptions: dict[str, NarratorMeterDescription]
    parser: ParserConfig
    persistence: PersistenceConfig
    prompt_display: PromptDisplayConfig
    rate_limit: RateLimitConfig
    recap_limits: RecapLimitsConfig
    retry: RetryConfig
    status_descriptions: StatusDescriptionsConfig
    truncations: TruncationsConfig
    scene_range_default: list[int]
    creativity_seeds: list[str]
