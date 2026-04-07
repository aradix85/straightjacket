#!/usr/bin/env python3
"""Straightjacket data models.

All model types are importable from here:
    from .models import GameState, NpcData, RollResult, ...

Implementation split across:
- models_base.py: serialization helpers, EngineConfig, Resources, ClockData, WorldState, ClockEvent, PlayerPreferences
- models_npc.py: MemoryEntry, NpcData
- models_story.py: SceneLogEntry, NarrationEntry, StoryAct, CurrentAct, Revelation, PossibleEnding,
                    StoryBlueprint, DirectorGuidance, NarrativeState, NpcEvolution, ChapterSummary, CampaignState

This file defines: RollResult, BrainResult, TurnSnapshot, GameState (top-level composites).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from .logging_util import log
from .models_base import (  # noqa: F401
    ClockData,
    ClockEvent,
    EngineConfig,
    PlayerPreferences,
    Resources,
    WorldState,
    _fields_from_dict,
    _fields_to_dict,
)
from .models_npc import (  # noqa: F401
    MemoryEntry,
    NpcData,
)
from .models_story import (  # noqa: F401
    CampaignState,
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
)


# ROLL RESULT

@dataclass
class RollResult:
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
class BrainResult:
    """Structured output from call_brain."""
    type: str = "action"
    move: str = "dialog"
    stat: str = "none"
    approach: str = ""
    target_npc: str | None = None
    dialog_only: bool = False
    player_intent: str = ""
    world_addition: str | None = None
    position: str = "risky"
    effect: str = "standard"
    dramatic_question: str = ""
    location_change: str | None = None
    time_progression: str = "none"

    @classmethod
    def from_dict(cls, data: dict) -> BrainResult:
        return _fields_from_dict(cls, data)


# TURN SNAPSHOT

@dataclass
class TurnSnapshot:
    """Snapshot of game state plus turn context for correction/burn.

    State fields (resources, world, etc.) are stored as dicts for restore().
    Turn context (player_input, brain, roll, narration) is set during turn processing.
    """
    resources: dict = field(default_factory=dict)
    world: dict = field(default_factory=dict)
    narrative: dict = field(default_factory=dict)
    campaign: dict = field(default_factory=dict)
    npcs: list[dict] = field(default_factory=list)
    crisis_mode: bool = False
    game_over: bool = False
    player_input: str = ""
    brain: BrainResult | None = None
    roll: RollResult | None = None
    narration: str | None = None

    def to_dict(self) -> dict:
        d = {
            "resources": self.resources,
            "world": self.world,
            "narrative": self.narrative,
            "campaign": self.campaign,
            "npcs": self.npcs,
            "crisis_mode": self.crisis_mode,
            "game_over": self.game_over,
            "player_input": self.player_input,
            "brain": _fields_to_dict(self.brain) if self.brain else None,
            "narration": self.narration,
        }
        if self.roll is not None:
            d["roll"] = dataclasses.asdict(self.roll)
        else:
            d["roll"] = None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> TurnSnapshot:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in known}
        snap = cls(**kwargs)
        if isinstance(snap.roll, dict):
            try:
                snap.roll = RollResult(**snap.roll)
            except (TypeError, KeyError):
                snap.roll = None
        if isinstance(snap.brain, dict):
            snap.brain = BrainResult.from_dict(snap.brain)
        return snap


# GAME STATE

@dataclass
class GameState:
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

    def get_stat(self, name: str) -> int:
        """Get a character stat by name (edge/heart/iron/shadow/wits)."""
        return getattr(self, name, 0)

    def snapshot(self) -> TurnSnapshot:
        """Complete snapshot of all mutable state. Called once at turn start."""
        return TurnSnapshot(
            resources=self.resources.snapshot(),
            world=self.world.snapshot(),
            narrative=self.narrative.snapshot(),
            campaign=self.campaign.snapshot(),
            npcs=[n.to_dict() for n in self.npcs],
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
        self.crisis_mode = snap.crisis_mode
        self.game_over = snap.game_over
        log(f"[GameState] Restored from snapshot: "
            f"H{self.resources.health} Sp{self.resources.spirit} "
            f"Su{self.resources.supply} Chaos{self.world.chaos_factor}")

    _IDENTITY_FIELDS = (
        "player_name", "character_concept", "pronouns", "paths",
        "background_vow", "setting_id", "setting_genre",
        "setting_tone", "setting_archetype", "setting_description",
        "edge", "heart", "iron", "shadow", "wits", "backstory",
    )

    _SUB_OBJECTS = ("resources", "world", "narrative", "campaign", "preferences")

    def to_dict(self) -> dict:
        """Serialize to nested dict for JSON persistence."""
        d = {k: getattr(self, k) for k in self._IDENTITY_FIELDS}
        for name in self._SUB_OBJECTS:
            d[name] = getattr(self, name).to_dict()
        d["npcs"] = [n.to_dict() for n in self.npcs]
        d["crisis_mode"] = self.crisis_mode
        d["game_over"] = self.game_over
        d["last_turn_snapshot"] = self.last_turn_snapshot.to_dict() if self.last_turn_snapshot else None
        return d

    @classmethod
    def from_dict(cls, data: dict) -> GameState:
        """Deserialize from nested dict."""
        game = cls()
        for k in cls._IDENTITY_FIELDS:
            setattr(game, k, data[k])
        game.resources = Resources.from_dict(data["resources"])
        game.world = WorldState.from_dict(data["world"])
        game.narrative = NarrativeState.from_dict(data["narrative"])
        game.campaign = CampaignState.from_dict(data["campaign"])
        game.preferences = PlayerPreferences.from_dict(data["preferences"])
        game.npcs = [NpcData.from_dict(n) for n in data["npcs"]]
        game.crisis_mode = data["crisis_mode"]
        game.game_over = data["game_over"]
        snap = data["last_turn_snapshot"]
        game.last_turn_snapshot = TurnSnapshot.from_dict(snap) if snap is not None else None
        return game
