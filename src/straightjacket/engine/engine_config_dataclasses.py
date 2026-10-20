from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PromptDisplayConfig:
    insight_chars: int
    recent_event_chars: int
    lore_description_chars: int
    lore_max_aliases: int
    epilogue_log_scenes: int
    recent_events_window: int
    campaign_history_chapters: int
    memory_consequences_max: int
    memory_npcs_max: int
    creativity_seed_count: int


@dataclass
class NarratorMeterDescription:
    flag_at_zero: str
    levels: dict[int, str]


@dataclass
class CorrectionConfig:
    ops: list[str]
    npc_edit_fields: list[str]


@dataclass
class NarrativeIntensityThresholds:
    meters: list[str]
    critical_below: int
    high_below: int
    moderate_below: int


@dataclass
class NarrativeDirectionEntry:
    tempo: str
    perspective: str


@dataclass
class NarrativeDirectionConfig:
    intensity: NarrativeIntensityThresholds
    by_outcome: dict[str, NarrativeDirectionEntry]


@dataclass
class RateLimitConfig:
    window_seconds: float
    max_requests: int
    warn_probe_max_tries: int
    warn_probe_poll_seconds: float


@dataclass
class RetryConfig:
    retryable_http_codes: list[int]
    backoff_base: int
    max_retry_after_seconds: float
    brain_stat_retries: int


@dataclass
class ParserConfig:
    salvage_min_length: int
    role_prefixes: list[str]
    leaked_prompt_tags: list[str]
    stream_hold_markers: list[str]
    stream_sentence_boundary: str
    stream_abbreviations: list[str]
    sentence_end_marks: list[str]
    sentence_breaks: list[str]
    epilogue_heading: str
    think_open: str
    think_block: str


@dataclass
class StatusDescriptionsConfig:
    meters: dict[str, dict[int, str]]
    bond: dict[int, str]
    clock: dict[int, str]
    track: dict[int, str]
    legacy: dict[int, str]
    xp: dict[int, str]
    combat_position: dict[str, str]
    menace: dict[int, str]
    act_progress: dict[str, str]


@dataclass
class AiTextConfig:
    schema_titles: dict[str, str]
    no_stat: str
    no_roll_type: str
    brain_trigger_hints: dict[str, str]
    consequence_labels: dict[str, str]
    narrator_defaults: dict[str, Any]


@dataclass
class RecapLimitsConfig:
    recap_log_window: int
    recap_narration_window: int
    recap_narration_truncate: int
    recap_campaign_history_window: int
    recap_campaign_summary_truncate: int
    recap_campaign_window: int


@dataclass
class TruncationsConfig:
    log_xshort: int
    log_short: int
    log_medium: int
    log_long: int
    log_xlong: int
    prompt_xshort: int
    prompt_short: int
    prompt_medium: int
    prompt_xlong: int
    prompt_xxlong: int
    narration_preview: int


@dataclass
class PersistenceConfig:
    default_save_name: str
