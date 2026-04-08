#!/usr/bin/env python3
"""Story model types: scene log, narration, story blueprint, director guidance,
narrative state, campaign state."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models_base import ClockEvent
from .serialization import deserialize, serialize


@dataclass
class SceneLogEntry:
    """One entry in the session log. Created per turn/correction."""

    scene: int = 0
    summary: str = ""
    move: str = ""
    result: str = ""
    consequences: list[str] = field(default_factory=list)
    clock_events: list[ClockEvent] = field(default_factory=list)
    position: str = "risky"
    effect: str = "standard"
    dramatic_question: str = ""
    chaos_interrupt: str | None = None
    npc_activation: dict = field(default_factory=dict)
    validator: dict = field(default_factory=dict)
    rich_summary: str = ""
    director_trigger: str = ""
    revelation_check: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> SceneLogEntry:
        return deserialize(cls, data)


@dataclass
class NarrationEntry:
    """One entry in narration history. Used for narrator conversation context."""

    scene: int = 0
    prompt_summary: str = ""
    narration: str = ""

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> NarrationEntry:
        return deserialize(cls, data)


@dataclass
class StoryAct:
    """Single act in a story blueprint."""

    phase: str = ""
    title: str = ""
    goal: str = ""
    scene_range: list[int] = field(default_factory=list)
    mood: str = ""
    transition_trigger: str = ""

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> StoryAct:
        return deserialize(cls, data)


@dataclass
class CurrentAct:
    """Computed act info from get_current_act(). Not serialized."""

    phase: str = ""
    title: str = ""
    goal: str = ""
    scene_range: list[int] = field(default_factory=list)
    mood: str = ""
    transition_trigger: str = ""
    act_number: int = 1
    total_acts: int = 3
    progress: str = "early"
    approaching_end: bool = False


@dataclass
class Revelation:
    """Story revelation with timing and weight."""

    id: str = ""
    content: str = ""
    earliest_scene: int = 999
    dramatic_weight: str = "medium"

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> Revelation:
        return deserialize(cls, data)


@dataclass
class PossibleEnding:
    """Possible story ending."""

    type: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> PossibleEnding:
        return deserialize(cls, data)


@dataclass
class StoryBlueprint:
    """Story architect output. Tracks act structure, revelations, and completion."""

    central_conflict: str = ""
    antagonist_force: str = ""
    thematic_thread: str = ""
    structure_type: str = "3act"
    acts: list[StoryAct] = field(default_factory=list)
    revelations: list[Revelation] = field(default_factory=list)
    possible_endings: list[PossibleEnding] = field(default_factory=list)
    revealed: list[str] = field(default_factory=list)
    triggered_transitions: list[str] = field(default_factory=list)
    triggered_director_phases: list[str] = field(default_factory=list)
    story_complete: bool = False

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> StoryBlueprint:
        return deserialize(cls, data)

    @property
    def has_acts(self) -> bool:
        return bool(self.acts)


@dataclass
class DirectorGuidance:
    """Director output stored between turns for narrator context."""

    narrator_guidance: str = ""
    npc_guidance: dict[str, str] = field(default_factory=dict)
    pacing: str = ""
    arc_notes: str = ""

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> DirectorGuidance:
        return deserialize(cls, data)


@dataclass
class NarrativeState:
    """Scene tracking, history, story arc, director guidance."""

    scene_count: int = 0
    session_log: list[SceneLogEntry] = field(default_factory=list)
    narration_history: list[NarrationEntry] = field(default_factory=list)
    story_blueprint: StoryBlueprint | None = None
    director_guidance: DirectorGuidance = field(default_factory=DirectorGuidance)
    scene_intensity_history: list[str] = field(default_factory=list)

    def snapshot(self) -> dict:
        """Lightweight snapshot for undo. Captures lengths (not full lists) and mutable sub-state."""
        return {
            "scene_count": self.scene_count,
            "session_log_len": len(self.session_log),
            "narration_history_len": len(self.narration_history),
            "director_guidance": self.director_guidance.to_dict(),
            "scene_intensity_history": list(self.scene_intensity_history),
            "story_blueprint_snapshot": {
                "revealed": list(self.story_blueprint.revealed),
                "triggered_transitions": list(self.story_blueprint.triggered_transitions),
                "triggered_director_phases": list(self.story_blueprint.triggered_director_phases),
                "story_complete": self.story_blueprint.story_complete,
            }
            if self.story_blueprint
            else None,
        }

    def restore(self, snap: dict) -> None:
        """Restore from a lightweight snapshot. Truncates lists to snapshotted lengths."""
        self.scene_count = snap["scene_count"]
        self.director_guidance = DirectorGuidance.from_dict(snap["director_guidance"])
        self.scene_intensity_history = list(snap["scene_intensity_history"])
        self.session_log = self.session_log[: snap["session_log_len"]]
        self.narration_history = self.narration_history[: snap["narration_history_len"]]
        bp_snap = snap["story_blueprint_snapshot"]
        if bp_snap is not None and self.story_blueprint is not None:
            self.story_blueprint.revealed = list(bp_snap["revealed"])
            self.story_blueprint.triggered_transitions = list(bp_snap["triggered_transitions"])
            self.story_blueprint.triggered_director_phases = list(bp_snap["triggered_director_phases"])
            self.story_blueprint.story_complete = bp_snap["story_complete"]
        elif bp_snap is None:
            # Blueprint was absent at snapshot time — remove any blueprint added since
            self.story_blueprint = None

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> NarrativeState:
        return deserialize(cls, data)


@dataclass
class NpcEvolution:
    """Projected NPC change from chapter summary."""

    name: str = ""
    projection: str = ""

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> NpcEvolution:
        return deserialize(cls, data)


@dataclass
class ChapterSummary:
    """Summary of a completed chapter for campaign continuity."""

    chapter: int = 0
    title: str = ""
    summary: str = ""
    unresolved_threads: list[str] = field(default_factory=list)
    character_growth: str = ""
    npc_evolutions: list[NpcEvolution] = field(default_factory=list)
    thematic_question: str = ""
    post_story_location: str = ""
    scenes: int = 0

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> ChapterSummary:
        return deserialize(cls, data)


@dataclass
class CampaignState:
    """Chapter progression and epilogue."""

    campaign_history: list[ChapterSummary] = field(default_factory=list)
    chapter_number: int = 1
    epilogue_shown: bool = False
    epilogue_dismissed: bool = False
    epilogue_text: str = ""

    def snapshot(self) -> dict:
        """Lightweight snapshot for turn undo. Only captures fields that can change
        mid-turn. campaign_history, chapter_number, and epilogue_text are excluded
        because they only change at chapter boundaries (start_new_chapter), never
        during normal turn processing or correction."""
        return {
            "epilogue_shown": self.epilogue_shown,
            "epilogue_dismissed": self.epilogue_dismissed,
        }

    def restore(self, snap: dict) -> None:
        self.epilogue_shown = snap["epilogue_shown"]
        self.epilogue_dismissed = snap["epilogue_dismissed"]

    def to_dict(self) -> dict:
        return serialize(self)

    @classmethod
    def from_dict(cls, data: dict) -> CampaignState:
        return deserialize(cls, data)
