from __future__ import annotations

from dataclasses import dataclass, field

from ..i18n import t
from .engine_loader import eng
from .models_base import ClockEvent, ProgressTrack, ThreatData
from .serialization import SerializableMixin


@dataclass
class ThreadEntry(SerializableMixin):
    id: str
    name: str
    thread_type: str
    source: str
    weight: int = 1
    linked_track_id: str = ""
    active: bool = True


@dataclass
class CharacterListEntry(SerializableMixin):
    id: str
    name: str
    entry_type: str
    weight: int = 1
    active: bool = True


@dataclass
class SceneLogEntry(SerializableMixin):
    scene: int = 0
    scene_type: str = field(kw_only=True)
    summary: str = ""
    move: str = ""
    result: str = ""
    consequences: list[str] = field(default_factory=list)
    clock_events: list[ClockEvent] = field(default_factory=list)
    position: str = "risky"
    effect: str = "standard"
    npc_activation: dict = field(default_factory=dict)
    validator: dict = field(default_factory=dict)
    rich_summary: str = ""
    director_trigger: str = ""
    oracle_answer: str = ""
    revelation_check: dict = field(default_factory=dict)


@dataclass
class NarrationEntry(SerializableMixin):
    scene: int
    prompt_summary: str
    narration: str


@dataclass
class StoryAct(SerializableMixin):
    phase: str = ""
    title: str = ""
    goal: str = ""
    scene_range: list[int] = field(default_factory=list)
    mood: str = ""
    transition_trigger: str = ""


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
    id: str = ""
    content: str = ""
    earliest_scene: int = 999
    dramatic_weight: str = "medium"


@dataclass
class PossibleEnding(SerializableMixin):
    type: str = ""
    description: str = ""


@dataclass
class StoryBlueprint(SerializableMixin):
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

    def __post_init__(self) -> None:
        triggers = eng().keyed_scenes.triggers
        if self.trigger_type not in triggers:
            raise ValueError(f"Unknown KeyedScene trigger_type {self.trigger_type!r}; registered: {sorted(triggers)}")


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
    keyed_scenes: list[KeyedScene] = field(default_factory=list)

    def snapshot(self) -> dict:
        return {
            "scene_count": self.scene_count,
            "session_log_len": len(self.session_log),
            "narration_history_len": len(self.narration_history),
            "threads_len": len(self.threads),
            "characters_list_len": len(self.characters_list),
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

    def restore(self, snap: dict) -> None:
        self.scene_count = snap["scene_count"]
        self.director_guidance = DirectorGuidance.from_dict(snap["director_guidance"])
        self.scene_intensity_history = list(snap["scene_intensity_history"])
        self.session_log = self.session_log[: snap["session_log_len"]]
        self.narration_history = self.narration_history[: snap["narration_history_len"]]
        self.threads = self.threads[: snap["threads_len"]]
        self.characters_list = self.characters_list[: snap["characters_list_len"]]
        self.keyed_scenes = [KeyedScene.from_dict(k) for k in snap["keyed_scenes"]]
        bp_snap = snap["story_blueprint_snapshot"]
        if bp_snap is not None and self.story_blueprint is not None:
            self.story_blueprint.revealed = list(bp_snap["revealed"])
            self.story_blueprint.triggered_transitions = list(bp_snap["triggered_transitions"])
            self.story_blueprint.triggered_director_phases = list(bp_snap["triggered_director_phases"])
            self.story_blueprint.story_complete = bp_snap["story_complete"]
        elif bp_snap is None:
            self.story_blueprint = None


@dataclass
class NpcEvolution(SerializableMixin):
    name: str
    projection: str


@dataclass
class InheritanceRollResult(SerializableMixin):
    track_name: str
    predecessor_filled_boxes: int
    result: str
    fraction: float
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
    legacy_quests_filled_boxes: int
    legacy_bonds_filled_boxes: int
    legacy_discoveries_filled_boxes: int
    inheritance_rolls: list[InheritanceRollResult]


@dataclass
class ChapterSummary(SerializableMixin):
    chapter: int
    title: str
    summary: str
    unresolved_threads: list[str]
    character_growth: str
    npc_evolutions: list[NpcEvolution]
    thematic_question: str
    post_story_location: str
    scenes: int
    progress_tracks: list[ProgressTrack]
    threats: list[ThreatData]
    impacts: list[str]
    assets: list[str]
    threads: list[ThreadEntry]


def _legacy_quests_factory() -> ProgressTrack:
    _e = eng()
    return ProgressTrack(
        id="legacy_quests",
        name=t("status.legacy_name_quests"),
        track_type="legacy",
        rank=_e.legacy.starting_rank,
        max_ticks=_e.progress.max_ticks,
    )


def _legacy_bonds_factory() -> ProgressTrack:
    _e = eng()
    return ProgressTrack(
        id="legacy_bonds",
        name=t("status.legacy_name_bonds"),
        track_type="legacy",
        rank=_e.legacy.starting_rank,
        max_ticks=_e.progress.max_ticks,
    )


def _legacy_discoveries_factory() -> ProgressTrack:
    _e = eng()
    return ProgressTrack(
        id="legacy_discoveries",
        name=t("status.legacy_name_discoveries"),
        track_type="legacy",
        rank=_e.legacy.starting_rank,
        max_ticks=_e.progress.max_ticks,
    )


@dataclass
class CampaignState(SerializableMixin):
    campaign_history: list[ChapterSummary] = field(default_factory=list)
    predecessors: list[PredecessorRecord] = field(default_factory=list)
    chapter_number: int = 1
    epilogue_shown: bool = False
    epilogue_dismissed: bool = False
    epilogue_text: str = ""

    pending_succession: bool = False

    xp: int = 0
    xp_spent: int = 0
    legacy_quests: ProgressTrack = field(default_factory=_legacy_quests_factory)
    legacy_bonds: ProgressTrack = field(default_factory=_legacy_bonds_factory)
    legacy_discoveries: ProgressTrack = field(default_factory=_legacy_discoveries_factory)

    @property
    def xp_available(self) -> int:
        return self.xp - self.xp_spent

    def snapshot(self) -> dict:
        return {
            "epilogue_shown": self.epilogue_shown,
            "epilogue_dismissed": self.epilogue_dismissed,
            "pending_succession": self.pending_succession,
            "xp": self.xp,
            "xp_spent": self.xp_spent,
            "legacy_quests": self.legacy_quests.to_dict(),
            "legacy_bonds": self.legacy_bonds.to_dict(),
            "legacy_discoveries": self.legacy_discoveries.to_dict(),
        }

    def restore(self, snap: dict) -> None:
        self.epilogue_shown = snap["epilogue_shown"]
        self.epilogue_dismissed = snap["epilogue_dismissed"]
        self.pending_succession = snap["pending_succession"]
        self.xp = snap["xp"]
        self.xp_spent = snap["xp_spent"]
        self.legacy_quests = ProgressTrack.from_dict(snap["legacy_quests"])
        self.legacy_bonds = ProgressTrack.from_dict(snap["legacy_bonds"])
        self.legacy_discoveries = ProgressTrack.from_dict(snap["legacy_discoveries"])
