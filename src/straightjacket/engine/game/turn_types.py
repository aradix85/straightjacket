from dataclasses import dataclass, field

from ..ai.provider_base import AIProvider
from ..datasworn.moves import Move
from ..mechanics.scene import SceneSetup
from ..models import (
    BrainResult,
    ClockEvent,
    EngineConfig,
    GameState,
    NpcData,
    ProgressTrack,
    RandomEvent,
    RollResult,
    ThreatEvent,
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
    pending_revs: list
    npc_activation_debug: dict
    activated_npcs: list[NpcData] = field(default_factory=list)
    mentioned_npcs: list[NpcData] = field(default_factory=list)
    pending_random_events: list[RandomEvent] = field(default_factory=list)


@dataclass
class RollOutcome:
    roll: RollResult
    ds_move: Move | None
    track: ProgressTrack | None
    is_progress_roll: bool


@dataclass
class ActionResolution:
    position: str
    effect: str
    consequences: list[str]
    clock_events: list[ClockEvent]
    npc_agency: list[str]
    agency_clock_events: list[ClockEvent]
    threat_events: list[ThreatEvent]
