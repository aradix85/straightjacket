#!/usr/bin/env python3
"""Straightjacket data models.

All model types are importable from here:
    from .models import GameState, NpcData, RollResult, ...

Implementation split across:
- serialization.py: generic serialize/deserialize
- models_base.py: EngineConfig, Resources, ClockData, ProgressTrack, WorldState, ClockEvent, PlayerPreferences
- models_npc.py: MemoryEntry, NpcData
- models_story.py: ThreadEntry, CharacterListEntry, SceneLogEntry, NarrationEntry, StoryAct, CurrentAct,
                    Revelation, PossibleEnding, StoryBlueprint, DirectorGuidance, NarrativeState,
                    NpcEvolution, ChapterSummary, CampaignState

This file defines: RollResult, BrainResult, TurnSnapshot, GameState (top-level composites).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .logging_util import log
from .models_base import (  # noqa: F401
    ClockData,
    ClockEvent,
    EngineConfig,
    FateResult,
    PlayerPreferences,
    ProgressTrack,
    RandomEvent,
    Resources,
    ThreatData,
    ThreatEvent,
    WorldState,
)
from .models_npc import (  # noqa: F401
    NPC_STATUSES,
    MemoryEntry,
    NpcData,
)
from .models_story import (  # noqa: F401
    CampaignState,
    CharacterListEntry,
    ChapterSummary,
    CurrentAct,
    DirectorGuidance,
    NarrationEntry,
    NarrativeState,
    NpcEvolution,
    PossibleEnding,
    Revelation,
    SceneLogEntry,
    StoryAct,
    StoryBlueprint,
    ThreadEntry,
)
from .serialization import SerializableMixin


# ROLL RESULT


@dataclass
class RollResult(SerializableMixin):
    d1: int
    d2: int
    c1: int
    c2: int
    stat_name: str
    stat_value: int
    action_score: int
    result: str
    move: str
    match: bool = False


# BRAIN RESULT


@dataclass
class BrainResult(SerializableMixin):
    """Structured output from call_brain."""

    type: str = "action"
    move: str = "dialog"
    stat: str = "none"
    approach: str = ""
    target_npc: str | None = None
    dialog_only: bool = False
    player_intent: str = ""
    world_addition: str | None = None
    location_change: str | None = None
    track_name: str | None = None
    track_rank: str | None = None
    target_track: str | None = None
    fate_question: str | None = None  # Yes/no question about the fiction; engine resolves after classification
    oracle_table: str | None = None  # Datasworn oracle path; engine rolls after classification


# TURN SNAPSHOT


@dataclass
class TurnSnapshot(SerializableMixin):
    """Snapshot of game state plus turn context for correction/burn.

    State fields (resources, world, etc.) are stored as dicts for restore().
    Turn context (player_input, brain, roll, narration) is set during turn processing.
    """

    resources: dict = field(default_factory=dict)
    world: dict = field(default_factory=dict)
    narrative: dict = field(default_factory=dict)
    campaign: dict = field(default_factory=dict)
    npcs: list[dict] = field(default_factory=list)
    progress_tracks: list[dict] = field(default_factory=list)
    threats: list[dict] = field(default_factory=list)
    impacts: list[str] = field(default_factory=list)
    crisis_mode: bool = False
    game_over: bool = False
    player_input: str = ""
    brain: BrainResult | None = None
    roll: RollResult | None = None
    narration: str | None = None


# GAME STATE


@dataclass
class GameState(SerializableMixin):
    """Complete game state. Sub-objects own logically grouped fields."""

    player_name: str = ""
    character_concept: str = ""
    pronouns: str = ""
    paths: list[str] = field(default_factory=list)
    background_vow: str = ""
    setting_id: str = ""
    setting_genre: str = ""
    setting_tone: str = ""
    setting_archetype: str = ""
    setting_description: str = ""
    edge: int = 1
    heart: int = 2
    iron: int = 1
    shadow: int = 1
    wits: int = 2
    backstory: str = ""
    assets: list[str] = field(default_factory=list)
    progress_tracks: list[ProgressTrack] = field(default_factory=list)
    threats: list[ThreatData] = field(default_factory=list)
    impacts: list[str] = field(default_factory=list)
    truths: dict[str, str] = field(default_factory=dict)

    resources: Resources = field(default_factory=Resources)
    world: WorldState = field(default_factory=WorldState)
    narrative: NarrativeState = field(default_factory=NarrativeState)
    campaign: CampaignState = field(default_factory=CampaignState)
    preferences: PlayerPreferences = field(default_factory=PlayerPreferences)

    npcs: list[NpcData] = field(default_factory=list)
    crisis_mode: bool = False
    game_over: bool = False

    last_turn_snapshot: TurnSnapshot | None = field(default=None, repr=False)
    post_epilogue_director_done: bool = field(default=False, repr=False)

    _STAT_NAMES = frozenset({"edge", "heart", "iron", "shadow", "wits"})

    def get_stat(self, name: str) -> int:
        """Get a character stat by name (edge/heart/iron/shadow/wits)."""
        if name not in self._STAT_NAMES:
            raise ValueError(f"Unknown stat: {name!r}")
        return getattr(self, name)

    def snapshot(self) -> TurnSnapshot:
        """Complete snapshot of all mutable state. Called once at turn start."""
        return TurnSnapshot(
            resources=self.resources.snapshot(),
            world=self.world.snapshot(),
            narrative=self.narrative.snapshot(),
            campaign=self.campaign.snapshot(),
            npcs=[n.to_dict() for n in self.npcs],
            progress_tracks=[t.to_dict() for t in self.progress_tracks],
            threats=[t.to_dict() for t in self.threats],
            impacts=list(self.impacts),
            crisis_mode=self.crisis_mode,
            game_over=self.game_over,
        )

    def restore(self, snap: TurnSnapshot) -> None:
        """Restore all mutable state from a snapshot."""
        self.resources.restore(snap.resources)
        self.world.restore(snap.world)
        self.narrative.restore(snap.narrative)
        self.campaign.restore(snap.campaign)
        self.npcs = [NpcData.from_dict(n) for n in snap.npcs]
        self.progress_tracks = [ProgressTrack.from_dict(t) for t in snap.progress_tracks]
        self.threats = [ThreatData.from_dict(t) for t in snap.threats]
        self.impacts = list(snap.impacts)
        self.crisis_mode = snap.crisis_mode
        self.game_over = snap.game_over
        log(
            f"[GameState] Restored from snapshot: "
            f"H{self.resources.health} Sp{self.resources.spirit} "
            f"Su{self.resources.supply} Chaos{self.world.chaos_factor}"
        )
        # Rebuild database from restored state
        from .db import sync as _db_sync
        from .db.connection import reset_db

        reset_db()
        _db_sync(self)
