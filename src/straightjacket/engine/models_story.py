from __future__ import annotations

import copy
from dataclasses import dataclass, field

from straightjacket.engine.models_base import ClockEvent, Consequence, ProgressTrack
from straightjacket.engine.serialization import SerializableMixin


@dataclass
class ThreadEntry(SerializableMixin):
    id: str
    name: str
    thread_type: str
    source: str
    weight: int
    linked_track_id: str | None
    active: bool


@dataclass
class CharacterListEntry(SerializableMixin):
    id: str
    name: str
    entry_type: str
    weight: int
    active: bool
    ac_status: str


@dataclass
class PlotlineEntry(SerializableMixin):
    id: str
    name: str
    status: str
    turning_point_count: int


@dataclass(kw_only=True)
class SceneLogEntry(SerializableMixin):
    scene: int
    scene_type: str
    summary: str
    move: str
    result: str
    consequences: list[Consequence] = field(default_factory=list)
    clock_events: list[ClockEvent] = field(default_factory=list)
    position: str
    effect: str
    rich_summary: str
    oracle_answer: str


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

    phase: str
    title: str
    goal: str
    scene_range: list[int]
    mood: str
    transition_trigger: str
    act_number: int
    total_acts: int
    progress: str
    approaching_end: bool


@dataclass
class Revelation(SerializableMixin):
    id: str
    content: str
    act_number: int
    keyed_scene_source: str
    dramatic_weight: str


@dataclass
class PossibleEnding(SerializableMixin):
    type: str
    description: str


@dataclass(kw_only=True)
class StoryBlueprint(SerializableMixin):
    central_conflict: str
    antagonist_force: str
    thematic_thread: str
    acts: list[StoryAct] = field(default_factory=list)
    revelations: list[Revelation] = field(default_factory=list)
    possible_endings: list[PossibleEnding] = field(default_factory=list)
    revealed: list[str] = field(default_factory=list)
    triggered_transitions: list[str] = field(default_factory=list)
    triggered_director_phases: list[str] = field(default_factory=list)
    story_complete: bool


@dataclass(kw_only=True)
class DirectorGuidance(SerializableMixin):
    narrator_guidance: str
    npc_guidance: dict[str, str] = field(default_factory=dict)
    arc_notes: str


@dataclass
class KeyedScene(SerializableMixin):
    id: str
    trigger_type: str
    trigger_value: str
    priority: int
    narrative_hint: str
    bound_entity_id: str | None
    source: str


@dataclass
class BlueprintProgress(SerializableMixin):
    revealed: list[str]
    triggered_transitions: list[str]
    triggered_director_phases: list[str]
    story_complete: bool


@dataclass(kw_only=True)
class NarrativeSnapshot(SerializableMixin):
    scene_count: int
    session_log: list[SceneLogEntry]
    narration_history: list[NarrationEntry]
    threads: list[ThreadEntry]
    characters_list: list[CharacterListEntry]
    plotlines_list: list[PlotlineEntry]
    keyed_scenes: list[KeyedScene]
    director_guidance: DirectorGuidance
    scene_intensity_history: list[str]
    story_blueprint_snapshot: BlueprintProgress | None


@dataclass(kw_only=True)
class NarrativeState(SerializableMixin):
    scene_count: int
    session_log: list[SceneLogEntry] = field(default_factory=list)
    narration_history: list[NarrationEntry] = field(default_factory=list)
    story_blueprint: StoryBlueprint | None
    director_guidance: DirectorGuidance
    scene_intensity_history: list[str] = field(default_factory=list)
    threads: list[ThreadEntry] = field(default_factory=list)
    characters_list: list[CharacterListEntry] = field(default_factory=list)
    plotlines_list: list[PlotlineEntry] = field(default_factory=list)
    keyed_scenes: list[KeyedScene] = field(default_factory=list)

    def snapshot(self) -> NarrativeSnapshot:
        blueprint = self.story_blueprint
        return copy.deepcopy(
            NarrativeSnapshot(
                scene_count=self.scene_count,
                session_log=self.session_log,
                narration_history=self.narration_history,
                threads=self.threads,
                characters_list=self.characters_list,
                plotlines_list=self.plotlines_list,
                keyed_scenes=self.keyed_scenes,
                director_guidance=self.director_guidance,
                scene_intensity_history=self.scene_intensity_history,
                story_blueprint_snapshot=BlueprintProgress(
                    revealed=blueprint.revealed,
                    triggered_transitions=blueprint.triggered_transitions,
                    triggered_director_phases=blueprint.triggered_director_phases,
                    story_complete=blueprint.story_complete,
                )
                if blueprint
                else None,
            )
        )

    def restore(self, snap: NarrativeSnapshot) -> None:
        held = copy.deepcopy(snap)
        blueprint, progress = self.story_blueprint, held.story_blueprint_snapshot
        if (blueprint is None) != (progress is None):
            msg = "a turn's snapshot and the game disagree on whether there is a story blueprint"
            raise ValueError(msg)
        self.scene_count = held.scene_count
        self.session_log = held.session_log
        self.narration_history = held.narration_history
        self.threads = held.threads
        self.characters_list = held.characters_list
        self.plotlines_list = held.plotlines_list
        self.keyed_scenes = held.keyed_scenes
        self.director_guidance = held.director_guidance
        self.scene_intensity_history = held.scene_intensity_history
        if blueprint is not None and progress is not None:
            blueprint.revealed = progress.revealed
            blueprint.triggered_transitions = progress.triggered_transitions
            blueprint.triggered_director_phases = progress.triggered_director_phases
            blueprint.story_complete = progress.story_complete


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
class CampaignSnapshot(SerializableMixin):
    predecessors: list[PredecessorRecord]
    pending_succession: bool
    xp: int
    legacy: dict[str, ProgressTrack]


@dataclass(kw_only=True)
class CampaignState(SerializableMixin):
    campaign_history: list[ChapterSummary] = field(default_factory=list)
    predecessors: list[PredecessorRecord] = field(default_factory=list)
    chapter_number: int
    epilogue_dismissed: bool

    pending_succession: bool

    xp: int
    xp_spent: int
    legacy: dict[str, ProgressTrack]

    @property
    def xp_available(self) -> int:
        return self.xp - self.xp_spent

    def snapshot(self) -> CampaignSnapshot:
        return copy.deepcopy(
            CampaignSnapshot(
                predecessors=self.predecessors,
                pending_succession=self.pending_succession,
                xp=self.xp,
                legacy=self.legacy,
            )
        )

    def restore(self, snap: CampaignSnapshot) -> None:
        held = copy.deepcopy(snap)
        self.predecessors = held.predecessors
        self.pending_succession = held.pending_succession
        self.xp = held.xp
        self.legacy = held.legacy
