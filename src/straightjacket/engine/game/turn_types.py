"""Shared dataclass types for the turn pipeline.

SceneContext is built once per turn and passed to both the dialog and
action branches. RollOutcome is the output of the roll phase; it carries
move/track context through to consequence resolution. ActionResolution
bundles the output of the consequences phase so the narration phase can
consume it.

These types live in their own module to keep turn.py, action_resolution.py
and scene_finalization.py free of each other's implementation details.
"""

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
    """Shared context built once per turn, passed to both dialog and action paths."""

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
    """Result of the roll phase: roll plus the move/track context it came from."""

    roll: RollResult
    ds_move: Move | None
    track: ProgressTrack | None
    is_progress_roll: bool


@dataclass
class ActionResolution:
    """Everything produced by the consequences phase of an action turn."""

    position: str
    effect: str
    consequences: list[str]
    clock_events: list[ClockEvent]
    npc_agency: list[str]
    agency_clock_events: list[ClockEvent]
    threat_events: list[ThreatEvent]
