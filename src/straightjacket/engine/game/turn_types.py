from typing import Any
from dataclasses import dataclass, field

from ..ai.provider_base import AIProvider, NarrationSink
from ..datasworn.moves import Move
from ..models import ClockFillResult
from ..models import (
    BrainResult,
    ClockEvent,
    EngineConfig,
    GameState,
    NpcData,
    ProgressTrack,
    RandomEvent,
    ResolvedFact,
    RollResult,
    SceneSetup,
    ThreatEvent,
    TurnSnapshot,
)


@dataclass
class SceneContext:
    provider: AIProvider
    game: GameState
    brain: BrainResult
    config: EngineConfig | None
    player_message: str
    scene_setup: SceneSetup
    scene_present_ids: set[str]
    pending_revs: list[Any]
    npc_activation_debug: dict[str, Any]
    facts: list[ResolvedFact]
    activated_npcs: list[NpcData] = field(default_factory=list)
    mentioned_npcs: list[NpcData] = field(default_factory=list)
    pending_random_events: list[RandomEvent] = field(default_factory=list)
    stream: NarrationSink | None = None
    narrator_note: str = ""
    summary_label: str = "Action"


@dataclass
class RollOutcome:
    roll: RollResult
    ds_move: Move | None
    track: ProgressTrack | None
    is_progress_roll: bool


@dataclass
class BurnOffer:
    roll: RollResult
    new_result: str
    cost: int
    brain: BrainResult
    player_words: str
    scene_setup: SceneSetup
    ds_move: Move | None
    random_events: list[RandomEvent]
    facts: list[ResolvedFact]
    resume_snapshot: TurnSnapshot


@dataclass
class ActionResolution:
    position: str
    effect: str
    consequences: list[str]
    clock_events: list[ClockEvent]
    npc_agency: list[str]
    agency_clock_events: list[ClockEvent]
    threat_events: list[ThreatEvent]
    clock_fill_results: list[ClockFillResult]
