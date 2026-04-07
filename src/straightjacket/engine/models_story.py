#!/usr/bin/env python3
"""Story model types: scene log, narration, story blueprint, director guidance,
narrative state, campaign state."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models_base import ClockEvent, _fields_from_dict, _fields_to_dict


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
        d = {}
        for f in self.__dataclass_fields__.values():
            val = getattr(self, f.name)
            if f.name == "clock_events":
                d[f.name] = [e.to_dict() for e in val]
            else:
                d[f.name] = val
        return d

    @classmethod
    def from_dict(cls, data: dict) -> SceneLogEntry:
        known = {f.name for f in cls.__dataclass_fields__.values()}
        kwargs = {k: v for k, v in data.items() if k in known}
        if "clock_events" in kwargs and isinstance(kwargs["clock_events"], list):
            kwargs["clock_events"] = [ClockEvent.from_dict(e) for e in kwargs["clock_events"]]
        return cls(**kwargs)


@dataclass
class NarrationEntry:
    """One entry in narration history. Used for narrator conversation context."""

    scene: int = 0
    prompt_summary: str = ""
    narration: str = ""

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NarrationEntry:
        return _fields_from_dict(cls, data)


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
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> StoryAct:
        return _fields_from_dict(cls, data)


@dataclass
class CurrentAct:
    """Computed act info from get_current_act(). StoryAct fields plus runtime state."""
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
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Revelation:
        return _fields_from_dict(cls, data)


@dataclass
class PossibleEnding:
    """Possible story ending."""
    type: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PossibleEnding:
        return _fields_from_dict(cls, data)


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
        return {
            "central_conflict": self.central_conflict,
            "antagonist_force": self.antagonist_force,
            "thematic_thread": self.thematic_thread,
            "structure_type": self.structure_type,
            "acts": [a.to_dict() for a in self.acts],
            "revelations": [r.to_dict() for r in self.revelations],
            "possible_endings": [e.to_dict() for e in self.possible_endings],
            "revealed": list(self.revealed),
            "triggered_transitions": list(self.triggered_transitions),
            "triggered_director_phases": list(self.triggered_director_phases),
            "story_complete": self.story_complete,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StoryBlueprint:
        bp = cls(
            central_conflict=data["central_conflict"],
            antagonist_force=data["antagonist_force"],
            thematic_thread=data["thematic_thread"],
            structure_type=data["structure_type"],
            revealed=list(data["revealed"]),
            triggered_transitions=list(data["triggered_transitions"]),
            triggered_director_phases=list(data.get("triggered_director_phases", [])),
            story_complete=bool(data["story_complete"]),
        )
        bp.acts = [StoryAct.from_dict(a) for a in data["acts"]]
        bp.revelations = [Revelation.from_dict(r) for r in data["revelations"]]
        bp.possible_endings = [PossibleEnding.from_dict(e) for e in data["possible_endings"]]
        return bp

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
        return {
            "narrator_guidance": self.narrator_guidance,
            "npc_guidance": dict(self.npc_guidance),
            "pacing": self.pacing,
            "arc_notes": self.arc_notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DirectorGuidance:
        return cls(
            narrator_guidance=data["narrator_guidance"],
            npc_guidance=dict(data["npc_guidance"]),
            pacing=data["pacing"],
            arc_notes=data["arc_notes"],
        )


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
            } if self.story_blueprint else None,
        }

    def restore(self, snap: dict) -> None:
        self.scene_count = snap["scene_count"]
        self.director_guidance = DirectorGuidance.from_dict(snap["director_guidance"])
        self.scene_intensity_history = list(snap["scene_intensity_history"])
        self.session_log = self.session_log[:snap["session_log_len"]]
        self.narration_history = self.narration_history[:snap["narration_history_len"]]
        bp_snap = snap["story_blueprint_snapshot"]
        if bp_snap is not None and self.story_blueprint is not None:
            self.story_blueprint.revealed = list(bp_snap["revealed"])
            self.story_blueprint.triggered_transitions = list(bp_snap["triggered_transitions"])
            self.story_blueprint.triggered_director_phases = list(bp_snap.get("triggered_director_phases", []))
            self.story_blueprint.story_complete = bp_snap["story_complete"]

    def to_dict(self) -> dict:
        return {
            "scene_count": self.scene_count,
            "session_log": [e.to_dict() for e in self.session_log],
            "narration_history": [e.to_dict() for e in self.narration_history],
            "story_blueprint": self.story_blueprint.to_dict() if self.story_blueprint else None,
            "director_guidance": self.director_guidance.to_dict(),
            "scene_intensity_history": list(self.scene_intensity_history),
        }

    @classmethod
    def from_dict(cls, data: dict) -> NarrativeState:
        n = cls()
        n.scene_count = data["scene_count"]
        n.session_log = [SceneLogEntry.from_dict(e) for e in data["session_log"]]
        n.narration_history = [NarrationEntry.from_dict(e) for e in data["narration_history"]]
        bp = data["story_blueprint"]
        n.story_blueprint = StoryBlueprint.from_dict(bp) if bp is not None else None
        n.director_guidance = DirectorGuidance.from_dict(data["director_guidance"])
        n.scene_intensity_history = list(data["scene_intensity_history"])
        return n


@dataclass
class NpcEvolution:
    """Projected NPC change from chapter summary."""
    name: str = ""
    projection: str = ""

    def to_dict(self) -> dict:
        return _fields_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NpcEvolution:
        return _fields_from_dict(cls, data)


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
        return {
            "chapter": self.chapter,
            "title": self.title,
            "summary": self.summary,
            "unresolved_threads": list(self.unresolved_threads),
            "character_growth": self.character_growth,
            "npc_evolutions": [e.to_dict() for e in self.npc_evolutions],
            "thematic_question": self.thematic_question,
            "post_story_location": self.post_story_location,
            "scenes": self.scenes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ChapterSummary:
        evolutions = [NpcEvolution.from_dict(e) for e in data["npc_evolutions"]]
        return cls(
            chapter=data["chapter"],
            title=data["title"],
            summary=data["summary"],
            unresolved_threads=list(data["unresolved_threads"]),
            character_growth=data["character_growth"],
            npc_evolutions=evolutions,
            thematic_question=data["thematic_question"],
            post_story_location=data["post_story_location"],
            scenes=data["scenes"],
        )


@dataclass
class CampaignState:
    """Chapter progression and epilogue."""
    campaign_history: list[ChapterSummary] = field(default_factory=list)
    chapter_number: int = 1
    epilogue_shown: bool = False
    epilogue_dismissed: bool = False
    epilogue_text: str = ""

    def snapshot(self) -> dict:
        return {
            "epilogue_shown": self.epilogue_shown,
            "epilogue_dismissed": self.epilogue_dismissed,
        }

    def restore(self, snap: dict) -> None:
        self.epilogue_shown = snap["epilogue_shown"]
        self.epilogue_dismissed = snap["epilogue_dismissed"]

    def to_dict(self) -> dict:
        return {
            "campaign_history": [ch.to_dict() for ch in self.campaign_history],
            "chapter_number": self.chapter_number,
            "epilogue_shown": self.epilogue_shown,
            "epilogue_dismissed": self.epilogue_dismissed,
            "epilogue_text": self.epilogue_text,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CampaignState:
        return cls(
            campaign_history=[ChapterSummary.from_dict(ch) for ch in data["campaign_history"]],
            chapter_number=data["chapter_number"],
            epilogue_shown=data["epilogue_shown"],
            epilogue_dismissed=data["epilogue_dismissed"],
            epilogue_text=data["epilogue_text"],
        )
