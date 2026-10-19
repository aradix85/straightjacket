from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models_base import ClockEvent, Consequence, ProgressTrack
from .serialization import SerializableMixin


@dataclass
class ThreadEntry(SerializableMixin):
    id: str
    name: str
    thread_type: str
    source: str
    weight: int = 1
    linked_track_id: str | None = None
    active: bool = True


@dataclass
class CharacterListEntry(SerializableMixin):
    id: str
    name: str
    entry_type: str
    weight: int = 1
    active: bool = True
    ac_status: str = ""


@dataclass
class PlotlineEntry(SerializableMixin):
    id: str
    name: str
    status: str
    turning_point_count: int = 0


@dataclass
class SceneLogEntry(SerializableMixin):
    scene: int = 0
    scene_type: str = field(kw_only=True)
    summary: str = ""
    move: str = ""
    result: str = ""
    consequences: list[Consequence] = field(default_factory=list)
    clock_events: list[ClockEvent] = field(default_factory=list)
    position: str = "risky"
    effect: str = "standard"
    rich_summary: str = ""
    oracle_answer: str = ""


@dataclass
class NarrationEntry(SerializableMixin):
    scene: int
    prompt_summary: str
    narration: str


@dataclass
class StoryAct(SerializableMixin):
    phase: str
    title: str
    goal: str
    scene_range: list[int]
    mood: str
    transition_trigger: str


@dataclass
class CurrentAct:
    _NOT_SERIALIZED = True

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
class Revelation(SerializableMixin):
    id: str
    content: str
    earliest_scene: int
    dramatic_weight: str


@dataclass
class PossibleEnding(SerializableMixin):
    type: str
    description: str


@dataclass
class StoryBlueprint(SerializableMixin):
    central_conflict: str
    antagonist_force: str
    thematic_thread: str
    structure_type: str
    acts: list[StoryAct] = field(default_factory=list)
    revelations: list[Revelation] = field(default_factory=list)
    possible_endings: list[PossibleEnding] = field(default_factory=list)
    revealed: list[str] = field(default_factory=list)
    triggered_transitions: list[str] = field(default_factory=list)
    triggered_director_phases: list[str] = field(default_factory=list)
    story_complete: bool = False


@dataclass
class DirectorGuidance(SerializableMixin):
    narrator_guidance: str = ""
    npc_guidance: dict[str, str] = field(default_factory=dict)
    arc_notes: str = ""


@dataclass
class KeyedScene(SerializableMixin):
    id: str
    trigger_type: str
    trigger_value: str
    priority: int
    narrative_hint: str
    bound_entity_id: str | None = None
    source: str = ""


@dataclass
class NarrativeState(SerializableMixin):
    scene_count: int = 0
    session_log: list[SceneLogEntry] = field(default_factory=list)
    narration_history: list[NarrationEntry] = field(default_factory=list)
    story_blueprint: StoryBlueprint | None = None
    director_guidance: DirectorGuidance = field(default_factory=DirectorGuidance)
    scene_intensity_history: list[str] = field(default_factory=list)
    threads: list[ThreadEntry] = field(default_factory=list)
    characters_list: list[CharacterListEntry] = field(default_factory=list)
    plotlines_list: list[PlotlineEntry] = field(default_factory=list)
    keyed_scenes: list[KeyedScene] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "scene_count": self.scene_count,
            "session_log": [e.to_dict() for e in self.session_log],
            "narration_history": [n.to_dict() for n in self.narration_history],
            "threads": [t.to_dict() for t in self.threads],
            "characters_list": [c.to_dict() for c in self.characters_list],
            "plotlines_list": [p.to_dict() for p in self.plotlines_list],
            "keyed_scenes": [k.to_dict() for k in self.keyed_scenes],
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

    def restore(self, snap: dict[str, Any]) -> None:
        self.scene_count = snap["scene_count"]
        self.director_guidance = DirectorGuidance.from_dict(snap["director_guidance"])
        self.scene_intensity_history = list(snap["scene_intensity_history"])
        self.session_log = [SceneLogEntry.from_dict(e) for e in snap["session_log"]]
        self.narration_history = [NarrationEntry.from_dict(n) for n in snap["narration_history"]]
        self.threads = [ThreadEntry.from_dict(t) for t in snap["threads"]]
        self.characters_list = [CharacterListEntry.from_dict(c) for c in snap["characters_list"]]
        self.plotlines_list = [PlotlineEntry.from_dict(p) for p in snap["plotlines_list"]]
        self.keyed_scenes = [KeyedScene.from_dict(k) for k in snap["keyed_scenes"]]
        bp, bp_snap = self.story_blueprint, snap["story_blueprint_snapshot"]
        if (bp is None) != (bp_snap is None):
            raise ValueError("a turn's snapshot and the game disagree on whether there is a story blueprint")
        if bp is not None:
            bp.revealed = list(bp_snap["revealed"])
            bp.triggered_transitions = list(bp_snap["triggered_transitions"])
            bp.triggered_director_phases = list(bp_snap["triggered_director_phases"])
            bp.story_complete = bp_snap["story_complete"]


@dataclass
class InheritanceRollResult(SerializableMixin):
    track_name: str
    result: str
    new_filled_boxes: int


@dataclass
class PredecessorRecord(SerializableMixin):
    player_name: str
    pronouns: str
    character_concept: str
    background_vow: str
    setting_id: str
    chapters_played: int
    scenes_played: int
    end_reason: str
    legacy_filled_boxes: dict[str, int]
    inheritance_rolls: list[InheritanceRollResult]


@dataclass
class ChapterSummary(SerializableMixin):
    chapter: int
    title: str
    summary: str
    unresolved_threads: list[str]


@dataclass
class CampaignState(SerializableMixin):
    campaign_history: list[ChapterSummary] = field(default_factory=list)
    predecessors: list[PredecessorRecord] = field(default_factory=list)
    chapter_number: int = 1
    epilogue_dismissed: bool = False

    pending_succession: bool = False

    xp: int = 0
    xp_spent: int = 0
    legacy: dict[str, ProgressTrack] = field(kw_only=True)

    @property
    def xp_available(self) -> int:
        return self.xp - self.xp_spent

    def snapshot(self) -> dict[str, Any]:
        return {
            "epilogue_dismissed": self.epilogue_dismissed,
            "pending_succession": self.pending_succession,
            "xp": self.xp,
            "xp_spent": self.xp_spent,
            "legacy": {name: track.to_dict() for name, track in self.legacy.items()},
        }

    def restore(self, snap: dict[str, Any]) -> None:
        self.epilogue_dismissed = snap["epilogue_dismissed"]
        self.pending_succession = snap["pending_succession"]
        self.xp = snap["xp"]
        self.xp_spent = snap["xp_spent"]
        self.legacy = {name: ProgressTrack.from_dict(track) for name, track in snap["legacy"].items()}
