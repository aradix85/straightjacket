from dataclasses import dataclass

from straightjacket.engine.ai.provider_base import AIProvider, NarrationSink
from straightjacket.engine.models import (
    BrainResult,
    ClockEvent,
    ClockFillResult,
    Consequence,
    GameState,
    RandomEvent,
    ResolvedFact,
    Revelation,
    RollResult,
    SceneSetup,
    ThreatEvent,
    TurnSnapshot,
)
from straightjacket.engine.prompt_shared import PromptScene
from straightjacket.engine.ruleset.moves import Move


@dataclass
class SceneContext:
    provider: AIProvider
    game: GameState
    brain: BrainResult
    scene: PromptScene
    revelation: Revelation | None
    facts: list[ResolvedFact]
    summary_label: str
    pending_random_events: list[RandomEvent]
    stream: NarrationSink | None
    narrator_note: str


@dataclass
class DirectorCall:
    narration: str


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
    consequences: list[Consequence]
    clock_events: list[ClockEvent]
    npc_agency: list[str]
    agency_clock_events: list[ClockEvent]
    threat_events: list[ThreatEvent]
    clock_fill_results: list[ClockFillResult]
